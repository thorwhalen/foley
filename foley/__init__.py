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
    foley.generate("a single wooden door creak", backend="stable_audio_open")
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
    UNKNOWN_LICENSE_FLAGS,
    LicenseFlags,
    apply_license_flags,
    derive_license_flags,
    keep,
    keep_sound,
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
    FOLEY_DATA_DIR,
    content_key,
    make_byte_store,
    make_meta_store,
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
    "derive_license_flags",
    "apply_license_flags",
    "keep",
    "keep_sound",
    # --- stores: content-addressed storage + the storage gate ----------------
    "content_key",
    "make_byte_store",
    "make_meta_store",
    "store_sound",
    "FOLEY_DATA_DIR",
    "DEFAULT_AUDIO_DIR",
    "DEFAULT_META_DIR",
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
]


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
        raise NotImplementedError(
            f"ingest backend {backend!r} not implemented; only 'local' is "
            f"available (source-adapter pulls arrive with subtask #5)."
        )
    return ingest_folder(
        path,
        library=library if library is not None else default_library(),
        recursive=recursive,
        do_qc=qc,
        **kw,
    )


def __getattr__(name: str):
    """Lazily expose ``foley.library`` (the default :class:`SoundLibrary`).

    Kept lazy so ``import foley`` never constructs the CLAP model or the index.
    """
    if name == "library":
        return default_library()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
