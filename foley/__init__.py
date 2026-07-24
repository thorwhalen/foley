"""foley — a retrieval-first façade for sound effects.

foley finds (or generates) the right sound effect for a moment of narration and
weaves it in. It is the SFX sibling of ``arioso`` (a unified façade over AI
music-generation backends): one simple surface over many sound *sources* (a
bring-your-own library, service APIs like Freesound, and generative-AI models),
a searchable *index* of every sound (by keyword *and* meaning, via CLAP
embeddings + hybrid search), an *agent* that selects the right sound for a
narrative context, and a *compositor* that places it under the voice.

Four stages::

    SOURCE  ->  INDEX  ->  SELECT  ->  WEAVE
    (get)      (find)      (choose)    (compose)

Intended façade (design-stage — see ``misc/docs/design.md`` and
``misc/docs/roadmap.md`` for what is implemented)::

    import foley

    foley.find("She pushed open the heavy oak door; rain hammered outside.")
    foley.search("distant thunder rumble", k=10)
    foley.generate("a single wooden door creak", backend="stable_audio")
    foley.ingest("~/my_sounds/")

The design is grounded in the research reports under ``misc/docs/research/``.

Foundation surface (implemented — the retrieval-agnostic base every later stage
stands on). This top-level namespace re-exports it:

    * **Data models** (``foley.base``) — the SSOT dataclasses/enums shared across
      layers (:class:`SoundRecord`, :class:`LicenseRecord`, :class:`Candidate`,
      :class:`SoundEvent`, :class:`Verdict`, :class:`IntendedUse`), the two
      affordance registries, and generic dict/JSON (de)serialization.
    * **License policy** (``foley.licensing``) — the ``license_id`` -> flag-set
      SSOT (:data:`LICENSE_FLAGS`), flag derivation, and the fail-closed
      :func:`keep` gate.
    * **Storage** (``foley.stores``) — content-addressed byte store + metadata
      store built from ``dol``, and :func:`store_sound` (the by-value vs
      by-reference gate driven by ``LicenseRecord.cache_bytes_ok``).
    * **QC** (``foley.qc``) — Tier-0 deterministic audio checks
      (:func:`run_qc` -> :class:`QCReport`, thresholds in :class:`QCThresholds`).
    * **Audio** (``foley.audio``) — I/O + DSP primitives. Exposed as a submodule
      (``foley.audio``) with the key functions also re-exported here.

Import cost: ``import foley`` pulls only ``dol`` (a light core dependency used by
``foley.stores``); ``numpy``/``soundfile``/``soxr``/``librosa``/``pyloudnorm`` are
lazy-imported inside the audio/QC functions that need them (install via the
``foley[audio]`` extra), so a bare install imports cleanly.
"""

from . import audio
from .audio import (
    WORKING_SAMPLE_RATE,
    encode,
    ensure_channels,
    fade,
    load,
    loudness_normalize,
    resample,
    save,
    to_mono,
    to_working,
    trim_silence,
)
from .base import (
    GENERATION_AFFORDANCES,
    QUERY_AFFORDANCES,
    SCHEMA_VERSION,
    AcquisitionMethod,
    Affordance,
    Candidate,
    CandidateOrigin,
    IntendedUse,
    Layer,
    LicenseRecord,
    Salience,
    SerializableMixin,
    SoundEvent,
    SoundRecord,
    StorageMode,
    Verdict,
    VerifyLevel,
)
from .licensing import (
    LICENSE_FLAGS,
    LICENSE_META,
    UNKNOWN_LICENSE_FLAGS,
    UNKNOWN_LICENSE_META,
    LicenseFlags,
    LicenseMeta,
    apply_license_flags,
    derive_license_flags,
    keep,
    keep_sound,
    license_id_from_cc_url,
    license_meta,
)
from .qc import (
    DEFAULT_QC_THRESHOLDS,
    QCReport,
    QCStatus,
    QCThresholds,
    dc_offset,
    detect_clipping,
    duration_s,
    estimate_snr,
    has_nan_inf,
    is_silent,
    measure_lufs,
    needs_edge_fade,
    run_qc,
    true_peak_dbtp,
)
from .stores import (
    DEFAULT_AUDIO_DIR,
    DEFAULT_META_DIR,
    DEFAULT_RUN_DIR,
    FOLEY_DATA_DIR,
    content_key,
    make_byte_store,
    make_meta_store,
    make_run_store,
    store_sound,
)
from . import index
from .index import (
    CLAP_SAMPLE_RATE,
    DEFAULT_CANDIDATE_K,
    DEFAULT_CLAP_DIM,
    DEFAULT_CLAP_MODEL_ID,
    RRF_K,
    Captioner,
    CatIdResolution,
    ClapEmbedder,
    ClapZeroShotTagger,
    Embedder,
    FusedHit,
    IngestReport,
    IngestResult,
    KeywordIndex,
    LanceIndex,
    MemoryIndex,
    PannsTagger,
    SoundLibrary,
    SqliteVecIndex,
    Tagger,
    VectorIndex,
    default_embedder,
    default_index,
    default_library,
    default_tagger,
    default_zeroshot_tagger,
    fuse_hits,
    hybrid_search,
    ingest_folder,
    ingest_one,
    lancedb_available,
    parse_ucs_filename,
    reciprocal_rank_fusion,
    resolve_catid,
    sqlite_vec_loadable,
    vector_search,
)

# --- source: bulk-corpus bootstrap (stdlib-only at import; numpy is lazy) ------
from .bootstrap import bootstrap, demo

# --- source: live-source adapters (Freesound) + the add_from pull facade -------
# Auto-discovery is lazy, so the Freesound adapter (and requests) is not imported
# until first use — `import foley` stays dol-only.
from .sources import add_from, list_sources, register_source

# --- source: generation adapters (Stable Audio Open / ElevenLabs) — #6 ---------
# The generate facade + its helpers. The generator adapter packages (and their
# torch/requests deps) are auto-discovered lazily, so `import foley` stays dol-only.
from .sources import (
    GenerationError,
    RecognizableVoiceRefusal,
    SafetyRefusal,
    TrademarkRefusal,
    candidate_of,
)
from .sources import generate as _generate_backend

# --- eval: Tier-1 retrieval metrics + the nDCG PR gate (numpy lazy) -----------
from . import eval  # noqa: A004 - deliberate: foley.eval is the retrieval-eval subpackage

# --- provenance: TASL attribution / credits (stdlib-only; #9b disclosure later) --
from . import provenance
from .provenance import (
    CreditEntry,
    Credits,
    attribution_line,
    credit_entry,
    credits_for,
)

# --- obs: observability + reproducible run-artifact (#11) ----------------------
# The obs package is stdlib-only at import (opentelemetry loads lazily inside the
# OTel-backed tracer only, behind foley[obs]), so this keeps `import foley` dol-only.
# Off by default: a plain façade call is a byte-for-byte no-op until obs is enabled.
from . import obs
from .obs import RunManifest, SpanRecord

__all__ = [
    # --- base: constants + enums ---------------------------------------------
    "SCHEMA_VERSION",
    "StorageMode",
    "AcquisitionMethod",
    "CandidateOrigin",
    "Salience",
    "Layer",
    "VerifyLevel",
    # --- base: affordances ---------------------------------------------------
    "Affordance",
    "QUERY_AFFORDANCES",
    "GENERATION_AFFORDANCES",
    # --- base: serialization + models ----------------------------------------
    "SerializableMixin",
    "LicenseRecord",
    "SoundRecord",
    "SoundEvent",
    "Verdict",
    "Candidate",
    "IntendedUse",
    # --- licensing: policy ---------------------------------------------------
    "LicenseFlags",
    "LICENSE_FLAGS",
    "UNKNOWN_LICENSE_FLAGS",
    "LicenseMeta",
    "LICENSE_META",
    "UNKNOWN_LICENSE_META",
    "license_meta",
    "license_id_from_cc_url",
    "derive_license_flags",
    "apply_license_flags",
    "keep",
    "keep_sound",
    # --- stores: content-addressed storage + the storage gate ----------------
    "content_key",
    "make_byte_store",
    "make_meta_store",
    "make_run_store",
    "store_sound",
    "FOLEY_DATA_DIR",
    "DEFAULT_AUDIO_DIR",
    "DEFAULT_META_DIR",
    "DEFAULT_RUN_DIR",
    # --- qc: Tier-0 deterministic audio QC -----------------------------------
    "QCStatus",
    "QCThresholds",
    "DEFAULT_QC_THRESHOLDS",
    "QCReport",
    "run_qc",
    "has_nan_inf",
    "duration_s",
    "dc_offset",
    "is_silent",
    "detect_clipping",
    "true_peak_dbtp",
    "estimate_snr",
    "needs_edge_fade",
    "measure_lufs",
    # --- audio: I/O + DSP primitives -----------------------------------------
    "audio",
    "WORKING_SAMPLE_RATE",
    "load",
    "save",
    "encode",
    "resample",
    "to_mono",
    "ensure_channels",
    "trim_silence",
    "fade",
    "loudness_normalize",
    "to_working",
    # --- index: embeddings, hybrid search, library façade, taxonomy ----------
    "index",
    "SoundLibrary",
    "default_library",
    "search",
    "similar",
    "Embedder",
    "ClapEmbedder",
    "default_embedder",
    "VectorIndex",
    "KeywordIndex",
    "MemoryIndex",
    "LanceIndex",
    "SqliteVecIndex",
    "default_index",
    "lancedb_available",
    "sqlite_vec_loadable",
    "hybrid_search",
    "vector_search",
    "reciprocal_rank_fusion",
    "fuse_hits",
    "FusedHit",
    "RRF_K",
    "DEFAULT_CANDIDATE_K",
    "DEFAULT_CLAP_MODEL_ID",
    "DEFAULT_CLAP_DIM",
    "CLAP_SAMPLE_RATE",
    "resolve_catid",
    "parse_ucs_filename",
    "CatIdResolution",
    "library",
    # --- index: taggers + ingestion ------------------------------------------
    "Tagger",
    "Captioner",
    "ClapZeroShotTagger",
    "PannsTagger",
    "default_tagger",
    "default_zeroshot_tagger",
    "ingest",
    "ingest_one",
    "ingest_folder",
    "IngestResult",
    "IngestReport",
    # --- source: bulk-corpus bootstrap ---------------------------------------
    "bootstrap",
    "demo",
    # --- source: live-source adapters + add_from pull facade -----------------
    "add_from",
    "list_sources",
    "register_source",
    # --- source: generation adapters (Stable Audio Open / ElevenLabs) --------
    "generate",
    "candidate_of",
    "GenerationError",
    # --- provenance: generation disclosure / watermark / safety (#9b) --------
    "SafetyRefusal",
    "TrademarkRefusal",
    "RecognizableVoiceRefusal",
    "art50_checklist",
    "scan_prompt",
    # --- obs: observability + reproducible run-artifact (#11) -----------------
    "obs",
    "RunManifest",
    "SpanRecord",
    # --- eval: Tier-1 retrieval metrics + nDCG gate --------------------------
    "eval",
    "evaluate",
    # --- provenance: TASL attribution / credits ------------------------------
    "provenance",
    "credits",
    "Credits",
    "CreditEntry",
    "credits_for",
    "attribution_line",
    "credit_entry",
]


def evaluate(*, golden=None, k: int = 10):
    """Run the Tier-1 retrieval eval over the golden set (nDCG@10 / recall / mAP / MRR).

    Scores every golden query through the real :meth:`SoundLibrary.search` path
    against a deterministic, CLAP-free Ring-0 library — the same computation the
    PR gate asserts on. See :mod:`foley.eval`.

    Args:
        golden: Optional path to a golden-set JSON (default: the frozen seed).
        k: Retrieval cutoff and metric ``@k``.

    Returns:
        A :class:`foley.eval.RetrievalReport`.
    """
    from .eval.golden import run_ring0_retrieval_eval

    kw = {"k": k}
    if golden is not None:
        kw["golden_path"] = golden
    return run_ring0_retrieval_eval(**kw)


def credits(
    sounds, *, title: str = "Credits", only_required: bool = False, write_to=None
):
    """Build the TASL attribution :class:`~foley.provenance.Credits` for ``sounds``.

    Works standalone today (given any iterable of sounds), and is what the WEAVE
    stage will call at render time. Inspect ``.markdown`` (a ``CREDITS.md``
    document) / ``.manifest`` (a JSON-serializable dict) on the result.

    Args:
        sounds: An iterable of :class:`SoundRecord` / :class:`Candidate` /
            :class:`LicenseRecord` (e.g. the result of :func:`search`, or the
            sounds placed in a timeline).
        title: The credits heading.
        only_required: Keep only legally-required attributions (drops CC0 /
            user-owned courtesy credits). Default credits everything.
        write_to: Optional directory; when given, writes ``CREDITS.md`` and
            ``credits.json`` into it (created if missing).

    Returns:
        A :class:`~foley.provenance.Credits`.
    """
    result = provenance.credits_for(sounds, title=title, only_required=only_required)
    if write_to is not None:
        from pathlib import Path

        out = Path(write_to)
        out.mkdir(parents=True, exist_ok=True)
        (out / "CREDITS.md").write_text(result.markdown, encoding="utf-8")
        (out / "credits.json").write_text(result.to_json(indent=2), encoding="utf-8")
    return result


def search(
    query: str,
    *,
    k: int = 10,
    filters=None,
    commercial_ok=None,
    ucs_category=None,
    min_snr=None,
    duration_range=None,
    rerank: bool = False,
):
    """Hybrid (CLAP vector ⊕ BM25) search of the default library.

    Convenience wrapper over ``foley.library.search(...)`` — see
    :meth:`foley.index.SoundLibrary.search`. Constructs the process-wide default
    library (local stores + CLAP + best available index) on first use.
    """
    return default_library().search(
        query,
        k=k,
        filters=filters,
        commercial_ok=commercial_ok,
        ucs_category=ucs_category,
        min_snr=min_snr,
        duration_range=duration_range,
        rerank=rerank,
    )


def similar(sound_id: str, *, k: int = 10):
    """Find sounds similar to a stored sound (audio<->audio) in the default library.

    See :meth:`foley.index.SoundLibrary.similar`.
    """
    return default_library().similar(sound_id, k=k)


def generate(
    prompt: str,
    *,
    backend: str = "stable_audio",
    library=None,
    store: bool = True,
    adapter=None,
    watermark=None,
    on_flagged: str = "refuse",
    watermarker=None,
    provenance_store=None,
    **affordances,
):
    """Generate a sound effect for ``prompt`` and add it to the library (by-value).

    Progressive disclosure: ``foley.generate("a single wooden door creak")`` works
    out of the box (the local Stable Audio Open backend, into the process-wide
    default library). The generated audio is stored **by-value** with a content-hash
    id, so it becomes a first-class, re-searchable library entry — every generation
    is a future free retrieval (the generation flywheel). It flows through the SAME
    :func:`~foley.index.ingest.ingest_one` pipeline as every other source, with
    operator consent for the generator license's AI-training restriction (the record
    keeps ``ai_training_ok=False``, so :func:`keep` still refuses it for
    training uses).

    Args:
        prompt: The natural-language sound description.
        backend: A registered generate source — ``"stable_audio"`` (default, local;
            needs ``foley[stable-audio]``) or ``"elevenlabs"`` (hosted;
            ``foley[elevenlabs]`` + ``$ELEVENLABS_API_KEY``).
        library: Target library (default: the process-wide default library).
        store: If ``False``, synthesize + enrich a preview without adding it.
        adapter: Optional pre-built adapter (the DI seam; production omits it and the
            registry lazily builds one).
        watermark: ``True`` require an AudioSeal watermark, ``False`` never, ``None``
            (default, auto) watermark iff ``foley[provenance]`` is installed (#9b).
        on_flagged: ``'refuse'`` (default, fail-closed) or ``'warn'`` for a prompt
            that trips the trademarked-audio / recognizable-voice safety gate (#9b).
        watermarker: An injected watermarker (the DI seam; tests pass a fake).
        provenance_store: A ``MutableMapping`` for content-credential sidecars
            (default: :func:`foley.stores.make_provenance_store`).
        **affordances: Unified generation affordances (``duration``,
            ``prompt_influence``, ``negative_prompt``, ``steps``, ``seed``, ``loop``,
            ``output_format`` — see :data:`GENERATION_AFFORDANCES`); a backend
            warns-and-drops the ones it does not support.

    Returns:
        The stored :class:`Candidate` (``origin=generated``) — its ``sound`` is the
        canonical, by-value :class:`SoundRecord` (a content-hash id).

    Raises:
        SafetyRefusal: If the prompt trips a safety gate and ``on_flagged='refuse'``
            (a :class:`GenerationError` subclass — ``TrademarkRefusal`` /
            ``RecognizableVoiceRefusal``).
        GenerationError: If the backend yields no stored sound (QC-quarantined,
            rights-blocked, or a synthesis/ingest error). The exception carries the
            full ``report`` and terminal ``status`` so callers can react distinctly.
    """
    report = _generate_backend(
        prompt,
        backend=backend,
        library=library,
        store=store,
        adapter=adapter,
        watermark=watermark,
        on_flagged=on_flagged,
        watermarker=watermarker,
        provenance_store=provenance_store,
        **affordances,
    )
    results = report.results
    res = results[0] if results else None
    if res is None:
        raise GenerationError(
            f"generation via {backend!r} produced no result", report=report, status=None
        )
    if res.status in ("pass", "warn"):
        return candidate_of(res)
    if res.status == "skipped_dup":
        # A byte-identical regeneration is already in the library — return it (the
        # desirable flywheel behavior: never store byte-twins).
        lib = library if library is not None else default_library()
        return Candidate(sound=lib[res.id], origin=CandidateOrigin.generated)
    raise GenerationError(
        f"generation via {backend!r} yielded no stored sound ({res.status})",
        report=report,
        status=res.status,
    )


def ingest(
    path,
    *,
    library=None,
    backend: str = "local",
    qc: bool = True,
    recursive: bool = True,
    **kw,
):
    """Ingest a folder (or single file) of sounds into the default library.

    ``probe -> QC -> tag -> zero-shot -> caption -> embed -> SoundRecord`` for
    each file, returning an :class:`~foley.index.IngestReport`. See
    :func:`foley.index.ingest_folder` / :func:`~foley.index.ingest_one` for the
    per-file options (``license``, taggers, ``min_status``, …).

    Args:
        path: A folder (walked) or a single audio file.
        library: Target library (default: the process-wide default library).
        backend: ``"local"`` ingests filesystem audio; other backends (a source
            adapter pull) route through ``add_from`` (subtask #5) — kept in the
            signature for forward-compat.
        qc: Run the Tier-0 QC gate (quarantines failing clips).
        recursive: Recurse into sub-folders.
        **kw: Forwarded to :func:`foley.index.ingest_one`.
    """
    if backend != "local":
        # A non-local backend names a live source adapter (#5): treat ``path`` as
        # the query and route through the add_from pull facade (search -> license
        # gate -> download -> the shared ingest_one pipeline).
        return add_from(backend, query=path, library=library, **kw)
    return ingest_folder(
        path,
        library=library if library is not None else default_library(),
        recursive=recursive,
        do_qc=qc,
        **kw,
    )


def __getattr__(name: str):
    """Lazily expose ``foley.library`` + the #9b disclosure helpers.

    ``library`` is kept lazy so ``import foley`` never constructs the CLAP model or
    the index; the disclosure helpers are lazy so the (stdlib-only)
    :mod:`foley.provenance.disclosure` module is not imported until first use,
    keeping the eager ``import foley`` graph minimal.
    """
    if name == "library":
        return default_library()
    if name in ("art50_checklist", "scan_prompt", "build_content_credential"):
        from .provenance import disclosure

        return getattr(disclosure, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
