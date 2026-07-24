"""Opt-in oracle: foley's pure-numpy metrics == ranx, over random graded trials.

This is the guarantee that lets foley hand-roll its IR metrics (report 08 §1.2
"don't hand-roll IR metrics") without shipping ranx/numba into CI: the shipped
metrics are proven bit-equal to ranx here, and this test is SKIPPED in CI
(``ranx`` is not in the ``test`` extra) — it runs only where ``foley[eval]`` is
installed. Doc pools are kept ≤ 10 so ``mrr`` and ``mrr@10`` coincide.
"""

import pytest

np = pytest.importorskip("numpy")
ranx = pytest.importorskip("ranx")

from foley.eval.retrieval import (  # noqa: E402
    average_precision_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)

_N_TRIALS = 300
_MAX_DOCS = 10
_MAX_GRADE = 3


def _random_case(rng):
    """One (qrels_q, run_q) with distinct scores and graded (0..3) judgments."""
    n_docs = int(rng.integers(2, _MAX_DOCS + 1))
    docs = [f"d{i}" for i in range(n_docs)]
    # distinct scores (a permutation) so there are no ties to disagree on
    scores = list(rng.permutation(n_docs).astype(float))
    run_q = dict(zip(docs, scores))
    n_rel = int(rng.integers(1, n_docs))  # at least one relevant
    rel_docs = list(rng.choice(docs, size=n_rel, replace=False))
    qrels_q = {d: int(rng.integers(1, _MAX_GRADE + 1)) for d in rel_docs}
    return qrels_q, run_q


def test_metrics_match_ranx_over_random_trials():
    rng = np.random.default_rng(20260724)
    qrels_all, run_all = {}, {}
    # key our per-query scores BY qid — ranx.evaluate(return_mean=False) returns
    # per-query scores in ranx's own (lexicographically-sorted) qid order, NOT
    # dict-insertion order, so the two sequences must be aligned by qid.
    ours = {"ndcg@10": {}, "map@10": {}, "recall@10": {}, "mrr": {}}
    for t in range(_N_TRIALS):
        q, r = _random_case(rng)
        qid = f"q{t}"
        qrels_all[qid], run_all[qid] = q, r
        ours["ndcg@10"][qid] = ndcg_at_k(q, r, 10)
        ours["map@10"][qid] = average_precision_at_k(q, r, 10)
        ours["recall@10"][qid] = recall_at_k(q, r, 10)
        ours["mrr"][qid] = mrr_at_k(q, r, 10)

    qrels = ranx.Qrels.from_dict(qrels_all)
    run = ranx.Run.from_dict(run_all)
    qids = list(qrels.qrels.keys())  # ranx's own per-query ordering
    for metric in ("ndcg@10", "map@10", "recall@10", "mrr"):
        theirs = np.asarray(ranx.evaluate(qrels, run, metric, return_mean=False))
        mine = np.asarray([ours[metric][qid] for qid in qids])
        max_diff = float(np.max(np.abs(mine - theirs)))
        assert max_diff < 1e-9, f"{metric}: max|foley-ranx|={max_diff}"
