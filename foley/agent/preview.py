"""Audition UX — preview a sound, find similar ones, and refine by relevance feedback (#12).

The interactive/agentic layer over the existing retrieval engine, all thin over
:class:`foley.index.SoundLibrary`:

* :func:`preview` — synthesize a short audition clip for a sound and reference it by a
  **store key** (never raw bytes over the wire); degrades to ``preview_uri=None`` when
  the audio codec extra is absent.
* :func:`similar_to` — "more like this": ``sound_id`` / :class:`~foley.base.Candidate`
  → by-id neighbours (``SoundLibrary.similar``), or a raw clip → audio-to-audio search
  (``SoundLibrary.search_clip``). A NEW clip/candidate-in entrypoint, distinct from the
  existing by-id ``SoundLibrary.similar``.
* :func:`refine` — TRUE relevance feedback (distinct from the query-paraphrase
  :func:`foley.refine_query`): expand the query for recall, pull neighbours of the
  session's **picks**, drop its **rejects**, and re-rank.

Dol-only core (numpy/soundfile only inside :func:`preview`'s encode path).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..base import Candidate
    from .session import SessionStore

#: Default audition length (seconds).
PREVIEW_SECONDS: int = 6


def _default_library():
    from ..index.library import default_library

    return default_library()


def preview(
    candidate_or_id,
    *,
    seconds: int = PREVIEW_SECONDS,
    library=None,
    byte_store=None,
    session: "Optional[SessionStore]" = None,
) -> "Candidate":
    """Produce a short audition of a sound; set its ``preview_uri`` to a store key.

    Writes the first ``seconds`` of the clip (FLAC) into ``byte_store`` under its
    content key and points :attr:`Candidate.preview_uri` at that key — referencing the
    audio, never returning bytes. Fail-safe: if the audio codec extra (``foley[audio]``)
    or the clip is unavailable, ``preview_uri`` is ``None`` (the sound id + duration
    still let a client fetch it).

    Args:
        candidate_or_id: A :class:`~foley.base.Candidate` or a sound id.
        seconds: Audition length.
        library: The :class:`foley.index.SoundLibrary` (default: the shared one).
        byte_store: A ``MutableMapping[str, bytes]`` to hold the preview (default: none —
            then ``preview_uri`` stays ``None``).
        session: Optional session (unused here; accepted for a uniform signature).

    Returns:
        The candidate with ``preview_uri`` set (or ``None`` on graceful degradation).
    """
    from ..base import Candidate

    library = library or _default_library()
    if isinstance(candidate_or_id, Candidate):
        cand, sid = candidate_or_id, candidate_or_id.sound.id
    else:
        sid = str(candidate_or_id)
        cand = Candidate(sound=library[sid])
    preview_uri = None
    if byte_store is not None:
        try:
            from ..audio import WORKING_SAMPLE_RATE, encode
            from ..stores import content_key

            arr = library.array(sid, sr=WORKING_SAMPLE_RATE, mono=True)
            clip = arr[: int(seconds * WORKING_SAMPLE_RATE)]
            data = encode(clip, WORKING_SAMPLE_RATE, fmt="flac")
            key = content_key(data)
            byte_store[key] = data
            preview_uri = key
        except Exception:
            preview_uri = None  # fail-safe: reference by id + duration instead
    cand.preview_uri = preview_uri
    return cand


def similar_to(clip_or_candidate, *, k: int = 10, library=None) -> "list[Candidate]":
    """ "More like this" — neighbours of a sound id / candidate, or of a raw clip.

    A ``str`` id or a :class:`~foley.base.Candidate` uses by-id neighbours
    (``SoundLibrary.similar``, self excluded); a raw working-array / bytes clip uses
    audio-to-audio search (``SoundLibrary.search_clip``).

    Args:
        clip_or_candidate: A sound id, a :class:`~foley.base.Candidate`, or a clip.
        k: How many neighbours to return.
        library: The :class:`foley.index.SoundLibrary` (default: the shared one).

    Returns:
        A list of :class:`~foley.base.Candidate`.
    """
    from ..base import Candidate

    library = library or _default_library()
    if isinstance(clip_or_candidate, str):
        return library.similar(clip_or_candidate, k=k)
    if isinstance(clip_or_candidate, Candidate):
        return library.similar(clip_or_candidate.sound.id, k=k)
    return library.search_clip(clip_or_candidate, k=k)


@dataclass
class RefineResult:
    """The output of :func:`refine`: the expanded queries and the re-ranked candidates."""

    queries: "list[str]"
    results: "list[Candidate]"


def _score(candidate) -> float:
    """A candidate's best available relevance score (for feedback re-ranking)."""
    for attr in ("rerank_score", "rrf_score", "clap_score"):
        v = getattr(candidate, attr, None)
        if v is not None:
            return float(v)
    return 0.0


def _rerank_by_feedback(candidates, *, picked: set, rejected: set) -> "list[Candidate]":
    """Drop rejected sounds and rank the rest by score (picks already boost via neighbours)."""
    kept = [c for c in candidates if c.sound.id not in rejected]
    kept.sort(key=_score, reverse=True)
    return kept


def refine(
    session: "Optional[SessionStore]" = None,
    *,
    query: "Optional[str]" = None,
    picked_ids: "tuple[str, ...]" = (),
    rejected_ids: "tuple[str, ...]" = (),
    hint: "Optional[str]" = None,
    n: int = 3,
    k: int = 10,
    library=None,
    refiner=None,
) -> RefineResult:
    """Relevance-feedback refinement: expand for recall, boost picks, drop rejects, re-rank.

    Distinct from :func:`foley.refine_query` (which only paraphrases a query): this reads
    the session's picks/rejects (or the explicit ``picked_ids`` / ``rejected_ids``),
    expands the query into paraphrases for recall, gathers neighbours of every pick, drops
    the rejects, and re-ranks by score.

    Args:
        session: The audition session (source of picks/rejects when not passed explicitly).
        query: The base text query to expand (optional).
        picked_ids / rejected_ids: Explicit feedback (override the session's).
        hint: A steer for the query expansion.
        n: Paraphrases to request.
        k: Result depth.
        library: The :class:`foley.index.SoundLibrary` (default: the shared one).
        refiner: The query-expansion seam (default: the deterministic fake).

    Returns:
        A :class:`RefineResult`.
    """
    library = library or _default_library()
    picked = list(picked_ids) or (session.picked_ids() if session else [])
    rejected = list(rejected_ids) or (session.rejected_ids() if session else [])

    queries: "list[str]" = []
    if query:
        from .refine import refine_query

        queries = list(
            dict.fromkeys(
                [query, *refine_query(query, n=n, hint=hint, refiner=refiner)]
            )
        )

    pool: "dict[str, Candidate]" = {}
    for q in queries:
        for c in library.search(q, k=k):
            pool.setdefault(c.sound.id, c)
    for pid in picked:
        for c in library.similar(pid, k=k):
            pool.setdefault(c.sound.id, c)

    ranked = _rerank_by_feedback(
        list(pool.values()), picked=set(picked), rejected=set(rejected)
    )
    return RefineResult(queries=queries, results=ranked[:k])
