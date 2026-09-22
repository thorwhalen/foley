# foley.sources.pull

`add_from` — the live-source pull façade (SOURCE → INDEX in one call).

The live analog of `foley.bootstrap.bootstrap()`’s per-corpus ingest loop:
resolve a registered live [`SourceAdapter`](foley.sources.base.html.md#foley.sources.base.SourceAdapter), search it
(with the license filter pushed into the query), gate each hit through the
fail-closed [`foley.keep()`](foley.html.md#foley.keep) license check, fetch its (transient) bytes, and run
them through the SAME [`foley.index.ingest.ingest_one()`](foley.index.ingest.html.md#foley.index.ingest.ingest_one) pipeline the local and
bulk paths use — so decode / QC / embed / tag / store are **not forked**.

For Freesound this stores every sound BY-REFERENCE (`cache_bytes_ok=False`): the
transient preview bytes are embedded once, then discarded; only the stable URI +
provenance + the CLAP vector persist. The audio is re-fetched on demand via the
adapter (there is no local blob to serve — `library.audio(id)` raises for a
remote by-reference sound; that is the contract).

### Module Attributes

| [`DEFAULT_INTENDED_USE`](#foley.sources.pull.DEFAULT_INTENDED_USE)   | a publishable, commercial, attributable use — the same fail-closed bar `foley.bootstrap.bootstrap()`'s Ring-1 filter applies.   |
|-------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|

### Functions

| [`add_from`](#foley.sources.pull.add_from)(source, \*, query[, license, limit, ...])   | Search a live `source` and ingest its license-clean hits into `library`.   |
|-------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|

### foley.sources.pull.DEFAULT_INTENDED_USE *= IntendedUse(commercial=True, publish=True, redistribute_standalone=False, will_train=False, can_attribute=True, revenue_usd=0, allow_voice_or_trademark=False)*

a publishable, commercial, attributable use — the
same fail-closed bar `foley.bootstrap.bootstrap()`’s Ring-1 filter applies.

* **Type:**
  Default intent for a pull

### foley.sources.pull.add_from(source, , query, license='cc0', limit=50, library=None, intended_use=None, adapter=None, \*\*affordances)

Search a live `source` and ingest its license-clean hits into `library`.

Progressive disclosure: `add_from("freesound", query="ocean waves")` works out
of the box (CC0-only, into the process-wide default library); every other knob
is an optional keyword. Each hit is license-gated BEFORE any bytes are fetched
(fail-closed), then routed through [`ingest_one()`](foley.index.ingest.html.md#foley.index.ingest.ingest_one), which
applies the by-reference storage gate from the sound’s own license.

* **Parameters:**
  * **source** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A registered live-source name (e.g. `'freesound'`).
  * **query** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The natural-language search query.
  * **license** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – License constraint pushed into the source query (default
    `'cc0'`). The per-item fail-closed guard enforces the source’s
    accepted-license allowlist regardless.
  * **limit** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Max candidates to request from the source.
  * **library** – Target [`SoundLibrary`](foley.index.library.html.md#foley.index.library.SoundLibrary) (default: the
    process-wide default library).
  * **intended_use** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`IntendedUse`](foley.base.html.md#foley.base.IntendedUse)]) – The rights intent each candidate is gated against (default:
    [`DEFAULT_INTENDED_USE`](#foley.sources.pull.DEFAULT_INTENDED_USE)).
  * **adapter** – An optional pre-built adapter to use instead of the registry’s
    (the dependency-injection seam — a test passes a fake-transport
    adapter; production omits it and the registry lazily builds one).
  * **\*\*affordances** – Extra unified affordances forwarded to the adapter’s
    `search` (e.g. `duration_range`, `sort`).
* **Return type:**
  [`IngestReport`](foley.index.ingest.html.md#foley.index.ingest.IngestReport)
* **Returns:**
  An [`IngestReport`](foley.index.ingest.html.md#foley.index.ingest.IngestReport) — inspect `.ingested` for the
  stored records (each `storage_mode == by_reference` for Freesound) and
  `.summary()` for counts, exactly like [`foley.ingest()`](foley.html.md#foley.ingest).
