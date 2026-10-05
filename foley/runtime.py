"""Runtime posture — local-first / offline mode as one verifiable contract (#12, report 12).

``RuntimeConfig`` couples the three things "offline" must mean into a single frozen,
inspectable value, each a **consumer of an existing SSOT** (no parallel policy):

* **data egress** — ``data_egress_allow`` filters the source registry by each adapter's
  already-declared ``config['data_egress']`` (``foley.sources`` SSOT), so a network
  adapter is simply not available offline.
* **telemetry** — ``telemetry=False`` disables the observability run-artifact export
  (``foley.obs``), so nothing leaves the device.
* **redaction** — ``redaction_mode`` routes narration-derived fields through the ready
  ``foley.obs.redact.REDACT_FIELDS`` redactor, so prompts/queries/narration never sit
  in even a local run store.

:func:`offline` (``offline_scope``) applies the posture for the duration of a ``with``
block via a :class:`contextvars.ContextVar` and **restores** the prior obs state on
exit — per-call granularity, not a process-global flip. Stdlib-only, so importing this
keeps ``import foley`` dol-only.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

#: The egress classes a source may declare (``config['data_egress']`` SSOT).
LOCAL: str = "local"
EXTERNAL: str = "external"

_CURRENT_RUNTIME: "ContextVar[RuntimeConfig | None]" = ContextVar(
    "foley_runtime", default=None
)


@dataclass(frozen=True)
class RuntimeConfig:
    """A frozen runtime posture — the local-first / offline contract as data.

    Args:
        offline: Whether this posture is offline/local-first.
        data_egress_allow: The egress classes a source may use to be available
            (``{'local'}`` offline; ``{'local','external'}`` online).
        telemetry: Whether the obs run-artifact export is on.
        redaction_mode: ``'hash'`` (default, salted), ``'off'`` (drop), or ``'full'``
            (raw — local-debug only).
        http_resilience: Whether HTTP source adapters are wrapped with the
            throttle/backoff/circuit-breaker (:mod:`foley.sources.resilience`).
    """

    offline: bool = False
    data_egress_allow: "frozenset[str]" = field(
        default_factory=lambda: frozenset({LOCAL, EXTERNAL})
    )
    telemetry: bool = True
    redaction_mode: str = "hash"
    http_resilience: bool = True

    @classmethod
    def default(cls) -> "RuntimeConfig":
        """The online default: all egress allowed, telemetry on, hashed redaction."""
        return cls()

    @classmethod
    def offline_local(cls) -> "RuntimeConfig":
        """The local-first offline posture: local-only egress, telemetry off, hashed redaction."""
        return cls(
            offline=True,
            data_egress_allow=frozenset({LOCAL}),
            telemetry=False,
            redaction_mode="hash",
        )

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Build from the environment: ``FOLEY_OFFLINE`` in {1,true,yes} → offline-local."""
        if os.environ.get("FOLEY_OFFLINE", "").lower() in ("1", "true", "yes"):
            return cls.offline_local()
        return cls.default()

    def allows(self, data_egress: "str | None") -> bool:
        """Whether a source declaring ``data_egress`` is available under this posture.

        An unknown/absent declaration is **rejected** (fail-closed): a source that does
        not say where its data goes is never used offline.
        """
        return data_egress in self.data_egress_allow


class EgressBlocked(PermissionError):
    """Raised when a call would send data off the device under an offline posture.

    Every external path checks the active :class:`RuntimeConfig` through
    :func:`require_egress` — the source registry, the generate and pull façades, and
    the LLM resolver — so ``with foley.offline():`` holds on every surface, not only
    in the MCP tools.
    """


class ModelNotCached(EgressBlocked):
    """Raised under an offline posture when a model's weights are not on this machine.

    foley never downloads weights inside :func:`offline` (#86); the message names the
    model and how to fetch it beforehand, online.
    """


def load_pretrained(loader, model_id: str, *, how_to_fetch: "str | None" = None, **kwargs):
    """Call ``loader(model_id, **kwargs)`` — a ``from_pretrained`` — honouring the posture.

    Online, it is a plain call. Under :func:`offline` it passes
    ``local_files_only=True`` (no Hub request at all) and turns a cache miss (an
    ``OSError``) into :class:`ModelNotCached`; any other error passes through as is.
    foley's ``from_pretrained`` loads (CLAP, Stable Audio) go through here; loaders
    with no local-only switch (AudioSeal, whisperX) go through :func:`no_download`.

    Args:
        loader: e.g. ``ClapModel.from_pretrained``.
        model_id: The Hub repo id.
        how_to_fetch: The pre-download instruction for the error (default: the
            ``huggingface-cli download`` command).
        **kwargs: Passed to ``loader``.
    """
    if current_runtime().allows(EXTERNAL):
        return loader(model_id, **kwargs)
    try:
        return loader(model_id, local_files_only=True, **kwargs)
    except OSError as exc:  # HF raises OSError (EnvironmentError) on a cache miss
        fetch = how_to_fetch or f"huggingface-cli download {model_id}"
        raise ModelNotCached(
            f"model {model_id!r} is not in the local cache, and the offline posture "
            f"forbids downloading it. Fetch it once while online: `{fetch}`."
        ) from exc


@contextmanager
def no_download(what: str, *, how_to_fetch: str):
    """Under an offline posture, forbid every outbound connection for the block.

    For model loaders that have no local-only switch (AudioSeal, whisperX): while the
    block runs, a non-loopback ``connect`` raises, and whatever error the library turns
    that into is re-raised as :class:`ModelNotCached` naming ``what`` and
    ``how_to_fetch``. Online it does nothing. The block is process-wide while it runs —
    acceptable because, offline, nothing should be connecting out anyway.
    """
    import socket

    if current_runtime().allows(EXTERNAL):
        yield
        return
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    tripped: list = []

    def _blocked(real):
        def guarded(sock, address):
            host = address[0] if isinstance(address, tuple) else None
            family_unix = getattr(socket, "AF_UNIX", None)
            if host is not None and sock.family != family_unix and not _is_loopback(host):
                tripped.append(address)
                raise ConnectionRefusedError(f"offline: connection to {address!r} blocked")
            return real(sock, address)

        return guarded

    socket.socket.connect = _blocked(real_connect)
    socket.socket.connect_ex = _blocked(real_connect_ex)
    try:
        yield
    except Exception as exc:
        if tripped:
            raise ModelNotCached(
                f"{what} is not on this machine, and the offline posture forbids "
                f"downloading it. Fetch it once while online: {how_to_fetch}"
            ) from exc
        raise
    finally:
        socket.socket.connect, socket.socket.connect_ex = real_connect, real_connect_ex


def _is_loopback(host: str) -> bool:
    import ipaddress

    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def require_local_files(paths: "list[str]", *, what: str, how_to_fetch: str) -> None:
    """Under an offline posture, raise :class:`ModelNotCached` unless every path exists.

    For model files a library downloads itself (PANNs fetches its checkpoint and label
    CSV with ``wget``, even at import), checked before that library is touched.
    """
    from pathlib import Path

    if current_runtime().allows(EXTERNAL):
        return
    missing = [p for p in paths if not Path(p).expanduser().exists()]
    if missing:
        raise ModelNotCached(
            f"{what} needs {missing}, which are not on this machine, and the offline "
            f"posture forbids downloading them. Fetch them once while online: {how_to_fetch}"
        )


def require_egress(data_egress: "str | None", *, what: str) -> None:
    """Raise :class:`EgressBlocked` unless the active runtime allows ``data_egress``.

    Args:
        data_egress: The egress class the call needs (``'local'`` | ``'external'``);
            ``None`` (undeclared) is always refused — callers that read a source's
            declaration map a missing one to ``'external'`` first.
        what: A short description for the error (``"source 'elevenlabs'"``).
    """
    cfg = current_runtime()
    if not cfg.allows(data_egress):
        raise EgressBlocked(
            f"{what} needs data_egress={data_egress!r}, which the current runtime "
            f"forbids (allowed: {sorted(cfg.data_egress_allow)}). It is blocked "
            "because an offline scope is active (foley.offline() or $FOLEY_OFFLINE)."
        )


def current_runtime() -> RuntimeConfig:
    """The active :class:`RuntimeConfig`; outside any scope, the one ``$FOLEY_OFFLINE`` selects."""
    return _CURRENT_RUNTIME.get() or RuntimeConfig.from_env()


def is_offline() -> bool:
    """Whether an offline runtime scope is currently active."""
    return current_runtime().offline


def _redaction_mode(mode: str):
    """Coerce a redaction-mode string to the obs ``RedactionMode`` enum."""
    from .obs.redact import RedactionMode

    return RedactionMode(mode)


@contextmanager
def offline_scope(config: "RuntimeConfig | None" = None):
    """Apply a :class:`RuntimeConfig` for the ``with`` block, restoring obs state on exit.

    Defaults to :meth:`RuntimeConfig.offline_local`. Disables telemetry export and sets
    the redaction mode for the scope; the prior obs enabled-state and redaction mode are
    captured on entry and restored on exit (so a scope never leaks its posture).

    Args:
        config: The posture to apply (default: offline-local).

    Yields:
        The applied :class:`RuntimeConfig`.
    """
    from . import obs
    from .obs import recorder

    cfg = config or RuntimeConfig.offline_local()
    token = _CURRENT_RUNTIME.set(cfg)
    prior_enabled = recorder._CONFIG.enabled
    prior_redaction = recorder._CONFIG.redaction_mode
    prior_force = recorder._CONFIG.force_disabled
    try:
        obs.configure(redaction_mode=_redaction_mode(cfg.redaction_mode))
        if not cfg.telemetry:
            # force_disabled hard-overrides $FOLEY_OBS, so telemetry-off actually holds
            # (obs.disable() alone only clears ``enabled``, which the env var re-ORs in).
            obs.configure(force_disabled=True)
            obs.disable()
        yield cfg
    finally:
        _CURRENT_RUNTIME.reset(token)
        obs.configure(redaction_mode=prior_redaction, force_disabled=prior_force)
        (obs.enable if prior_enabled else obs.disable)()


@contextmanager
def offline(config: "RuntimeConfig | None" = None):
    """Alias of :func:`offline_scope` — ``with foley.offline(): ...`` for local-first runs."""
    with offline_scope(config) as cfg:
        yield cfg
