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


def current_runtime() -> RuntimeConfig:
    """The active :class:`RuntimeConfig`, or the online default outside any scope."""
    return _CURRENT_RUNTIME.get() or RuntimeConfig.default()


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
