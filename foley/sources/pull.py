"""``add_from`` — the live-source pull façade (SOURCE → INDEX in one call).

The live analog of :func:`foley.bootstrap.bootstrap`'s per-corpus ingest loop:
resolve a registered live :class:`~foley.sources.base.SourceAdapter`, search it
(with the license filter pushed into the query), gate each hit through the
fail-closed :func:`foley.keep` license check, fetch its (transient) bytes, and run
them through the SAME :func:`foley.index.ingest.ingest_one` pipeline the local and
bulk paths use — so decode / QC / embed / tag / store are **not forked**.

For Freesound this stores every sound BY-REFERENCE (``cache_bytes_ok=False``): the
transient preview bytes are embedded once, then discarded; only the stable URI +
provenance + the CLAP vector persist. The audio is re-fetched on demand via the
adapter (there is no local blob to serve — ``library.audio(id)`` raises for a
remote by-reference sound; that is the contract).
"""

from __future__ import annotations

from typing import Optional

from ..base import IntendedUse
from ..index.ingest import IngestReport, IngestResult, ingest_one
from ..licensing import keep
from .registry import get_source

#: Default intent for a pull: a publishable, commercial, attributable use — the
#: same fail-closed bar :func:`foley.bootstrap.bootstrap`'s Ring-1 filter applies.
DEFAULT_INTENDED_USE = IntendedUse(commercial=True, publish=True, can_attribute=True)


def add_from(
    source: str,
    *,
    query: str,
    license: Optional[str] = "cc0",
    limit: int = 50,
    library=None,
    intended_use: Optional[IntendedUse] = None,
    adapter=None,
    **affordances,
) -> IngestReport:
    """Search a live ``source`` and ingest its license-clean hits into ``library``.

    Progressive disclosure: ``add_from("freesound", query="ocean waves")`` works out
    of the box (CC0-only, into the process-wide default library); every other knob
    is an optional keyword. Each hit is license-gated BEFORE any bytes are fetched
    (fail-closed), then routed through :func:`~foley.index.ingest.ingest_one`, which
    applies the by-reference storage gate from the sound's own license.

    Args:
        source: A registered live-source name (e.g. ``'freesound'``).
        query: The natural-language search query.
        license: License constraint pushed into the source query (default
            ``'cc0'``). The per-item fail-closed guard enforces the source's
            accepted-license allowlist regardless.
        limit: Max candidates to request from the source.
        library: Target :class:`~foley.index.library.SoundLibrary` (default: the
            process-wide default library).
        intended_use: The rights intent each candidate is gated against (default:
            :data:`DEFAULT_INTENDED_USE`).
        adapter: An optional pre-built adapter to use instead of the registry's
            (the dependency-injection seam — a test passes a fake-transport
            adapter; production omits it and the registry lazily builds one).
        **affordances: Extra unified affordances forwarded to the adapter's
            ``search`` (e.g. ``duration_range``, ``sort``).

    Returns:
        An :class:`~foley.index.ingest.IngestReport` — inspect ``.ingested`` for the
        stored records (each ``storage_mode == by_reference`` for Freesound) and
        ``.summary()`` for counts, exactly like :func:`foley.ingest`.
    """
    from ..bootstrap import MetadataCaptioner  # local: avoids a sources<->bootstrap cycle
    from ..index.library import default_library

    lib = library if library is not None else default_library()
    src_adapter = adapter if adapter is not None else get_source(source)["adapter"]
    use = intended_use if intended_use is not None else DEFAULT_INTENDED_USE

    report = IngestReport(root=f"{source}:{query}")
    # A batch-level search failure (rate-limit 429 / 5xx / auth) yields an
    # inspectable report with one error entry, never an unhandled exception.
    try:
        candidates = src_adapter.search(query, license=license, k=limit, **affordances)
    except Exception as exc:
        report.record(IngestResult(id=f"{source}:search", status="error", error=repr(exc)))
        return report

    for cand in candidates:
        rec = cand.sound
        lic = rec.license
        # Fail-closed license gate BEFORE fetching any bytes (report only provenance
        # for a dropped hit) — mirrors bootstrap's COMMERCIAL_USE pre-embed filter.
        if not keep(lic, use):
            report.record(
                IngestResult(
                    id=rec.id,
                    status="skipped_license",
                    notes=[f"dropped: {lic.license_id} not clean for intended use"],
                )
            )
            continue
        # One try guards BOTH the fetch AND the decode/ingest: a hit whose preview
        # 404s, rate-limits, or returns undecodable bytes (HTML error page, truncated
        # audio) is recorded as an error and skipped — one bad hit never aborts the
        # batch (mirrors ingest_folder's per-file resilience). download takes only the
        # source id (the SourceAdapter contract); the adapter resolves its own preview.
        try:
            data = src_adapter.download(lic.source_id)
            res = ingest_one(
                data,
                library=lib,
                sound_id=rec.id,  # canonical short id -> stable-id dedup
                source_uri=rec.uri,  # stable by-reference re-fetch handle
                license=lic,
                captioner=MetadataCaptioner(rec.caption) if rec.caption else None,
                seed_tags=rec.tags,
            )
        except Exception as exc:  # transient fetch/decode failure never aborts the batch
            report.record(IngestResult(id=rec.id, status="error", error=repr(exc)))
            continue
        report.record(res)
    return report
