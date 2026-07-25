"""The MCP surface — foley's façade as agent-callable tools (py2mcp, #12, report 05/10).

Exposes the SELECT→preview→WEAVE loop to an LLM agent (or any MCP client) as a set of
**JSON-safe** tools built with ``py2mcp`` (``mk_mcp_server`` over stdio). The single rule:
tools take/return only JSON (ids, scores, license summaries, timeline dicts, store keys) —
**never** a :class:`~foley.base.Candidate`, a :class:`~foley.weave.WeaveResult`, or numpy
audio. Heavy objects stay server-side; audio is referenced by a byte-store key.

The tool functions are thin wrappers over the existing façade (a single seam, three
surfaces: Python / CLI / MCP): they resolve the shared :class:`foley.index.SoundLibrary`
and per-session :class:`foley.agent.session.SessionStore` (both injectable for tests).
``py2mcp`` / ``fastmcp`` are imported LAZILY inside :func:`build_mcp_server` only, so
``import foley`` and ``import foley.agent`` stay dol-only.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# injectable shared state (a default library + session factory; overridden in tests)
# ---------------------------------------------------------------------------

_STATE: dict = {
    "library": None,
    "session_factory": None,
    "byte_store": None,
    "runtime": None,
}


def _configure(*, library=None, session_factory=None, byte_store=None, runtime=None):
    """Set the shared library / session-factory / byte-store / runtime (test + server seam)."""
    for key, val in (
        ("library", library),
        ("session_factory", session_factory),
        ("byte_store", byte_store),
        ("runtime", runtime),
    ):
        if val is not None:
            _STATE[key] = val


def _lib():
    if _STATE["library"] is not None:
        return _STATE["library"]
    from ..index.library import default_library

    return default_library()


def _session(session_id: str):
    if _STATE["session_factory"] is not None:
        return _STATE["session_factory"](session_id)
    from .session import SessionStore

    return SessionStore(session_id)


def _byte_store():
    if _STATE["byte_store"] is not None:
        return _STATE["byte_store"]
    from ..stores import make_byte_store

    _STATE["byte_store"] = make_byte_store()
    return _STATE["byte_store"]


def _runtime():
    if _STATE["runtime"] is not None:
        return _STATE["runtime"]
    from ..runtime import current_runtime

    return current_runtime()


# ---------------------------------------------------------------------------
# JSON-safe projections (compact — never the leaky full to_dict())
# ---------------------------------------------------------------------------


def _enum(x):
    return x.value if hasattr(x, "value") else x


def _license_summary(lic) -> dict:
    """A compact, JSON-safe license summary (the fields an agent needs to decide)."""
    return {
        "license_id": getattr(lic, "license_id", None),
        "commercial_ok": getattr(lic, "commercial_ok", None),
        "requires_attribution": getattr(lic, "requires_attribution", None),
        "attribution_text": getattr(lic, "attribution_text", None),
        "redistribute_standalone_ok": getattr(lic, "redistribute_standalone_ok", None),
        "is_ai_generated": getattr(lic, "is_ai_generated", None),
    }


def _candidate_row(c) -> dict:
    """Project a :class:`~foley.base.Candidate` to a compact JSON row.

    Deliberately omits the leaky internals (``storage_mode`` / ``uri`` / QC block /
    embeddings) — only what an agent needs to audition and decide.
    """
    s = c.sound
    verdict = None
    if c.verdict is not None:
        verdict = {
            "match": getattr(c.verdict, "match", None),
            "confidence": getattr(c.verdict, "confidence", None),
            "level": _enum(getattr(c.verdict, "level", None)),
        }
    return {
        "id": s.id,
        "caption": s.caption,
        "tags": list(s.tags or []),
        "duration_s": s.duration_s,
        "ucs_category": s.ucs_category,
        "origin": _enum(c.origin),
        "scores": {
            "clap": c.clap_score,
            "bm25": c.bm25_score,
            "rrf": c.rrf_score,
            "rerank": c.rerank_score,
        },
        "verdict": verdict,
        "license": _license_summary(s.license),
        "license_ok": c.license_ok,
        "preview_uri": c.preview_uri,
    }


def _weave_result_row(result) -> dict:
    """Project a :class:`~foley.weave.WeaveResult` to JSON: audio by store key, no ndarray."""
    audio_ref = None
    try:
        from ..audio import encode
        from ..stores import content_key

        data = encode(result.audio, result.sr, fmt="flac")
        audio_ref = content_key(data)
        _byte_store()[audio_ref] = data
    except Exception:
        audio_ref = None
    credits = getattr(result.credits, "entries", ())
    return {
        "audio_ref": audio_ref,
        "sr": result.sr,
        "timeline": result.timeline.to_dict(),
        "credits": [e.to_dict() if hasattr(e, "to_dict") else e for e in list(credits)],
        "captions_vtt": result.captions_vtt,
        "captions_srt": result.captions_srt,
        "master_report": result.master_report,
        "watermark": result.watermark,
        "content_credential": result.content_credential,
        "run_manifest_ref": result.run_manifest_ref,
    }


# ---------------------------------------------------------------------------
# the tools (module-level, JSON in/out) — the MCP surface
# ---------------------------------------------------------------------------


def foley_find(
    context: str,
    max_events: int = 6,
    verify: str = "listen",
    commercial_ok: bool = False,
    k: int = 10,
    session: str = "default",
) -> list:
    """Find verified, license-clean sound candidates for a narrative passage.

    Caches the full candidates in the session so ``foley_plan`` / ``foley_weave`` can
    rehydrate them by id. Returns compact candidate rows.
    """
    from .. import find
    from ..base import IntendedUse

    cands = list(
        find(
            context,
            max_events=max_events,
            verify=verify,
            k=k,
            intended_use=IntendedUse(commercial=commercial_ok),
            library=_lib(),
        )
    )
    _session(session).cache_candidates(cands)
    return [_candidate_row(c) for c in cands]


def foley_search(
    query: str,
    k: int = 10,
    commercial_ok: bool = False,
    ucs_category: Optional[str] = None,
    rerank: bool = False,
    session: str = "default",
) -> list:
    """Hybrid (CLAP + keyword) search of the library for a text query; returns candidate rows."""
    hits = _lib().search(
        query,
        k=k,
        commercial_ok=commercial_ok or None,
        ucs_category=ucs_category,
        rerank=rerank,
    )
    _session(session).cache_candidates(hits)
    return [_candidate_row(c) for c in hits]


def foley_similar_to(sound_id: str, k: int = 10, session: str = "default") -> list:
    """ "More like this" — the library neighbours of a sound (by id); returns candidate rows."""
    from .preview import similar_to

    hits = similar_to(sound_id, k=k, library=_lib())
    _session(session).cache_candidates(hits)
    return [_candidate_row(c) for c in hits]


def foley_preview(sound_id: str, seconds: int = 6, session: str = "default") -> dict:
    """Produce a short audition of a sound; returns its store key (never audio bytes)."""
    from .preview import preview

    cand = preview(sound_id, seconds=seconds, library=_lib(), byte_store=_byte_store())
    return {
        "sound_id": sound_id,
        "preview_uri": cand.preview_uri,
        "duration_s": cand.sound.duration_s,
        "caption": cand.sound.caption,
    }


def foley_refine(
    session: str = "default",
    query: Optional[str] = None,
    picked_ids: Optional[list] = None,
    rejected_ids: Optional[list] = None,
    hint: Optional[str] = None,
    k: int = 10,
) -> dict:
    """Relevance-feedback refinement: expand the query, boost picks, drop rejects, re-rank."""
    from .preview import refine

    sess = _session(session)
    res = refine(
        sess,
        query=query,
        picked_ids=tuple(picked_ids or ()),
        rejected_ids=tuple(rejected_ids or ()),
        hint=hint,
        k=k,
        library=_lib(),
    )
    sess.cache_candidates(res.results)
    return {"queries": res.queries, "results": [_candidate_row(c) for c in res.results]}


def foley_pick(
    sound_id: str,
    session: str = "default",
    layer: Optional[str] = None,
    onset: Optional[float] = None,
) -> dict:
    """Accept a sound into the session (persisted); ``foley_plan`` folds picks into a timeline."""
    n = _session(session).add_pick(sound_id, layer=layer, onset=onset)
    return {"ok": True, "sound_id": sound_id, "n_picks": n}


def foley_drop_pick(sound_id: str, session: str = "default") -> dict:
    """Remove a previously-picked sound from the session."""
    n = _session(session).drop_pick(sound_id)
    return {"ok": True, "sound_id": sound_id, "n_picks": n}


def foley_reject(
    sound_id: str, session: str = "default", reason: Optional[str] = None
) -> dict:
    """Reject a sound (feeds ``foley_refine`` relevance feedback)."""
    n = _session(session).add_reject(sound_id, reason=reason)
    return {"ok": True, "sound_id": sound_id, "n_rejects": n}


def foley_list_picks(session: str = "default") -> list:
    """The sounds picked in this session (the 'persist picks' read side)."""
    return _session(session).list_picks()


def foley_generate(
    prompt: str,
    backend: str = "stable_audio",
    commercial_ok: bool = False,
    session: str = "default",
) -> dict:
    """Generate a sound from a text prompt (local backends only when offline)."""
    from ..runtime import EXTERNAL, LOCAL
    from ..sources.registry import source_egress

    egress = source_egress(backend) or LOCAL
    if _runtime().offline and egress == EXTERNAL:
        return {
            "ok": False,
            "error": f"backend {backend!r} is external and disallowed in offline mode",
        }
    from .. import GenerationError, generate

    # The public façade returns the stored Candidate (a re-searchable, by-value
    # SoundRecord) and RAISES GenerationError on any non-success outcome (QC-quarantined,
    # rights-blocked, safety-refused, or an empty result). Surface both as JSON so the
    # agent gets the real generated id on success — and a structured error, never an
    # escaping exception, on failure — honoring the module's JSON-in/JSON-out contract.
    try:
        cand = generate(prompt, backend=backend, library=_lib())
    except GenerationError as exc:
        return {
            "ok": False,
            "status": getattr(exc, "status", None),
            "error": str(exc),
            "backend": backend,
        }
    return {"ok": True, "sound_ids": [cand.sound.id], "backend": backend}


def foley_plan(
    session: str = "default",
    transcript: Optional[str] = None,
    candidate_ids: Optional[list] = None,
) -> dict:
    """Fold picks (or explicit candidate ids) into a JSON sound-design timeline.

    Each pick's explicit ``layer`` / ``onset`` (set via :func:`foley_pick`) is overlaid
    onto its candidate's :class:`~foley.base.SoundEvent` so ``plan`` honors the agent's
    placement choices — a numeric ``onset`` becomes an absolute-seconds anchor (see
    :func:`foley.weave.anchor.parse_symbolic_anchor`).
    """
    from .. import plan
    from ..base import Layer, SoundEvent

    sess = _session(session)
    ids = candidate_ids if candidate_ids is not None else sess.picked_ids()
    cands = sess.rehydrate(ids)
    for c in cands:
        sid = getattr(getattr(c, "sound", None), "id", None)
        pick = sess.picks.get(sid) if sid is not None else None
        if not pick:
            continue
        layer, onset = pick.get("layer"), pick.get("onset")
        if layer is None and onset is None:
            continue
        if c.event is None:
            c.event = SoundEvent(query=c.sound.caption or "", audioset=[])
        if layer is not None:
            c.event.layer = Layer(layer)
        if onset is not None:
            c.event.onset = str(onset)  # numeric → absolute-seconds anchor in WEAVE
    return plan(cands, transcript=transcript).to_dict()


def foley_weave(narration: str, timeline: dict, session: str = "default") -> dict:
    """Render a timeline under the narration; returns the mix by store key + captions + credits."""
    from .. import weave as _weave
    from ..base import SoundDesignTimeline

    result = _weave(narration, SoundDesignTimeline.from_dict(timeline), library=_lib())
    return _weave_result_row(result)


def _tl_op(op, timeline: dict, *args) -> dict:
    from ..base import SoundDesignTimeline

    return op(SoundDesignTimeline.from_dict(timeline), *args).to_dict()


def foley_swap_clip(timeline: dict, item_id: str, sound_id: str) -> dict:
    """Swap a timeline item's clip; returns the new timeline."""
    from ..weave.timeline import swap_clip

    return _tl_op(swap_clip, timeline, item_id, sound_id)


def foley_set_gain(timeline: dict, item_id: str, gain_db: float) -> dict:
    """Set a timeline item's gain (dB); returns the new timeline."""
    from ..weave.timeline import set_gain

    return _tl_op(set_gain, timeline, item_id, gain_db)


def foley_nudge(timeline: dict, item_id: str, delta_s: float) -> dict:
    """Shift a timeline item's onset by ``delta_s`` seconds; returns the new timeline."""
    from ..weave.timeline import nudge

    return _tl_op(nudge, timeline, item_id, delta_s)


def foley_toggle(timeline: dict, item_id: str, enabled: bool) -> dict:
    """Mute/unmute a timeline item; returns the new timeline."""
    from ..weave.timeline import toggle

    return _tl_op(toggle, timeline, item_id, enabled)


def foley_set_master(
    timeline: dict,
    target_lufs: Optional[float] = None,
    peak_dbfs: Optional[float] = None,
) -> dict:
    """Set the timeline's master target (LUFS / true-peak); returns the new timeline.

    Either field may be set independently — omitting one keeps the podcast default for
    that field (so ``peak_dbfs=-2.0`` alone tightens only the true-peak ceiling).
    """
    from ..base import MasterProfile, SoundDesignTimeline
    from ..weave.timeline import set_master

    if target_lufs is None and peak_dbfs is None:
        profile = "podcast"
    else:
        profile = MasterProfile(
            target_lufs=target_lufs if target_lufs is not None else -16.0,
            true_peak_db=peak_dbfs if peak_dbfs is not None else -1.0,
        )
    return set_master(SoundDesignTimeline.from_dict(timeline), profile).to_dict()


def foley_timeline_captions(timeline: dict, fmt: str = "vtt") -> dict:
    """Export SDH captions for a timeline (``fmt='vtt'`` | ``'srt'``)."""
    from ..base import SoundDesignTimeline
    from ..weave.timeline import to_srt, to_webvtt

    tl = SoundDesignTimeline.from_dict(timeline)
    return {"vtt": to_webvtt(tl)} if fmt == "vtt" else {"srt": to_srt(tl)}


def foley_capabilities() -> dict:
    """What foley can do here — keys / extras / system deps / offline / sources / degraded."""
    from ..requirements import capability_report

    return capability_report(runtime=_runtime())


def foley_status(session: str = "default") -> dict:
    """The current runtime posture + this session's pick/reject counts."""
    from ..obs import is_enabled
    from ..obs import recorder as _obs_recorder
    from ..sources.registry import list_sources

    cfg = _runtime()
    sess = _session(session)
    return {
        "offline": cfg.offline,
        "sources": list_sources(egress_allow=cfg.data_egress_allow),
        "telemetry_enabled": bool(is_enabled()),
        # The *effective* recorder redaction mode (not the aspirational RuntimeConfig
        # value), so status can never affirmatively misstate the real posture.
        "redaction_mode": _enum(_obs_recorder._CONFIG.redaction_mode),
        "n_picks": len(sess.list_picks()),
        "n_rejects": len(sess.list_rejects()),
    }


#: The full JSON-safe tool surface (SSOT), in a stable order.
TOOLS = [
    foley_find,
    foley_search,
    foley_similar_to,
    foley_preview,
    foley_refine,
    foley_pick,
    foley_drop_pick,
    foley_reject,
    foley_list_picks,
    foley_generate,
    foley_plan,
    foley_weave,
    foley_swap_clip,
    foley_set_gain,
    foley_nudge,
    foley_toggle,
    foley_set_master,
    foley_timeline_captions,
    foley_capabilities,
    foley_status,
]


def _resolve_tools(*, include: "Optional[list[str]]" = None) -> list:
    """The tool list, optionally subset by name (``include``)."""
    if include is None:
        return list(TOOLS)
    by_name = {fn.__name__: fn for fn in TOOLS}
    return [by_name[n] for n in include if n in by_name]


def build_mcp_server(
    *,
    library=None,
    session: str = "default",
    runtime=None,
    byte_store=None,
    include: "Optional[list[str]]" = None,
    name: str = "foley",
):
    """Build the foley MCP server (lazy ``py2mcp``); registers the JSON-safe tool surface.

    Validates that every source declares a ``data_egress`` (fail-closed), binds the
    injectable library / runtime / byte-store, and hands the resolved tool functions to
    ``py2mcp.mk_mcp_server``. Never starts a server or touches the network.

    Args:
        library: The :class:`foley.index.SoundLibrary` (default: the shared one).
        session: The default session id.
        runtime: A :class:`foley.runtime.RuntimeConfig` (default: the active one).
        byte_store: A ``MutableMapping[str, bytes]`` for previews / rendered mixes.
        include: Optional subset of tool names to expose.
        name: The MCP server name.

    Returns:
        A ``fastmcp.FastMCP`` server.
    """
    from ..sources.registry import _validate_egress

    _validate_egress()
    _configure(library=library, runtime=runtime, byte_store=byte_store)
    _STATE["default_session"] = session
    from py2mcp import mk_mcp_server  # lazy: foley[mcp]

    return mk_mcp_server(_resolve_tools(include=include), name=name)


def _run_server(server, runtime) -> None:
    """Run ``server`` under the runtime's obs posture (offline → telemetry hard-off).

    Factored out of :func:`serve` so the offline-posture enforcement is unit-testable
    without a blocking stdio loop: when ``runtime`` is a telemetry-off (offline) posture,
    the whole serve loop runs inside :func:`foley.runtime.offline_scope`, so the
    ``--offline`` promise of "no telemetry" is actually enforced for the server's
    lifetime (with :func:`foley.obs.recorder.run` now honoring ``force_disabled``, this
    silences the ``find`` / ``weave`` paths too, not only the ``facade_run`` ones).
    """
    if runtime is not None and not runtime.telemetry:
        from ..runtime import offline_scope

        with offline_scope(runtime):
            server.run()
    else:
        server.run()


def serve(
    *, name: str = "foley", runtime=None, **kwargs
) -> None:  # pragma: no cover - blocking I/O
    """Build and run the foley MCP server over stdio (blocks); enforces an offline posture."""
    _run_server(build_mcp_server(name=name, runtime=runtime, **kwargs), runtime)


def _cli(argv: "Optional[list[str]]" = None) -> int:  # pragma: no cover - entry point
    """``foley-mcp`` console entry: serve foley over MCP (stdio)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="foley-mcp", description="Serve foley to agents over MCP (stdio)."
    )
    parser.add_argument("--name", default="foley")
    parser.add_argument("--session", default="default")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="local-first: no external sources / telemetry",
    )
    args = parser.parse_args(argv)
    runtime = None
    if args.offline:
        from ..runtime import RuntimeConfig

        runtime = RuntimeConfig.offline_local()
    serve(name=args.name, session=args.session, runtime=runtime)
    return 0
