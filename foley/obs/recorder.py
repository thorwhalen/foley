"""The run-recorder: owns the manifest, drives the OTel mirror, off by default (#11).

This is where the manifest-first design lives. A :class:`RunRecorder` builds the
:class:`~foley.obs.run_artifact.RunManifest` + its span tree from its own clock +
id-factory — **independent of the tracer** — so the artifact is complete with a total
no-op tracer. The façades reach it through :func:`facade_run` (a get-or-create,
off-by-default context manager) and :func:`current_run`; a #7 ``find()`` opens an
explicit :func:`run` scope so nested façade calls aggregate into **one** manifest.

Discipline (mirroring the rest of foley): **off by default** — a plain
``import foley`` + a plain ``foley.generate(...)`` is a byte-for-byte no-op that
touches no store and stays dol-only. ``foley.obs.enable()`` / ``$FOLEY_OBS=1`` /
``with foley.obs.run(...)`` turn it on. Emitting a manifest needs NO extra (all
stdlib); only the OTel span mirror needs ``foley[obs]``. Recording never raises into a
façade — a store-write failure degrades gracefully.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from contextvars import ContextVar
from typing import Callable, MutableMapping, Optional

from .redact import RedactionMode, Redactor
from .run_artifact import RunManifest, SpanRecord, emit_run_manifest
from .trace import GENAI, Tracer, get_tracer


# ---------------------------------------------------------------------------
# process-wide config + the current-run ContextVar
# ---------------------------------------------------------------------------


def _iso_now() -> Optional[str]:
    """ISO-8601 UTC timestamp (real wall-clock; overridden to ``None`` in tests)."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@dataclass
class ObsConfig:
    """Process-wide observability configuration (flipped by :func:`enable`/:func:`disable`)."""

    enabled: bool = False
    redaction_mode: RedactionMode = RedactionMode.hash
    salt: str = "foley-obs-v1"
    prefer_otel: bool = True
    run_store: Optional[MutableMapping] = None  # default: lazily make_run_store()
    tracer: Optional[Tracer] = None  # default: lazily get_tracer(prefer_otel)
    clock: Callable[[], float] = time.time
    id_factory: Callable[[], str] = field(default=lambda: uuid.uuid4().hex)
    now: Callable[[], Optional[str]] = _iso_now


_CONFIG = ObsConfig()
_CURRENT_RUN: "ContextVar[Optional[RunRecorder]]" = ContextVar(
    "foley_run", default=None
)


def is_enabled() -> bool:
    """Whether observability is on (via :func:`enable` or ``$FOLEY_OBS`` in {1,true,yes})."""
    return _CONFIG.enabled or os.environ.get("FOLEY_OBS", "").lower() in (
        "1",
        "true",
        "yes",
    )


def enable(**overrides) -> None:
    """Turn observability on process-wide (and apply any :class:`ObsConfig` overrides)."""
    _apply(overrides)
    _CONFIG.enabled = True


def disable() -> None:
    """Turn observability off process-wide (façades revert to a byte-for-byte no-op)."""
    _CONFIG.enabled = False


def configure(**overrides) -> None:
    """Apply :class:`ObsConfig` overrides WITHOUT flipping ``enabled`` (the test-injection seam)."""
    _apply(overrides)


def reset() -> None:
    """Restore the default config (test teardown; clears injected store/tracer/clock)."""
    global _CONFIG
    _CONFIG = ObsConfig()


def _apply(overrides: dict) -> None:
    for k, v in overrides.items():
        if not hasattr(_CONFIG, k):
            raise ValueError(f"unknown obs config field {k!r}")
        setattr(_CONFIG, k, v)


_DEFAULT_STORE: "Optional[MutableMapping]" = None


def _default_store() -> MutableMapping:
    """The process-wide default run store (lazily built under FOLEY_DATA_DIR/runs)."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        from ..stores import make_run_store

        _DEFAULT_STORE = make_run_store()
    return _DEFAULT_STORE


def _foley_version() -> str:
    try:
        from importlib.metadata import version

        return version("foley")
    except Exception:  # pragma: no cover
        return "unknown"


# ---------------------------------------------------------------------------
# span handle + recorder
# ---------------------------------------------------------------------------


class _SpanHandle:
    """Yielded inside ``recorder.span(...)``; fans ``set_attribute`` to the record + mirror."""

    def __init__(self, record: SpanRecord, mirror, redactor: Redactor):
        self._record = record
        self._mirror = mirror
        self._redactor = redactor

    def set_attribute(self, key: str, value) -> None:
        """Set a (redacted) attribute on both the manifest span record and the OTel mirror."""
        redacted = self._redactor.redact_value(key, value)
        self._record.attributes[key] = redacted
        self._mirror.set_attribute(
            key,
            redacted
            if isinstance(redacted, (str, bool, int, float))
            else str(redacted),
        )


class RunRecorder:
    """Builds one :class:`RunManifest` (span tree + composed shapes), tracer-independent."""

    def __init__(
        self,
        manifest: RunManifest,
        *,
        tracer: Tracer,
        redactor: Redactor,
        run_store: MutableMapping,
        clock: Callable[[], float],
        id_factory: Callable[[], str],
    ):
        self.manifest = manifest
        self._tracer = tracer
        self._redactor = redactor
        self._run_store = run_store
        self._clock = clock
        self._id_factory = id_factory
        self._stack: "list[SpanRecord]" = []

    @contextmanager
    def span(self, name: str, *, kind: Optional[str] = None, **attributes):
        """Open a span: append a :class:`SpanRecord` (from our own clock/ids) + mirror it."""
        start_ms = self._clock() * 1000.0
        rec = SpanRecord(
            name=name,
            span_id=self._id_factory(),
            parent_id=self._stack[-1].span_id if self._stack else None,
            kind=kind,
            start_ms=start_ms,
            attributes=self._redactor.redact_attrs(attributes),
        )
        self.manifest.spans.append(rec)
        self._stack.append(rec)
        try:
            with self._tracer.start_as_current_span(
                name, kind=kind, attributes=rec.attributes
            ) as mirror:
                if self.manifest.trace_ref is None and getattr(
                    mirror, "trace_id", None
                ):
                    self.manifest.trace_ref = mirror.trace_id
                try:
                    yield _SpanHandle(rec, mirror, self._redactor)
                    mirror.set_status(True)
                except BaseException as exc:
                    # An exception message can echo the raw prompt/narration, so store
                    # only a redacted form (the type name, unless mode='full') and set
                    # the semconv-correct error.type (the class name) — never the raw
                    # repr. record_exception (message + stacktrace) runs only in 'full'.
                    rec.status = "error"
                    rec.error = self._redactor.redact_error(exc)
                    error_type = type(exc).__name__
                    rec.attributes[GENAI["error_type"]] = error_type
                    mirror.set_attribute(GENAI["error_type"], error_type)
                    mirror.set_status(False, rec.error)
                    if self._redactor.mode == RedactionMode.full:
                        mirror.record_exception(exc)
                    raise
        finally:
            rec.duration_ms = self._clock() * 1000.0 - start_ms
            self._stack.pop()

    # -- manifest setters (mutate; never raise) -----------------------------

    def set_inputs(self, **inputs) -> None:
        self.manifest.inputs.update(self._redactor.redact_attrs(inputs))

    def set_params(self, **params) -> None:
        self.manifest.params.update(params)

    def add_result_ids(self, ids) -> None:
        self.manifest.result_ids.extend(ids)

    def add_candidate_scores(self, scores) -> None:
        self.manifest.candidate_scores.extend(scores)

    def set_ingest_report(self, report_dict) -> None:
        self.manifest.ingest_report = report_dict

    def set_credits_ref(self, credits_manifest) -> None:
        self.manifest.credits_ref = credits_manifest

    def add_seed(self, sound_id: str, seed: dict) -> None:
        self.manifest.seeds[sound_id] = self._redactor.redact_attrs(seed)

    def add_disclosure_ref(self, sound_id: str, ref: dict) -> None:
        self.manifest.disclosure_refs[sound_id] = ref

    def set_status(self, status: str) -> None:
        self.manifest.status = status

    def set_error(self, message: str) -> None:
        self.manifest.status = "error"
        self.manifest.error = message

    def emit(self) -> None:
        """Persist the manifest to the run store — swallowing any write failure."""
        try:
            emit_run_manifest(self._run_store, self.manifest, redactor=self._redactor)
        except Exception as exc:  # noqa: BLE001 - obs must never break the façade
            self.manifest.error = f"run-manifest emit failed: {exc!r}"


# ---------------------------------------------------------------------------
# null run — the true zero-cost no-op yielded when obs is off
# ---------------------------------------------------------------------------


class _NullSpanHandle:
    def set_attribute(self, key: str, value) -> None:  # noqa: D102
        pass


_NULL_SPAN_HANDLE = _NullSpanHandle()


class _NullRun:
    """Yielded by :func:`facade_run` / :func:`current_run` when obs is off — all no-ops."""

    @contextmanager
    def span(self, name: str, *, kind: Optional[str] = None, **attributes):
        yield _NULL_SPAN_HANDLE

    def set_inputs(self, **inputs) -> None: ...
    def set_params(self, **params) -> None: ...
    def add_result_ids(self, ids) -> None: ...
    def add_candidate_scores(self, scores) -> None: ...
    def set_ingest_report(self, report_dict) -> None: ...
    def set_credits_ref(self, credits_manifest) -> None: ...
    def add_seed(self, sound_id: str, seed: dict) -> None: ...
    def add_disclosure_ref(self, sound_id: str, ref: dict) -> None: ...
    def set_status(self, status: str) -> None: ...
    def set_error(self, message: str) -> None: ...


_NULL_RUN = _NullRun()


# ---------------------------------------------------------------------------
# run scopes
# ---------------------------------------------------------------------------


def _new_recorder(op: str, *, inputs, params, config: ObsConfig) -> RunRecorder:
    redactor = Redactor(mode=config.redaction_mode, salt=config.salt)
    tracer = (
        config.tracer
        if config.tracer is not None
        else get_tracer(prefer_otel=config.prefer_otel)
    )
    store = config.run_store if config.run_store is not None else _default_store()
    manifest = RunManifest(
        run_id=config.id_factory(),
        op=op,
        created_at=config.now(),
        foley_version=_foley_version(),
        inputs=redactor.redact_attrs(inputs or {}),
        params=params or {},
    )
    return RunRecorder(
        manifest,
        tracer=tracer,
        redactor=redactor,
        run_store=store,
        clock=config.clock,
        id_factory=config.id_factory,
    )


@contextmanager
def _open_run(op: str, *, inputs, params, config: ObsConfig):
    recorder = _new_recorder(op, inputs=inputs, params=params, config=config)
    token = _CURRENT_RUN.set(recorder)
    try:
        with recorder.span("foley." + op):
            yield recorder
    except BaseException as exc:
        # Redacted (type name unless mode='full') — a raw message can echo the prompt.
        recorder.set_error(recorder._redactor.redact_error(exc))
        raise
    finally:
        _CURRENT_RUN.reset(token)
        recorder.emit()


@contextmanager
def facade_run(op: str, *, inputs=None, params=None):
    """The get-or-create seam every façade wraps its body in.

    Nested (a run is already active) → a child span into the SAME manifest, no emit
    (the outer owner emits). Enabled + top-level → a new recorder that emits one
    manifest on exit. Disabled → the zero-cost :data:`_NULL_RUN`.
    """
    active = _CURRENT_RUN.get()
    if active is not None:
        with active.span(op):
            yield active
        return
    if not is_enabled():
        yield _NULL_RUN
        return
    with _open_run(op, inputs=inputs, params=params, config=_CONFIG) as rec:
        yield rec


def current_run():
    """The active :class:`RunRecorder`, or :data:`_NULL_RUN` (for the shared child span)."""
    return _CURRENT_RUN.get() or _NULL_RUN


@contextmanager
def run(op: str = "run", *, inputs=None, params=None, **overrides):
    """Open an explicit run scope that aggregates nested façade calls into ONE manifest.

    Forces observability on for the scope (even if globally disabled) — the #7
    ``find()`` aggregation entrypoint, shipped now as skeleton. Get-or-create: a nested
    :func:`run` reuses the active recorder. ``overrides`` are per-scope
    :class:`ObsConfig` fields (e.g. ``run_store``, ``prefer_otel``, ``clock``).
    """
    active = _CURRENT_RUN.get()
    if active is not None:
        with active.span(op):
            yield active
        return
    config = replace(_CONFIG, **overrides) if overrides else _CONFIG
    with _open_run(op, inputs=inputs, params=params, config=config) as rec:
        yield rec
