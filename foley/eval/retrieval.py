"""Tier-1 retrieval metrics + run assembly — pure stdlib, CI-safe, ranx-exact.

The metrics (``nDCG@10``, ``Recall@k``, ``Precision@k``, ``mAP@10``, ``MRR@10``)
are hand-rolled in stdlib (no ``ranx``/``numba``) so the nDCG PR gate runs in
foley's numpy-only CI with zero heavy deps — yet they are **numerically
identical** to ``ranx``/``pytrec_eval`` (guarded by the opt-in
``tests/eval/test_metrics_vs_ranx.py`` oracle). nDCG uses the **linear** Järvelin
gain ``Σ grade_i / log2(rank+1)`` — the definition ``ranx``'s ``"ndcg@10"`` and
``pytrec_eval``'s ``ndcg_cut_10`` actually implement (report 08 §1.1's
``2^grade−1`` is a doc bug).

Vocabulary (TREC-style):
    * **qrels** — ``{query_id: {clip_id: grade}}`` — the ground-truth relevance
      grades (0 = wrong, 1 = acceptable, 2 = ideal); the raw grade is the gain,
      so the metrics are grade-scale-agnostic.
    * **run** — ``{query_id: {clip_id: score}}`` — the system's scored results.

:func:`build_run` assigns strictly-descending integer scores in the search order,
so a run has **no score ties** and its ranking reproduces ``search()``'s
(already id-tiebroken) order exactly — the source of cross-platform determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import log2

#: The metrics reported by :func:`evaluate_run` (nDCG@10 is the sole PR gate).
DEFAULT_METRICS = ("ndcg@10", "recall@10", "map@10", "mrr@10")


def _ranked_ids(run_q: "dict[str, float]") -> "list[str]":
    """Doc ids of one query's run, best-first: score desc, ties broken by id asc.

    Deterministic and — because :func:`build_run` makes scores strictly
    descending and distinct — equal to the underlying ``search()`` order.
    """
    return sorted(run_q, key=lambda i: (-run_q[i], i))


def ndcg_at_k(
    qrels_q: "dict[str, int]", run_q: "dict[str, float]", k: int = 10
) -> float:
    """Normalized DCG at ``k`` with linear gains (0.0 when no graded answer)."""
    ranked = _ranked_ids(run_q)[:k]
    dcg = sum(qrels_q.get(i, 0) / log2(p + 2) for p, i in enumerate(ranked))
    ideal = sorted(qrels_q.values(), reverse=True)[:k]
    idcg = sum(g / log2(p + 2) for p, g in enumerate(ideal))
    return 0.0 if idcg == 0 else dcg / idcg


def _relevant(qrels_q: "dict[str, int]", rel_lvl: int) -> "set[str]":
    return {i for i, g in qrels_q.items() if g >= rel_lvl}


def recall_at_k(
    qrels_q: "dict[str, int]",
    run_q: "dict[str, float]",
    k: int = 10,
    *,
    rel_lvl: int = 1,
) -> float:
    """Fraction of ALL relevant docs (grade ≥ ``rel_lvl``) retrieved in the top-``k``."""
    rel = _relevant(qrels_q, rel_lvl)
    if not rel:
        return 0.0
    hits = sum(1 for i in _ranked_ids(run_q)[:k] if i in rel)
    return hits / len(rel)


def precision_at_k(
    qrels_q: "dict[str, int]",
    run_q: "dict[str, float]",
    k: int = 10,
    *,
    rel_lvl: int = 1,
) -> float:
    """Fraction of the top-``k`` that is relevant (denominator is literal ``k``)."""
    rel = _relevant(qrels_q, rel_lvl)
    hits = sum(1 for i in _ranked_ids(run_q)[:k] if i in rel)
    return hits / k


def average_precision_at_k(
    qrels_q: "dict[str, int]",
    run_q: "dict[str, float]",
    k: int = 10,
    *,
    rel_lvl: int = 1,
) -> float:
    """Average precision (trec_eval ``map``: divide by TOTAL relevant, not ``min(R,k)``)."""
    rel = _relevant(qrels_q, rel_lvl)
    if not rel:
        return 0.0
    hits = 0
    total = 0.0
    for p, i in enumerate(_ranked_ids(run_q)[:k]):
        if i in rel:
            hits += 1
            total += hits / (p + 1)
    return total / len(rel)


def mrr_at_k(
    qrels_q: "dict[str, int]",
    run_q: "dict[str, float]",
    k: int = 10,
    *,
    rel_lvl: int = 1,
) -> float:
    """Reciprocal rank of the first relevant doc in the top-``k`` (0.0 if none)."""
    rel = _relevant(qrels_q, rel_lvl)
    for p, i in enumerate(_ranked_ids(run_q)[:k]):
        if i in rel:
            return 1.0 / (p + 1)
    return 0.0


def mean_over_queries(values: "list[float]") -> float:
    """Macro-average of per-query metric values (0.0 for an empty list)."""
    return sum(values) / len(values) if values else 0.0


#: metric-name -> the callable computing it (``@k`` parsed off the name).
_METRIC_FNS = {
    "ndcg": ndcg_at_k,
    "recall": recall_at_k,
    "precision": precision_at_k,
    "map": average_precision_at_k,
    "mrr": mrr_at_k,
}


def _parse_metric(name: str) -> "tuple[str, int]":
    base, _, kstr = name.partition("@")
    return base, (int(kstr) if kstr else 10)


def build_run(candidates) -> "dict[str, float]":
    """Turn an ordered ``search()`` result into a run row with distinct scores.

    Assigns each candidate a strictly-descending integer score
    (``len - rank``) in the order returned, so the run carries **no score
    ties** and :func:`_ranked_ids` reproduces the search ranking exactly — the
    determinism the gate relies on. The doc id is ``candidate.sound.id``.

    Args:
        candidates: An ordered ``list[Candidate]`` from
            :meth:`foley.index.library.SoundLibrary.search` (best first).

    Returns:
        ``{clip_id: score}`` with distinct descending scores.
    """
    n = len(candidates)
    return {c.sound.id: float(n - rank) for rank, c in enumerate(candidates)}


@dataclass
class RetrievalReport:
    """Per-query + mean Tier-1 metrics over a golden set (JSON-friendly)."""

    per_query: "dict[str, dict[str, float]]" = field(default_factory=dict)
    mean: "dict[str, float]" = field(default_factory=dict)
    ranks: "dict[str, int]" = field(default_factory=dict)
    k: int = 10

    def format_regression_diff(self, baseline: dict) -> str:
        """A human diff for a failing gate: mean vs baseline + the worst queries."""
        metric = baseline.get("metric", "ndcg@10")
        cur = self.mean.get(metric, 0.0)
        base = baseline.get("value", 0.0)
        lines = [
            f"{metric}: current={cur:.4f} baseline={base:.4f} "
            f"floor={base - baseline.get('tolerance', 0.02):.4f} "
            f"Δ={cur - base:+.4f}",
            "worst queries (query_id: metric | rank-of-top-answer):",
        ]
        worst = sorted(self.per_query.items(), key=lambda kv: kv[1].get(metric, 0.0))
        for qid, m in worst[:8]:
            lines.append(
                f"  {qid}: {m.get(metric, 0.0):.4f} | rank={self.ranks.get(qid, '-')}"
            )
        return "\n".join(lines)


def evaluate_run(
    run: "dict[str, dict[str, float]]",
    qrels: "dict[str, dict[str, int]]",
    *,
    k: int = 10,
    metrics: "tuple[str, ...]" = DEFAULT_METRICS,
    rel_lvl: int = 1,
) -> RetrievalReport:
    """Score a ``run`` against ``qrels``, returning a :class:`RetrievalReport`.

    Only query ids present in ``qrels`` are scored (a run row without a
    ground-truth judgment is ignored). ``ranks`` records, per query, the 1-based
    rank of the highest-graded answer (for the failure diff).
    """
    report = RetrievalReport(k=k)
    for qid, qrels_q in qrels.items():
        run_q = run.get(qid, {})
        scores: "dict[str, float]" = {}
        for name in metrics:
            base, mk = _parse_metric(name)
            fn = _METRIC_FNS[base]
            scores[name] = (
                fn(qrels_q, run_q, mk, rel_lvl=rel_lvl)
                if base != "ndcg"
                else fn(qrels_q, run_q, mk)
            )
        report.per_query[qid] = scores
        report.ranks[qid] = _rank_of_top_answer(qrels_q, run_q)
    report.mean = {
        name: mean_over_queries([m[name] for m in report.per_query.values()])
        for name in metrics
    }
    return report


def _rank_of_top_answer(qrels_q: "dict[str, int]", run_q: "dict[str, float]") -> int:
    """1-based rank of the highest-graded answer clip in the run (0 = not found)."""
    if not qrels_q:
        return 0
    best_clip = max(qrels_q, key=lambda i: qrels_q[i])
    ranked = _ranked_ids(run_q)
    return ranked.index(best_clip) + 1 if best_clip in ranked else 0
