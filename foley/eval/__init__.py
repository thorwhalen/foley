"""Tier-1 retrieval evaluation — metrics, a frozen golden set, and the nDCG gate.

This subpackage answers "did we retrieve the right sound?" with TREC-style
ranking metrics (``nDCG@10`` / ``Recall@k`` / ``mAP@10`` / ``MRR@10``) over a
frozen golden set, and ships the **PR gate**: a pytest check that blocks a change
whose ``nDCG@10`` regresses by more than ``0.02`` on the Ring-0 golden set. Every
part is pure numpy/stdlib and deterministic — no ``ranx``/``numba``, no CLAP, no
downloads — so the gate runs on every index/embedder/prompt PR in foley's CI.

Tier-2 fit-judging (LLM/audio-LM "does this clip match the intent?") is subtask
#10b, added after the Select agent (#7). All numpy imports are function-local so
``import foley`` stays dol-only.
"""

from __future__ import annotations

from .baseline import (
    DEFAULT_TOLERANCE,
    is_stale,
    load_baseline,
    write_baseline,
)
from .embedder import HashingBowEmbedder
from .golden import (
    GoldenItem,
    build_eval_library,
    load_golden,
    run_ring0_retrieval_eval,
    to_qrels,
)
from .retrieval import (
    RetrievalReport,
    average_precision_at_k,
    build_run,
    evaluate_run,
    mean_over_queries,
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

__all__ = [
    # metrics
    "ndcg_at_k",
    "recall_at_k",
    "precision_at_k",
    "average_precision_at_k",
    "mrr_at_k",
    "mean_over_queries",
    "build_run",
    "evaluate_run",
    "RetrievalReport",
    # golden set + harness
    "GoldenItem",
    "load_golden",
    "to_qrels",
    "build_eval_library",
    "run_ring0_retrieval_eval",
    # embedder + baseline
    "HashingBowEmbedder",
    "load_baseline",
    "write_baseline",
    "is_stale",
    "DEFAULT_TOLERANCE",
]
