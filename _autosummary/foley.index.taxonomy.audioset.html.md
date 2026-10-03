# foley.index.taxonomy.audioset

AudioSet-label -> UCS-CatID overlap map (report 04 §5.3, [11 §3.1]).

The machine-label layer (PANNs/PaSST emit AudioSet labels on ingest) is bridged
to the human-facing UCS browse tree by a small overlap map. This is the
conceptual seed of the EnvSound-UCS “Rosetta stone”; the full table drops in as
`taxonomy/data/audioset_ucs.json` and merges over the seed. Every target CatID
is validated against the UCS table at load time (fail-fast on a broken map).

### Functions

| [`default_audioset_ucs_map`](#foley.index.taxonomy.audioset.default_audioset_ucs_map)()                        | The process-wide default AudioSet->UCS map (seed + any JSON drop).   |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| [`load_audioset_ucs_map`](#foley.index.taxonomy.audioset.load_audioset_ucs_map)(\*[, data_dir, table, ...]) | Build the AudioSet(name|MID) -> UCS-CatID map.                       |

### foley.index.taxonomy.audioset.default_audioset_ucs_map()

The process-wide default AudioSet->UCS map (seed + any JSON drop).

* **Return type:**
  [`AudioSetUcsMap`](foley.index.taxonomy.model.html.md#foley.index.taxonomy.model.AudioSetUcsMap)

### foley.index.taxonomy.audioset.load_audioset_ucs_map(, data_dir=None, table=None, include_seed=True)

Build the AudioSet(name|MID) -> UCS-CatID map.

* **Parameters:**
  * **data_dir** – Directory to look for `audioset_ucs.json` in (defaults to the
    package’s `taxonomy/data/`); merged over the seed when present.
  * **table** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`UcsTable`](foley.index.taxonomy.model.html.md#foley.index.taxonomy.model.UcsTable)]) – The UCS table every target CatID must exist in (defaults to
    [`default_ucs_table()`](foley.index.taxonomy.ucs.html.md#foley.index.taxonomy.ucs.default_ucs_table)).
  * **include_seed** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Start from the in-code seed map (default `True`).
* **Return type:**
  [`AudioSetUcsMap`](foley.index.taxonomy.model.html.md#foley.index.taxonomy.model.AudioSetUcsMap)
* **Returns:**
  A ready [`AudioSetUcsMap`](foley.index.taxonomy.model.html.md#foley.index.taxonomy.model.AudioSetUcsMap).
* **Raises:**
  [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If any entry targets a CatID absent from `table`.
