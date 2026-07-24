"""The reproducible run-artifact SSOT — ``RunManifest`` + ``SpanRecord`` (#11).

Every instrumented foley operation (``generate`` / ``add_from`` / ``ingest`` /
``search`` / ``similar`` — and, later, a #7 ``find()`` / #8 ``weave()`` scope) emits
one :class:`RunManifest`: simultaneously the debug **trace** (the span tree), the
reproducible **plan/seed** record (inputs, params, seeds, chosen clips), and the
**provenance** record (credits + disclosure refs) — report 10 §1.3. It is the join
that makes foley debuggable, evaluable, and reproducible; #8's
``SoundDesignTimeline.run_manifest_ref`` will point at :attr:`RunManifest.run_id`.

Pure data: both dataclasses subclass :class:`~foley.base.SerializableMixin`, so
``to_dict`` / ``to_json`` / ``from_dict`` (incl. ``spans`` rehydrating element-wise to
:class:`SpanRecord`, exactly like ``IngestReport.results``) come for free, and adding
fields later (token usage, cost, timings for #7) is schema-safe with no
``SCHEMA_VERSION`` bump. The manifest **composes** the existing shapes — it embeds
``IngestReport.to_dict()`` and ``Credits.manifest`` and references ``Candidate`` ids +
``LicenseRecord`` generation fields — it never forks them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import MutableMapping, Optional

from ..base import SCHEMA_VERSION, SerializableMixin


@dataclass
class SpanRecord(SerializableMixin):
    """One node of the run's span tree (the trace half of the artifact).

    Built by the recorder from its own clock + id-factory, independent of any tracer,
    so the tree is complete even when the OTel mirror is a total no-op.
    """

    name: str
    span_id: str
    parent_id: Optional[str] = None
    kind: Optional[str] = None  # 'CLIENT' | 'INTERNAL'
    start_ms: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "ok"  # 'ok' | 'error'
    attributes: dict = field(default_factory=dict)  # gen_ai.* + foley.* (REDACTED)
    events: list = field(default_factory=list)  # redacted content events (reserved for #7)
    error: Optional[str] = None


@dataclass
class RunManifest(SerializableMixin):
    """The reproducible run-artifact for one foley operation (trace ⊕ plan ⊕ provenance).

    Persisted by :func:`emit_run_manifest` into a run store keyed by :attr:`run_id`.
    Sensitive prompt/query text lives redacted (see :mod:`foley.obs.redact`); chosen
    clips are held by reference (``SoundRecord`` id) so the manifest stays light and a
    trace can be replayed against a fresh index.
    """

    run_id: str  # uuid4 hex — store key + the #8 SoundDesignTimeline.run_manifest_ref target
    op: str  # 'generate'|'add_from'|'ingest'|'search'|'similar' (+ 'find'/'run' when aggregated)
    created_at: Optional[str] = None  # ISO-8601; None in deterministic/test mode
    foley_version: Optional[str] = None
    inputs: dict = field(default_factory=dict)  # REDACTED request (query/prompt via REDACT_FIELDS)
    params: dict = field(default_factory=dict)  # resolved-effective kwargs (open-closed)
    spans: "list[SpanRecord]" = field(default_factory=list)  # THE TRACE (rehydrated via _decode)
    steps: list = field(default_factory=list)  # RESERVED for #7 decompose/verify/decide + branch
    ingest_report: Optional[dict] = None  # IngestReport.to_dict() — embeds, never forks
    result_ids: list = field(default_factory=list)  # produced/returned SoundRecord ids
    candidate_scores: list = field(default_factory=list)  # [{id,clap,bm25,rrf,rerank}]
    credits_ref: Optional[dict] = None  # credits_for(records).manifest (TASL + disclosure)
    disclosure_refs: dict = field(default_factory=dict)  # {id:{watermark,c2pa_manifest_ref,...}}
    seeds: dict = field(default_factory=dict)  # {id:{backend,model,version,prompt(REDACTED),seed,...}}
    plan_ref: Optional[dict] = None  # RESERVED for #8 SoundDesignTimeline / OTIO plan
    trace_ref: Optional[str] = None  # OTel trace id hex — ONLY when a recording SDK is configured
    status: str = "ok"
    error: Optional[str] = None
    schema_version: int = SCHEMA_VERSION


def emit_run_manifest(
    store: MutableMapping, manifest: RunManifest, *, redactor=None
) -> str:
    """Serialize ``manifest`` (redacting the payload) and write it to ``store``.

    The plain-dict write path keeps an emit-time interposition point for the
    belt-and-suspenders redaction sweep (do NOT couple the write to
    auto-serialization). Returns the ``run_id``.

    Args:
        store: A ``MutableMapping[str, dict]`` (default:
            :func:`foley.stores.make_run_store`; a dict in tests).
        manifest: The :class:`RunManifest` to persist.
        redactor: An optional :class:`~foley.obs.redact.Redactor` applied to the full
            payload before the write (the emit-time net).
    """
    payload = manifest.to_dict()
    if redactor is not None:
        payload = redactor.redact_manifest(payload)
    store[manifest.run_id] = payload
    return manifest.run_id


def load_run(store: MutableMapping, run_id: str) -> RunManifest:
    """Load and typed-rehydrate a :class:`RunManifest` from ``store`` (the read helper)."""
    return RunManifest.from_dict(store[run_id])


def ingest_digest(report) -> dict:
    """A leak-free digest of an :class:`~foley.index.ingest.IngestReport` for a manifest.

    Records the per-clip **outcomes** (id, status, QC status, notes) + summary counts —
    NOT the full ``SoundRecord``\\ s. The records carry ``caption`` (which equals the
    raw generation prompt for a generated clip) + ``tags`` and already live in the meta
    store keyed by the id referenced in ``result_ids``, so embedding them would both
    leak prompt text into the manifest and duplicate data. Duck-typed over the report
    (``.summary()`` + ``.results``) to avoid an obs → index import coupling.
    """
    return {
        "summary": report.summary(),
        "results": [
            {
                "id": r.id,
                "status": r.status,
                "qc": (r.qc.get("status") if r.qc else None),
                "notes": list(r.notes),
            }
            for r in report.results
        ],
    }
