"""Tests for the vector+keyword index backends (``foley.index.indexes``).

A single shared test body runs against every backend available in the env
(``MemoryIndex`` always; ``LanceIndex`` when lancedb is installed;
``SqliteVecIndex`` when sqlite-vec is loadable) — so the protocol contract is
verified identically across tiers. Backend-specific behaviours (LanceDB staged
writes, the default-backend ladder) get their own focused tests.
"""

import pytest

np = pytest.importorskip("numpy")

from foley.index.indexes import (  # noqa: E402
    LanceIndex,
    MemoryIndex,
    SqliteVecIndex,
    default_index,
    lancedb_available,
    sqlite_vec_loadable,
)

_DIM = 8


def _rvec(seed: int, dim: int = _DIM):
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


_DOCS = {
    "s1": ("dog barking loudly in the yard", _rvec(11)),
    "s2": ("cat meowing softly indoors", _rvec(22)),
    "s3": ("heavy wooden door creaking open", _rvec(33)),
    "s4": ("rain on a window pane", _rvec(44)),
}


# ---------------------------------------------------------------------------
# shared contract — runs on every available backend
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "lance", "sqlitevec"])
def backend(request, tmp_path):
    name = request.param
    if name == "lance":
        if not lancedb_available():
            pytest.skip("lancedb not installed")
        return LanceIndex(uri=str(tmp_path / "lance"), dim=_DIM)
    if name == "sqlitevec":
        if not sqlite_vec_loadable():
            pytest.skip("sqlite-vec not loadable in this interpreter")
        return SqliteVecIndex(path=str(tmp_path / "idx.db"), dim=_DIM)
    return MemoryIndex(dim=_DIM)


def _populate(index):
    for sid, (text, vec) in _DOCS.items():
        index.upsert(sid, vec, {"id": sid})
        index.index(sid, text, {"id": sid})


def test_empty_reads(backend):
    assert backend.knn(_rvec(1), 5) == []
    assert backend.bm25("dog", 5) == []
    assert backend.get_vector("missing") is None


def test_knn_returns_nearest_first(backend):
    _populate(backend)
    hits = backend.knn(_DOCS["s3"][1], 3)
    assert hits[0][0] == "s3"
    assert hits[0][1] > 0.99  # cosine similarity of a vector with itself ~1.0
    # scores are descending
    scores = [s for _, s in hits]
    assert scores == sorted(scores, reverse=True)


def test_bm25_finds_keyword_match(backend):
    _populate(backend)
    hits = backend.bm25("door creaking", 3)
    assert hits and hits[0][0] == "s3"


def test_get_vector_roundtrip(backend):
    _populate(backend)
    got = backend.get_vector("s3")
    assert got is not None
    assert np.allclose(got, _DOCS["s3"][1], atol=1e-5)


def test_upsert_replaces_without_duplicating(backend):
    _populate(backend)
    new_vec = _rvec(99)
    backend.upsert("s3", new_vec, {"id": "s3"})
    backend.index("s3", "updated thunderstorm rumble", {"id": "s3"})
    # the updated vector is what comes back
    assert np.allclose(backend.get_vector("s3"), new_vec, atol=1e-5)
    # and the new text is searchable, exactly one hit for the unique term
    hits = backend.bm25("thunderstorm", 5)
    assert [h[0] for h in hits] == ["s3"]


def test_dim_mismatch_raises(backend):
    with pytest.raises(ValueError):
        backend.upsert("bad", np.zeros(_DIM + 1, dtype=np.float32), {})


# ---------------------------------------------------------------------------
# MemoryIndex specifics
# ---------------------------------------------------------------------------


def test_memory_infers_dim_from_first_upsert():
    idx = MemoryIndex()
    idx.upsert("a", _rvec(1, dim=5), {})
    assert idx.dim == 5


def test_memory_bm25_ranks_by_relevance():
    idx = MemoryIndex(dim=_DIM)
    idx.index("a", "rain rain rain heavy", {})
    idx.index("b", "a single mention of rain", {})
    hits = idx.bm25("rain", 2)
    assert [h[0] for h in hits] == ["a", "b"]  # denser term freq ranks first


def test_memory_knn_tiebreak_is_deterministic_by_id():
    # two identical vectors under different ids => tied cosine => id-order decides
    idx = MemoryIndex(dim=_DIM)
    shared = _rvec(5)
    idx.upsert("z_last", shared, {})
    idx.upsert("a_first", shared, {})
    hits = idx.knn(shared, 2)
    assert [h[0] for h in hits] == ["a_first", "z_last"]  # not numpy sort order


# ---------------------------------------------------------------------------
# LanceIndex specifics (staged writes)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not lancedb_available(), reason="lancedb not installed")
def test_lance_get_vector_from_pending_before_flush(tmp_path):
    idx = LanceIndex(uri=str(tmp_path / "lance"), dim=_DIM)
    v = _rvec(7)
    idx.upsert("p1", v, {})  # staged, not flushed
    assert np.allclose(idx.get_vector("p1"), v, atol=1e-5)


@pytest.mark.skipif(not lancedb_available(), reason="lancedb not installed")
def test_lance_commit_persists(tmp_path):
    uri = str(tmp_path / "lance")
    idx = LanceIndex(uri=uri, dim=_DIM)
    _populate(idx)
    idx.commit()
    # a fresh handle over the same uri sees the data
    reopened = LanceIndex(uri=uri, dim=_DIM)
    assert reopened.get_vector("s1") is not None
    assert reopened.bm25("door", 3)[0][0] == "s3"


# ---------------------------------------------------------------------------
# capability probes + default backend ladder
# ---------------------------------------------------------------------------


def test_capability_probes_are_bool():
    assert isinstance(lancedb_available(), bool)
    assert isinstance(sqlite_vec_loadable(), bool)


@pytest.mark.skipif(not lancedb_available(), reason="lancedb not installed")
def test_default_index_prefers_lancedb(tmp_path):
    idx = default_index(data_dir=tmp_path, dim=_DIM)
    assert isinstance(idx, LanceIndex)


def test_default_index_raises_when_no_backend(tmp_path, monkeypatch):
    import foley.index.indexes as ix

    monkeypatch.setattr(ix, "lancedb_available", lambda: False)
    monkeypatch.setattr(ix, "sqlite_vec_loadable", lambda: False)
    with pytest.raises(RuntimeError, match="No persistent index backend"):
        ix.default_index(data_dir=tmp_path, dim=_DIM)
