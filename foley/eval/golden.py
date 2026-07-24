"""The frozen golden set + the deterministic Ring-0 retrieval harness.

A :class:`GoldenItem` is one ``(narrative context → expected sounds)`` judgment;
its ``answer_clip_ids`` + ``grade`` become the TREC ``qrels`` the metrics score
against. :func:`build_eval_library` stands up an ephemeral, in-memory library
over the bundled Ring-0 synthetic fixture with **injected caption vectors** (via
:class:`~foley.eval.embedder.HashingBowEmbedder`), so retrieval is deterministic
and CLAP-free; :func:`run_ring0_retrieval_eval` runs every golden query through
the real ``SoundLibrary.search`` path and scores it.

The eval fixtures (``seed.json``, ``baseline.json``) are **package data** under
``foley/data/golden/`` — so they ship in the wheel and ``foley.evaluate()`` /
``foley eval`` work on a bare ``pip install`` (not only from a source checkout).
``build_eval_library`` builds records **directly** with stable
``ring0:<stem>`` ids (not via ``ingest_one``'s content-hash ids), so the run doc
ids join 1:1 with the qrels — no alias map, no content-hash keyspace trap. The
gate therefore does NOT exercise ``ingest_one`` (that path is covered by
``test_ingest``/``test_bootstrap``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..base import SoundRecord
from .embedder import HashingBowEmbedder
from .retrieval import RetrievalReport, build_run, evaluate_run

#: Package data root (``foley/eval/golden.py`` → parent.parent = ``foley`` →
#: ``foley/data``); both the eval fixtures and the Ring-0 manifest ship here, so
#: they resolve identically from a source checkout and an installed wheel.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_GOLDEN_PATH = _DATA_DIR / "golden" / "seed.json"
RING0_MANIFEST_PATH = _DATA_DIR / "ring0" / "manifest.json"


@dataclass(frozen=True)
class GoldenItem:
    """One frozen ``(context → expected sounds)`` judgment (report 08 §1.3).

    Attributes:
        id: Unique item id (e.g. ``gld_0001``).
        context: The narrative paragraph (the future SELECT input).
        expected_events: One or more ``{query, ucs_catid, layer, diegetic,
            salience, ...}`` dicts; ``query`` is the string fed to ``search``.
        answer_clip_ids: ``{ucs_catid: [clip_id, ...]}`` — the acceptable clips.
        grade: ``{clip_id: grade}`` (2 ideal / 1 acceptable / 0 wrong).
        negatives: Free-text distractors (unused by scoring; documentation).
        labeler: Provenance of the labels (``llm+human`` etc.).
        schema_version: The GoldenItem schema version.
    """

    id: str
    context: str
    expected_events: list
    answer_clip_ids: dict
    grade: dict
    negatives: list = field(default_factory=list)
    labeler: str = "llm+human"
    schema_version: int = 1


def load_golden(path=DEFAULT_GOLDEN_PATH) -> "list[GoldenItem]":
    """Load and validate the frozen golden set from ``path`` (JSON list)."""
    raw = json.loads(Path(path).read_text())
    return [
        GoldenItem(
            id=it["id"],
            context=it["context"],
            expected_events=it["expected_events"],
            answer_clip_ids=it["answer_clip_ids"],
            grade=it["grade"],
            negatives=it.get("negatives", []),
            labeler=it.get("labeler", "llm+human"),
            schema_version=it.get("schema_version", 1),
        )
        for it in raw
    ]


def to_qrels(golden: "list[GoldenItem]") -> "dict[str, dict[str, int]]":
    """Flatten the golden set into TREC qrels: ``{query_id: {clip_id: grade}}``.

    One qrels row per ``(item, event)`` — ``query_id = f"{item.id}::{event_idx}"``
    — future-proofing multi-event items (seed items are single-event today). Each
    clip in ``answer_clip_ids`` carries its ``grade``.
    """
    qrels: "dict[str, dict[str, int]]" = {}
    for item in golden:
        clips = {
            clip_id
            for clip_list in item.answer_clip_ids.values()
            for clip_id in clip_list
        }
        judgments = {clip_id: int(item.grade.get(clip_id, 0)) for clip_id in clips}
        for ev_idx in range(len(item.expected_events)):
            qrels[f"{item.id}::{ev_idx}"] = dict(judgments)
    return qrels


def build_eval_library(*, embedder=None, manifest_path=RING0_MANIFEST_PATH):
    """Build the ephemeral Ring-0 eval library (stem ids + injected caption vectors).

    Each manifest clip becomes a :class:`~foley.base.SoundRecord` with id
    ``ring0:<stem>`` and a vector = ``embedder.embed_text(caption + tags)`` — so
    both the vector and BM25 legs carry the caption bag-of-words and the answer
    clip lands at integer rank 1 (deterministic, cross-platform).

    Args:
        embedder: A text embedder (default: :class:`HashingBowEmbedder`).
        manifest_path: The Ring-0 ``manifest.json`` (default: the bundled fixture).

    Returns:
        A populated in-memory :class:`~foley.index.library.SoundLibrary`.
    """
    from ..bootstrap import _fresh_memory_library, _ring0_license

    emb = embedder if embedder is not None else HashingBowEmbedder()
    lib = _fresh_memory_library(embedder=emb)
    manifest_dir = Path(manifest_path).parent
    manifest = json.loads(Path(manifest_path).read_text())
    for entry in manifest:
        stem = Path(entry["file"]).stem
        text = entry["caption"] + " " + " ".join(entry.get("tags", []))
        rec = SoundRecord(
            id=f"ring0:{stem}",
            # A real fetchable uri (the fixture wav) so the record stores
            # by-reference without the audio bytes — retrieval only needs the
            # injected vector + metadata, not the decoded PCM.
            uri=str(manifest_dir / entry["file"]),
            caption=entry["caption"],
            tags=list(entry.get("tags", [])),
            ucs_category=entry.get("ucs_catid"),
            license=_ring0_license(),
        )
        lib.add(rec, vector=emb.embed_text(text)[0])
    return lib


def run_ring0_retrieval_eval(
    *, k: int = 10, golden_path=DEFAULT_GOLDEN_PATH, embedder=None
) -> RetrievalReport:
    """Score the golden set's queries against the Ring-0 library — the gate input.

    Runs every golden ``expected_events[].query`` through the real
    :meth:`SoundLibrary.search` path (vector ⊕ BM25 ⊕ RRF) and evaluates the
    resulting runs against the golden qrels.

    Args:
        k: Retrieval cutoff (and the metric ``@k``).
        golden_path: The golden set JSON.
        embedder: The eval embedder (default: :class:`HashingBowEmbedder`).

    Returns:
        A :class:`RetrievalReport` (per-query + mean nDCG@10 / recall / mAP / MRR).
    """
    golden = load_golden(golden_path)
    lib = build_eval_library(embedder=embedder)
    qrels = to_qrels(golden)
    run: "dict[str, dict[str, float]]" = {}
    for item in golden:
        for ev_idx, event in enumerate(item.expected_events):
            candidates = lib.search(event["query"], k=k)
            run[f"{item.id}::{ev_idx}"] = build_run(candidates)
    return evaluate_run(run, qrels, k=k)
