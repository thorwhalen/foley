# foley.sources.fsd50k

FSD50K — the labeled, commercial-safe backbone corpus (Ring 1).

FSD50K (report 11 §1.1, Zenodo 4060432) is ~51 k Freesound clips with AudioSet
labels. Its *compilation* is CC-BY-4.0, but \*\*each clip carries its own Freesound
license\*\* (CC0 / CC-BY / CC-BY-NC / Sampling+), so licensing is resolved
**per-clip** from the shipped metadata, not stamped uniformly. The bootstrap
Ring-1 policy then drops the non-commercial slice (CC-BY-NC / Sampling+) via the
fail-closed commercial filter, keeping the ~85 % CC0/CC-BY backbone.

Per-clip metadata lives in the FSD50K `*_clips_info_FSD50K.json` files
(`{fname: {title, description, tags, license, uploader, ...}}`) where `license`
is a Creative-Commons URL. This adapter reads those, maps the URL to a foley
`license_id`, and fails closed (`license_id='unknown'`, `rights_verified=
False`) for any clip whose license is missing or unrecognized — such clips are
then dropped by [`foley.keep()`](foley.md#foley.keep). The bytes are a Zenodo bulk download, so
they are cacheable (`cache_bytes_ok=True`, stored by-value) — do NOT copy #5’s
Freesound-*API* `cache_bytes_ok=False` override.

#### NOTE
The exact metadata filename/columns are per the published FSD50K layout; if a
future release moves them, this adapter degrades to fail-closed rather than
guessing. Verify against the real download when wiring the fetch (#4 ships the
local-dir ingestion; auto-download is a fast-follow).

### Module Attributes

| [`FSD50K`](#foley.sources.fsd50k.FSD50K)   | The FSD50K Ring-1 adapter.   |
|-----------------------------------------------------------|------------------------------|

### Classes

| [`Fsd50kCorpus`](#foley.sources.fsd50k.Fsd50kCorpus)()   | Ring-1 FSD50K adapter with per-clip Freesound license resolution.   |
|-------------------------------------------------------------------|---------------------------------------------------------------------|

### foley.sources.fsd50k.FSD50K *= <foley.sources.fsd50k.Fsd50kCorpus object>*

The FSD50K Ring-1 adapter.

### *class* foley.sources.fsd50k.Fsd50kCorpus

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Ring-1 FSD50K adapter with per-clip Freesound license resolution.

#### corpus_dir(data_dir)

`data_dir/fsd50k` — the conventional on-disk root.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### iter_clips(root)

Yield a clip per audio file, carrying its per-clip license metadata.

Each clip’s `meta` gets `{license_id, rights_verified, creator_name,
source_url}` resolved from the FSD50K clips-info JSON (fail-closed when a
clip is absent from the metadata).

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`ClipSpec`](foley.sources.base.md#foley.sources.base.ClipSpec)]

#### resolve_license(spec)

Build the per-clip rights record from the metadata in `spec.meta`.

* **Return type:**
  [`LicenseRecord`](foley.base.md#foley.base.LicenseRecord)
