# foley.eval.embedder

A deterministic, numpy-only text embedder for the retrieval eval gate.

[`HashingBowEmbedder`](#foley.eval.embedder.HashingBowEmbedder) is a hashing bag-of-words text embedder — the
shippable sibling of the test suite’s `FakeEmbedder`. It exists so the nDCG PR
gate is **deterministic and CLAP-free**: unlike `FakeEmbedder`’s random
`embed_audio` (whose content-noise vectors make RRF rankings platform-dependent
— the flakiness documented in `tests/test_bootstrap.py`), the eval harness
*injects* `embed_text(caption + tags)` as each clip’s vector, so both search
legs (vector cosine and BM25) carry the same caption bag-of-words. Every golden
query then shares 2–3 tokens with its answer clip → integer rank-1 in both legs →
a bit-exact, cross-platform-stable nDCG.

It is a text-only embedder: `embed_audio` is intentionally unimplemented (the
gate never calls it — vectors are injected via
[`foley.index.library.SoundLibrary.add()`](foley.index.library.html.md#foley.index.library.SoundLibrary.add)).

### Module Attributes

| [`DEFAULT_DIM`](#foley.eval.embedder.DEFAULT_DIM)   | Default embedding width (matches the test `FakeEmbedder` for parity).   |
|----------------------------------------------------------------|-------------------------------------------------------------------------|

### Classes

| [`HashingBowEmbedder`](#foley.eval.embedder.HashingBowEmbedder)(\*[, dim])   | Deterministic hashing bag-of-words text embedder (L2-normalized).   |
|----------------------------------------------------------------------------------|---------------------------------------------------------------------|

### foley.eval.embedder.DEFAULT_DIM *= 64*

Default embedding width (matches the test `FakeEmbedder` for parity).

### *class* foley.eval.embedder.HashingBowEmbedder(, dim=64)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Deterministic hashing bag-of-words text embedder (L2-normalized).

Two texts sharing a token share a dimension, so cosine similarity tracks
lexical overlap — plausible *and* reproducible (a stable `hashlib` hash,
never the salted builtin `hash`). Suitable only for the eval gate /
offline retrieval regression; real retrieval uses CLAP.

#### embed_text(text)

Embed `text` (or a list of texts) -> a `(n, dim)` float32 array.
