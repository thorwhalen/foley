"""The ``SoundLibrary`` façade — one searchable, license-aware sound library.

Composes the four injected storage concerns behind a stable interface (report
04 §6.1), so each swaps local->cloud with no change to retrieval logic::

    SoundLibrary
    ├── sounds : Mapping[content_key -> bytes]   # audio blobs   (dol.Files -> S3)
    ├── meta   : Mapping[id -> SoundRecord]       # canonical SSOT (JSON -> S3/PG)
    ├── vindex : VectorIndex                      # CLAP 512-d    (LanceDB/sqlite/memory)
    └── kindex : KeywordIndex (BM25)              # tags+caption  (same, or separate)

Progressive disclosure: ``SoundLibrary()`` works out of the box with sensible
local defaults (all components lazily constructed), while every store, index, and
the embedder is an optional keyword injection (open-closed). The library is a
read-only ``Mapping`` of :class:`~foley.base.SoundRecord`s (``lib[sound_id]``);
:meth:`add` is the write path that stores bytes and updates both indexes.

``search`` embeds the query, runs the vector KNN and the BM25 keyword search, and
RRF-fuses them (:mod:`foley.index.search`) — nothing here changes between the
in-memory, LanceDB, or sqlite backends, or between local and cloud storage.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import cached_property, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ..base import Candidate, CandidateOrigin, SoundRecord, StorageMode
from ..stores import (
    FOLEY_DATA_DIR,
    make_byte_store,
    make_meta_store,
    store_sound,
)
from .search import DEFAULT_CANDIDATE_K, RRF_K, hybrid_search, vector_search

if TYPE_CHECKING:  # pragma: no cover - typing only
    from numpy import ndarray

    from ..audio import AudioSource

#: When post-filtering results, pull this many times ``k`` from the rankers first
#: so enough survive the metadata filter to still return ``k``.
_OVERFETCH_FACTOR: int = 5


class SoundLibrary(Mapping):
    """A searchable, license-aware library of sounds (the foley INDEX façade).

    Read it as a ``Mapping`` of :class:`~foley.base.SoundRecord`s; search it with
    :meth:`search` (text) / :meth:`search_clip` (a reference clip) / :meth:`similar`
    (audio<->audio by id); browse it with :meth:`filter`; grow it with :meth:`add`.
    """

    def __init__(
        self,
        *,
        sounds=None,
        meta=None,
        vindex=None,
        kindex=None,
        embedder=None,
        data_dir=None,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        rrf_k: int = RRF_K,
    ):
        """Create a library; omitted components are built lazily on first use.

        Args:
            sounds: Byte store ``Mapping[content_key -> bytes]`` (default:
                ``dol.Files`` under the data dir).
            meta: Metadata store ``Mapping[id -> SoundRecord]`` (default: JSON
                files under the data dir).
            vindex: The vector index (default: shared best-available backend).
            kindex: The keyword index (default: the same shared backend).
            embedder: The text<->audio embedder (default: CLAP).
            data_dir: Data root for the default stores/index (default:
                ``$FOLEY_DATA_DIR`` or ``~/.local/share/foley``).
            candidate_k: Per-ranker shortlist depth before fusion.
            rrf_k: The RRF damping constant.
        """
        self._sounds = sounds
        self._meta = meta
        self._vindex = vindex
        self._kindex = kindex
        self._embedder = embedder
        self._data_dir = data_dir
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k

    # -- lazily-defaulted components ----------------------------------------

    @cached_property
    def data_dir(self) -> Path:
        """The data root for default stores/index."""
        return Path(self._data_dir) if self._data_dir is not None else FOLEY_DATA_DIR

    @cached_property
    def sounds(self):
        """The content-addressed byte store."""
        if self._sounds is not None:
            return self._sounds
        return make_byte_store(self.data_dir / "audio")

    @cached_property
    def meta(self):
        """The metadata store (``id -> SoundRecord``)."""
        if self._meta is not None:
            return self._meta
        return make_meta_store(self.data_dir / "meta")

    @cached_property
    def embedder(self):
        """The text<->audio embedder (CLAP by default)."""
        if self._embedder is not None:
            return self._embedder
        from .embedders import default_embedder

        return default_embedder()

    @cached_property
    def _default_backend(self):
        """The shared best-available index backend (used for both v/kindex)."""
        from .indexes import default_index

        return default_index(data_dir=self.data_dir, dim=self.embedder.dim)

    @cached_property
    def vindex(self):
        """The vector index."""
        return self._vindex if self._vindex is not None else self._default_backend

    @cached_property
    def kindex(self):
        """The keyword index."""
        return self._kindex if self._kindex is not None else self._default_backend

    # -- Mapping surface (read-only browse over meta) -----------------------

    def __getitem__(self, sound_id: str) -> SoundRecord:
        return self.meta[sound_id]

    def __iter__(self):
        return iter(self.meta)

    def __len__(self) -> int:
        return len(self.meta)

    # -- audio access -------------------------------------------------------

    def audio(self, sound_id: str) -> bytes:
        """Return a sound's archive bytes (by-value from the store, or from a
        local by-reference path).

        Args:
            sound_id: The record id.

        Returns:
            The raw archive bytes.

        Raises:
            LookupError: If the bytes are neither cached (by-value) nor readable
                from a local ``uri`` — a remote by-reference sound needs its
                source adapter (subtask #5) to fetch.
        """
        rec = self.meta[sound_id]
        if rec.storage_mode == StorageMode.by_value and rec.content_sha256:
            return self.sounds[rec.content_sha256]
        uri = rec.uri
        if uri and os.path.exists(uri):
            return Path(uri).read_bytes()
        raise LookupError(
            f"audio bytes for {sound_id!r} are not available locally "
            f"(storage_mode={rec.storage_mode}, uri={uri!r}); a remote "
            f"by-reference sound must be fetched via its source adapter."
        )

    def array(
        self, sound_id: str, *, sr: Optional[int] = None, mono: bool = True
    ) -> "ndarray":
        """Decode a sound to a working array (``float32``).

        Args:
            sound_id: The record id.
            sr: Target sample rate (default: the working rate, 48 kHz).
            mono: Down-mix to mono (default ``True``).

        Returns:
            The decoded working array.
        """
        from ..audio import WORKING_SAMPLE_RATE, load, to_working

        samples, orig_sr = load(self.audio(sound_id))
        target_sr = WORKING_SAMPLE_RATE if sr is None else sr
        return to_working(samples, orig_sr, mono=mono, target_sr=target_sr)

    # -- write path ---------------------------------------------------------

    def add(
        self,
        record: SoundRecord,
        *,
        data: Optional[bytes] = None,
        vector: "Optional[ndarray]" = None,
    ) -> SoundRecord:
        """Store a sound and index it (the ingest write path).

        Persists bytes via :func:`~foley.stores.store_sound` (honouring the
        by-value/by-reference license gate), upserts the CLAP vector into the
        vector index, and indexes ``caption``+``tags`` into the keyword index.

        A sound is retrieval-first, so it MUST carry an embedding: supply either
        ``data`` (bytes to embed — note a by-reference sound is embedded from its
        transient bytes even though they are not cached) or a precomputed
        ``vector``. Adding with neither raises, rather than silently indexing a
        vectorless row (which the single-table :class:`LanceIndex` cannot persist,
        producing backend-dependent search results).

        Args:
            record: The record to add (mutated by ``store_sound`` with resolved
                storage fields, and stamped with the embedding model/dim).
            data: The archive bytes (required for by-value storage; also the
                source for computing ``vector`` when it is not supplied).
            vector: A precomputed CLAP embedding; when omitted and ``data`` is
                given, it is computed via the library's embedder.

        Returns:
            The same (persisted, indexed) ``record``.

        Raises:
            ValueError: If neither ``data`` nor ``vector`` is provided (no way to
                obtain an embedding).
        """
        if vector is None and data is not None:
            samples, orig_sr = _decode(data)
            vector = self.embedder.embed_audio(samples, orig_sr)
        if vector is None:
            raise ValueError(
                f"add({record.id!r}) needs an embedding: pass audio bytes as "
                f"data= (to embed) or a precomputed vector=. A retrieval-first "
                f"library indexes every sound by its CLAP vector; to keyword-index "
                f"a vectorless sound, call the keyword index's index() directly."
            )
        record.embedding_model = self.embedder.model_id
        record.embedding_dim = self.embedder.dim
        record.embedding_ref = record.id
        store_sound(record, data, sounds=self.sounds, meta=self.meta)
        self.vindex.upsert(record.id, vector, {"id": record.id})
        self.kindex.index(record.id, _index_text(record), {"id": record.id})
        _commit(self.vindex)
        _commit(self.kindex)
        return record

    # -- retrieval ----------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        filters: Optional[dict] = None,
        commercial_ok: Optional[bool] = None,
        ucs_category: Optional[str] = None,
        min_snr: Optional[float] = None,
        duration_range: "Optional[tuple[float, float]]" = None,
        rerank: bool = False,
    ) -> "list[Candidate]":
        """Hybrid (CLAP vector ⊕ BM25) search for a text query.

        Args:
            query: The natural-language query.
            k: Number of results to return.
            filters: Extra ``{record_attr: value}`` equality predicates.
            commercial_ok: If ``True``, keep only commercially-usable sounds.
            ucs_category: Keep only sounds with this UCS CatID.
            min_snr: Keep only sounds whose QC ``snr_db`` is at least this.
            duration_range: Keep only sounds whose ``duration_s`` is in
                ``(min, max)``.
            rerank: Re-order the shortlist by direct query<->audio cosine
                (fills the CLAP score for keyword-only hits).

        Returns:
            Up to ``k`` :class:`~foley.base.Candidate`s, best first.
        """
        from ..obs.recorder import facade_run
        from ..obs.trace import GENAI

        # Root run-span for the retrieval op; a no-op unless observability is on (#11).
        with facade_run(
            "search",
            inputs={
                "query": query,
                "k": k,
                "filters": filters,
                "commercial_ok": commercial_ok,
                "ucs_category": ucs_category,
                "min_snr": min_snr,
                "duration_range": duration_range,
            },
            params={"rerank": rerank, "rrf_k": self.rrf_k},
        ) as run:
            filtering = any(
                x is not None
                for x in (filters, commercial_ok, ucs_category, min_snr, duration_range)
            )
            fetch_k = k * _OVERFETCH_FACTOR if filtering else k
            with run.span(
                "retrieve",
                **{
                    GENAI["operation"]: "embeddings",
                    GENAI["data_source_id"]: "foley-index",
                },
            ):
                hits = hybrid_search(
                    query,
                    embedder=self.embedder,
                    vindex=self.vindex,
                    kindex=self.kindex,
                    k=fetch_k,
                    candidate_k=max(self.candidate_k, fetch_k),
                    rrf_k=self.rrf_k,
                )
            candidates = self._hits_to_candidates(hits)
            candidates = [
                c
                for c in candidates
                if _record_matches(
                    c.sound,
                    filters=filters,
                    commercial_ok=commercial_ok,
                    ucs_category=ucs_category,
                    min_snr=min_snr,
                    duration_range=duration_range,
                )
            ]
            if rerank:
                candidates = self._rerank(query, candidates)
            result = candidates[:k]
            run.add_result_ids([c.sound.id for c in result])
            run.add_candidate_scores(
                [
                    {
                        "id": c.sound.id,
                        "clap": c.clap_score,
                        "bm25": c.bm25_score,
                        "rrf": c.rrf_score,
                        "rerank": c.rerank_score,
                    }
                    for c in result
                ]
            )
            return result

    def search_clip(
        self, clip: "AudioSource", *, sr: Optional[int] = None, k: int = 10
    ) -> "list[Candidate]":
        """Search by a reference audio clip (audio<->audio via CLAP).

        Args:
            clip: A working array, or a path/bytes/file decodable by
                :func:`foley.audio.load`.
            sr: Sample rate when ``clip`` is already a working array.
            k: Number of results.

        Returns:
            Up to ``k`` :class:`~foley.base.Candidate`s, most-similar first.
        """
        samples, orig_sr = _as_working(clip, sr)
        qvec = self.embedder.embed_audio(samples, orig_sr)
        hits = vector_search(qvec, vindex=self.vindex, k=k)
        return self._hits_to_candidates(hits)

    def similar(self, sound_id: str, *, k: int = 10) -> "list[Candidate]":
        """Return the ``k`` sounds most similar to ``sound_id`` (audio<->audio).

        Uses the stored vector (no re-decoding); the query sound itself is
        excluded from the results.
        """
        from ..obs.recorder import facade_run

        with facade_run("similar", inputs={"sound_id": sound_id, "k": k}) as run:
            qvec = self.vindex.get_vector(sound_id)
            if qvec is None:
                return []
            hits = vector_search(qvec, vindex=self.vindex, k=k + 1)
            candidates = self._hits_to_candidates(hits, exclude_id=sound_id)
            result = candidates[:k]
            run.add_result_ids([c.sound.id for c in result])
            return result

    def filter(self, **facets) -> "list[SoundRecord]":
        """Browse the library by metadata facets (no ranking).

        Accepts the same facet keywords as :meth:`search`'s filters
        (``commercial_ok``, ``ucs_category``, ``min_snr``, ``duration_range``)
        plus any ``record_attr=value`` equality predicate.
        """
        known = ("commercial_ok", "ucs_category", "min_snr", "duration_range")
        primary = {k: facets.pop(k, None) for k in known}
        extra = facets or None
        return [
            rec
            for rec in self.meta.values()
            if _record_matches(rec, filters=extra, **primary)
        ]

    # -- internals ----------------------------------------------------------

    def _hits_to_candidates(self, hits, *, exclude_id: Optional[str] = None):
        out = []
        for h in hits:
            if exclude_id is not None and h.id == exclude_id:
                continue
            if h.id not in self.meta:
                continue  # index/meta drift: skip orphan hits
            out.append(
                Candidate(
                    sound=self.meta[h.id],
                    origin=CandidateOrigin.retrieved,
                    clap_score=h.clap_score,
                    bm25_score=h.bm25_score,
                    rrf_score=h.rrf_score,
                )
            )
        return out

    def _rerank(self, query: str, candidates):
        if not candidates:
            return candidates
        import numpy as np

        qvec = self.embedder.embed_text(query)[0]
        for cand in candidates:
            vec = self.vindex.get_vector(cand.sound.id)
            if vec is not None:
                cand.clap_score = float(np.dot(qvec, vec))
        return sorted(
            candidates,
            key=lambda c: c.clap_score if c.clap_score is not None else -1.0,
            reverse=True,
        )


# ---------------------------------------------------------------------------
# module-level helpers
# ---------------------------------------------------------------------------


def _index_text(record: SoundRecord) -> str:
    """The BM25 document for a record: its caption + tags."""
    parts = []
    if record.caption:
        parts.append(record.caption)
    if record.tags:
        parts.append(" ".join(str(t) for t in record.tags))
    return " ".join(parts)


def _decode(data: bytes):
    from ..audio import load

    return load(data)


def _as_working(clip: "Union[AudioSource, ndarray]", sr: Optional[int]):
    """Coerce a clip (working array or decodable source) to ``(samples, sr)``."""
    if hasattr(clip, "ndim"):  # already a working array
        if sr is None:
            from ..audio import WORKING_SAMPLE_RATE

            sr = WORKING_SAMPLE_RATE
        return clip, sr
    from ..audio import load

    return load(clip)


def _commit(index) -> None:
    commit = getattr(index, "commit", None)
    if callable(commit):
        commit()


def _record_matches(
    record: SoundRecord,
    *,
    filters: Optional[dict] = None,
    commercial_ok: Optional[bool] = None,
    ucs_category: Optional[str] = None,
    min_snr: Optional[float] = None,
    duration_range: "Optional[tuple[float, float]]" = None,
) -> bool:
    """True if ``record`` satisfies every supplied metadata facet."""
    if commercial_ok and not record.license.commercial_ok:
        return False
    if ucs_category is not None and record.ucs_category != ucs_category:
        return False
    if min_snr is not None:
        snr = (record.qc or {}).get("snr_db")
        # Only a FINITE snr below the floor excludes. A None snr means "no finite
        # SNR" — either unmeasured or infinitely clean (a zero-padded one-shot
        # scores +inf, clamped to None for JSON-safety); a max-clean clip must not
        # be dropped by a quality floor, so None passes.
        if snr is not None and snr < min_snr:
            return False
    if duration_range is not None:
        lo, hi = duration_range
        if record.duration_s is None or not (lo <= record.duration_s <= hi):
            return False
    if filters:
        for attr, value in filters.items():
            if getattr(record, attr, None) != value:
                return False
    return True


@lru_cache(maxsize=1)
def default_library() -> SoundLibrary:
    """The process-wide default library (local stores + CLAP + best index)."""
    return SoundLibrary()
