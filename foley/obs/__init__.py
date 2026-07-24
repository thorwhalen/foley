"""Observability & the reproducible run-artifact for foley (#11).

The cross-cutting layer that makes foley debuggable, auditable, and re-renderable —
the "snapshots/stories for the SFX layer". Every instrumented operation
(``generate`` / ``add_from`` / ``ingest`` / ``search`` / ``similar`` — and, later, a
#7 ``find()`` / #8 ``weave()`` scope) can emit one :class:`RunManifest`:
simultaneously the debug **trace** (span tree), the reproducible **plan/seed** record,
and the **provenance** record — report 10 §1.3.

**Manifest-first**: the run-artifact is pure stdlib and exists on a bare
``pip install foley``; OpenTelemetry is an *optional mirror* behind the
``foley[obs]`` extra (vendor-neutral GenAI spans for Langfuse/Datadog/…). **Off by
default**: ``import foley`` stays dol-only and a plain façade call is a byte-for-byte
no-op until ``foley.obs.enable()`` / ``$FOLEY_OBS=1`` / ``with foley.obs.run(...)``.
Sensitive prompt/query/narration text is **redacted** (salted content hash) by default.

All four submodules are stdlib-only at import; ``opentelemetry`` loads lazily inside
:class:`~foley.obs.trace.OTelTracer` only, so importing this package is dol-only.
"""

from __future__ import annotations

from .recorder import (
    ObsConfig,
    RunRecorder,
    configure,
    current_run,
    disable,
    enable,
    facade_run,
    is_enabled,
    reset,
    run,
)
from .redact import REDACT_FIELDS, RedactionMode, Redactor, redact_text
from .run_artifact import (
    RunManifest,
    SpanRecord,
    emit_run_manifest,
    ingest_digest,
    load_run,
)
from .trace import GENAI, NoOpTracer, Tracer, get_tracer

__all__ = [
    # run-artifact SSOT
    "RunManifest",
    "SpanRecord",
    "emit_run_manifest",
    "ingest_digest",
    "load_run",
    # recorder / scopes / config
    "run",
    "facade_run",
    "current_run",
    "enable",
    "disable",
    "configure",
    "reset",
    "is_enabled",
    "ObsConfig",
    "RunRecorder",
    # tracer seam
    "get_tracer",
    "Tracer",
    "NoOpTracer",
    "GENAI",
    # redaction
    "redact_text",
    "Redactor",
    "RedactionMode",
    "REDACT_FIELDS",
]
