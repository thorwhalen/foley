"""Tests for Tier-1 retrieval eval + the nDCG PR gate (``foley.eval``).

Two layers: (1) the METRICS as pure functions, checked against hand-computed and
ranx-verified values (the numpy-free safety net that lets us hand-roll the metrics
instead of shipping ranx into CI); (2) the GATE — the deterministic Ring-0 harness
+ the regression assert. numpy (a test-extra) backs the harness/library.
"""

import warnings
from math import log2

import pytest

pytest.importorskip("numpy")

from foley.eval import (  # noqa: E402
    average_precision_at_k,
    build_run,
    evaluate_run,
    load_baseline,
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from foley.eval.baseline import is_stale  # noqa: E402
from foley.eval.golden import (  # noqa: E402
    DEFAULT_GOLDEN_PATH,
    RING0_MANIFEST_PATH,
    build_eval_library,
    load_golden,
    run_ring0_retrieval_eval,
    to_qrels,
)

# ---------------------------------------------------------------------------
# metric units — hand-computed / ranx-verified
# ---------------------------------------------------------------------------


def test_ndcg_linear_gain_matches_ranx_oracle():
    # The exact value ranx 0.3.21 "ndcg@10" + pytrec_eval ndcg_cut_10 produce.
    qrels = {"a": 3, "b": 2, "c": 1}
    run = {"a": 0.9, "c": 0.8, "b": 0.7, "z": 0.6}
    assert ndcg_at_k(qrels, run, 10) == pytest.approx(0.9725044904464192, abs=1e-15)


def test_ndcg_single_answer_rank_positions():
    # single graded answer at rank 1 -> 1.0 exactly; at rank 2 -> 1/log2(3)
    assert ndcg_at_k({"a": 2}, {"a": 2.0, "b": 1.0}, 10) == 1.0
    assert ndcg_at_k({"a": 2}, {"b": 2.0, "a": 1.0}, 10) == pytest.approx(1 / log2(3))


def test_ndcg_no_relevant_is_zero():
    assert ndcg_at_k({}, {"a": 1.0}, 10) == 0.0


def test_ndcg_penalizes_acceptable_above_ideal():
    # graded discrimination (not MRR-in-disguise): ranking the acceptable(1) clip
    # ABOVE the ideal(2) one must score strictly worse than the correct order.
    qrels = {"ideal": 2, "ok": 1}
    correct = ndcg_at_k(qrels, {"ideal": 2.0, "ok": 1.0}, 10)
    swapped = ndcg_at_k(qrels, {"ok": 2.0, "ideal": 1.0}, 10)
    assert correct == 1.0
    assert swapped < correct


def test_recall_denominator_is_all_relevant():
    qrels = {"a": 1, "b": 1}  # 2 relevant
    assert recall_at_k(qrels, {"a": 2.0, "x": 1.0}, 10) == 0.5  # 1 of 2 in top-k
    assert recall_at_k({}, {"a": 1.0}, 10) == 0.0
    # R > k: denominator is ALL relevant (12), not min(R, k) — 10/12, not 1.0
    many = {f"d{i}": 1 for i in range(12)}
    ranked = {f"d{i}": float(12 - i) for i in range(12)}
    assert recall_at_k(many, ranked, 10) == pytest.approx(10 / 12)


def test_precision_is_hits_over_literal_k():
    assert precision_at_k({"a": 1}, {"a": 3.0, "b": 2.0, "c": 1.0}, 2) == 0.5


def test_average_precision_uses_total_relevant():
    # relevant at ranks 1 and 3, R=2 -> (1/1 + 2/3)/2
    qrels = {"a": 1, "c": 1}
    run = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert average_precision_at_k(qrels, run, 10) == pytest.approx((1.0 + 2 / 3) / 2)
    assert average_precision_at_k({}, run, 10) == 0.0
    # R > k: divide by TOTAL relevant (12), trec_eval convention -> 10/12, not 1.0
    many = {f"d{i}": 1 for i in range(12)}
    ranked = {f"d{i}": float(12 - i) for i in range(12)}
    assert average_precision_at_k(many, ranked, 10) == pytest.approx(10 / 12)


def test_mrr_truncates_at_k():
    assert mrr_at_k({"a": 1}, {"x": 3.0, "y": 2.0, "a": 1.0}, 10) == pytest.approx(1 / 3)
    # first relevant past the cutoff -> 0.0 (truncated mrr@k, not uncapped)
    run = {f"d{i}": float(20 - i) for i in range(15)}
    run["a"] = 0.0
    assert mrr_at_k({"a": 1}, run, 10) == 0.0


def test_build_run_yields_distinct_descending_scores():
    class _C:
        def __init__(self, id_):
            self.sound = type("S", (), {"id": id_})()

    run = build_run([_C("x"), _C("y"), _C("z")])
    assert run == {"x": 3.0, "y": 2.0, "z": 1.0}
    # _ranked_ids reproduces the search order
    from foley.eval.retrieval import _ranked_ids

    assert _ranked_ids(run) == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# the golden harness + THE GATE
# ---------------------------------------------------------------------------


def test_build_eval_library_uses_stable_stem_ids():
    lib = build_eval_library()
    ids = set(lib)
    assert len(ids) == 6
    assert all(i.startswith("ring0:") for i in ids)
    # qrels join 1:1 with the library (guards the content-hash id-keyspace trap)
    qrels = to_qrels(load_golden())
    qrels_clips = {c for q in qrels.values() for c in q}
    assert qrels_clips <= ids


def test_ring0_eval_is_deterministic_across_runs():
    a = run_ring0_retrieval_eval(k=10)
    b = run_ring0_retrieval_eval(k=10)
    assert a.mean == b.mean
    assert a.per_query == b.per_query


def test_ndcg_at_10_regression_gate():
    # THE PR GATE. Runs the real SoundLibrary.search path over the Ring-0 golden
    # set and blocks a change whose nDCG@10 falls > 0.02 below the committed
    # baseline. Deterministic + CLAP-free + no downloads (the whole design point).
    report = run_ring0_retrieval_eval(k=10)
    baseline = load_baseline()
    current = report.mean["ndcg@10"]
    floor = baseline["value"] - baseline["tolerance"]
    assert current >= floor, report.format_regression_diff(baseline)
    # advisory: an improvement should ratchet the baseline (never a hard fail)
    if current > baseline["value"] + baseline["tolerance"]:
        warnings.warn(
            "nDCG@10 improved above the baseline — run `foley eval --update-baseline`.",
            stacklevel=1,
        )


def test_gate_would_catch_a_rank_regression():
    # Prove the gate has teeth: a regression that drops every answer clip from
    # rank-1 to rank-2 collapses nDCG@10 to 1/log2(3) ≈ 0.63, far below the
    # ~0.98 floor — so the gate WOULD fail (this is why the tripwire is useful).
    qrels = to_qrels(load_golden())
    regressed = {}
    for qid, q in qrels.items():
        answer = max(q, key=lambda i: q[i])
        regressed[qid] = {"distractor": 2.0, answer: 1.0}  # answer demoted to rank 2
    report = evaluate_run(regressed, qrels, k=10)
    baseline = load_baseline()
    floor = baseline["value"] - baseline["tolerance"]
    assert report.mean["ndcg@10"] < floor


def test_baseline_matches_current_on_this_platform_exactly():
    # The exact-1.0 design: with the injected semantic vectors every answer clip
    # is integer rank-1, so nDCG@10 == 1.0 bit-exactly on every platform.
    report = run_ring0_retrieval_eval(k=10)
    assert report.mean["ndcg@10"] == 1.0


def test_baseline_stamps_match_committed_fixtures():
    # If this fails, the seed/manifest changed without re-baselining.
    baseline = load_baseline()
    assert not is_stale(
        baseline, seed_path=DEFAULT_GOLDEN_PATH, manifest_path=RING0_MANIFEST_PATH
    ), "baseline stale: run `foley eval --update-baseline` and commit the diff"
