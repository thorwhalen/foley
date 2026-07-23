"""Tests for the pure RRF fusion + hybrid-search orchestration (``foley.index.search``).

These need no optional dependencies — RRF is rank arithmetic. They pin the exact
fused scores (so a regression in the fusion constant or formula is caught) and
the determinism of the tie-break.
"""

from foley.index.search import (
    RRF_K,
    FusedHit,
    fuse_hits,
    hybrid_search,
    reciprocal_rank_fusion,
    vector_search,
)


# ---------------------------------------------------------------------------
# reciprocal_rank_fusion — the exact rank arithmetic
# ---------------------------------------------------------------------------


def test_rrf_single_list_scores_by_position():
    fused = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    assert fused == [
        ("a", 1 / 61),
        ("b", 1 / 62),
        ("c", 1 / 63),
    ]


def test_rrf_default_k_is_60():
    assert RRF_K == 60
    assert reciprocal_rank_fusion([["a"]]) == [("a", 1 / 61)]


def test_rrf_doc_in_both_lists_floats_up():
    # 'x' is rank-2 in both lists; 'a' and 'p' are each rank-1 in one list only.
    fused = reciprocal_rank_fusion([["a", "x"], ["p", "x"]], k=60)
    scores = dict(fused)
    assert scores["x"] == 1 / 62 + 1 / 62  # appears in both
    assert scores["a"] == 1 / 61
    assert fused[0][0] == "x"  # the doc both rankers agree on wins


def test_rrf_larger_k_flattens_but_preserves_order():
    small = reciprocal_rank_fusion([["a", "b", "c"]], k=10)
    large = reciprocal_rank_fusion([["a", "b", "c"]], k=1000)
    assert [i for i, _ in small] == [i for i, _ in large] == ["a", "b", "c"]
    assert large[0][1] < small[0][1]  # bigger k => smaller scores


def test_rrf_ties_break_by_id_ascending():
    # two singleton lists => both ids at rank 1 => equal score => id order decides
    fused = reciprocal_rank_fusion([["b"], ["a"]], k=60)
    assert fused == [("a", 1 / 61), ("b", 1 / 61)]


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


# ---------------------------------------------------------------------------
# fuse_hits — carries the component scores, truncates to k
# ---------------------------------------------------------------------------


def test_fuse_hits_carries_component_scores():
    vhits = [("a", 0.9), ("b", 0.5)]
    khits = [("b", 3.2), ("c", 1.0)]
    hits = fuse_hits(vhits, khits, k=10)
    by_id = {h.id: h for h in hits}
    assert by_id["a"].clap_score == 0.9 and by_id["a"].bm25_score is None
    assert by_id["c"].bm25_score == 1.0 and by_id["c"].clap_score is None
    assert by_id["b"].clap_score == 0.5 and by_id["b"].bm25_score == 3.2
    # 'b' is in both lists => highest fused score => first
    assert hits[0].id == "b"


def test_fuse_hits_truncates_to_k():
    vhits = [("a", 1.0), ("b", 0.9), ("c", 0.8)]
    khits = [("d", 1.0)]
    hits = fuse_hits(vhits, khits, k=2)
    assert len(hits) == 2
    assert all(isinstance(h, FusedHit) for h in hits)


# ---------------------------------------------------------------------------
# hybrid_search / vector_search — orchestration over fakes
# ---------------------------------------------------------------------------


class _StubEmbedder:
    model_id = "stub"
    dim = 3

    def embed_text(self, text):
        return [[1.0, 0.0, 0.0]]  # 2-D, one row


class _StubVIndex:
    def knn(self, vector, k, *, where=None):
        return [("a", 0.99), ("b", 0.80)][:k]


class _StubKIndex:
    def bm25(self, query, k, *, where=None):
        return [("b", 4.1), ("c", 2.0)][:k]


def test_hybrid_search_embeds_then_fuses():
    hits = hybrid_search(
        "anything",
        embedder=_StubEmbedder(),
        vindex=_StubVIndex(),
        kindex=_StubKIndex(),
        k=3,
    )
    ids = [h.id for h in hits]
    assert ids[0] == "b"  # only doc in both rankers
    assert set(ids) == {"a", "b", "c"}


def test_vector_search_preserves_order_and_has_no_bm25():
    hits = vector_search([1.0, 0.0, 0.0], vindex=_StubVIndex(), k=2)
    assert [h.id for h in hits] == ["a", "b"]
    assert hits[0].clap_score == 0.99
    assert all(h.bm25_score is None and h.rrf_score is None for h in hits)
