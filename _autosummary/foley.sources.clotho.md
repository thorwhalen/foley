# foley.sources.clotho

Clotho-eval — a captioned Ring-0 corpus that doubles as a retrieval fixture.

Clotho (report 11 §1.2 / §2.1) is an audio-captioning benchmark built from a
redistributable Freesound subset; its *evaluation* split is a clean Ring-0 seed
corpus **and** the retrieval regression fixture #10a scores against. Each clip
ships five human captions — real descriptive text — which this adapter injects so
they flow through the normal ingest pipeline into the BM25 keyword index (no
special-casing).

Licensing is uniform `CC-BY-4.0` (a conservative, attributable stamp over the
redistributable-subset guarantee — if a clip is actually CC0 we merely
over-attribute, never under-attribute). Audio must be downloaded locally; this
adapter only enumerates + captions + licenses it.

### Module Attributes

| [`CLOTHO`](#foley.sources.clotho.CLOTHO)   | The Clotho-eval Ring-0 adapter.   |
|-----------------------------------------------------------|-----------------------------------|

### Classes

| [`ClothoEvalCorpus`](#foley.sources.clotho.ClothoEvalCorpus)(name, ring, ...[, ...])   | Ring-0 Clotho-eval adapter: uniform CC-BY + injected human captions.   |
|---------------------------------------------------------------------------------------------|------------------------------------------------------------------------|

### foley.sources.clotho.CLOTHO *= ClothoEvalCorpus(name='clotho', ring=0, default_license_id='CC-BY-4.0', source='clotho', rights_verified=True, tag_hints_from_path=False)*

The Clotho-eval Ring-0 adapter.

### *class* foley.sources.clotho.ClothoEvalCorpus(name, ring, default_license_id, source, rights_verified=True, tag_hints_from_path=False)

Bases: [`UniformCorpus`](foley.sources.base.md#foley.sources.base.UniformCorpus)

Ring-0 Clotho-eval adapter: uniform CC-BY + injected human captions.

#### iter_clips(root)

Yield clips with their human caption attached in `meta['caption']`.

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`ClipSpec`](foley.sources.base.md#foley.sources.base.ClipSpec)]
