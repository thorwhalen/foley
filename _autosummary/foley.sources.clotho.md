# foley.sources.clotho

Clotho-eval — a captioned Ring-0 corpus that doubles as a retrieval fixture.

Clotho (report 11 §1.2 / §2.1) is an audio-captioning benchmark built from a
Freesound subset; its *evaluation* split is a Ring-0 seed corpus and a retrieval
fixture. Audio must be downloaded locally; this adapter only enumerates, licenses
and (optionally) captions it.

Rights are **per clip and per asset** (#68, report 14 §3.11):

* **Audio** keeps each file’s own Freesound licence, read from the `license`
  column of `clotho_metadata_*.csv` with its CC version (CC0, CC BY 3.0,
  CC BY-NC 3.0, Sampling+ in the eval split). A clip absent from the metadata, or
  under an unrecognised licence, fails closed (`unknown`, unverified). So no
  non-commercial clip passes [`foley.keep()`](foley.md#foley.keep) under commercial intent.
* **Captions** are licensed by Tampere University for **non-commercial use only**
  (not CC-BY 4.0, as report 11 said). They are therefore **not** put into the
  library’s keyword index by default: an index is not intent-aware at query time,
  and foley’s default intent is commercial. A non-commercial / eval-only library can
  opt in: `register_corpus(dataclasses.replace(CLOTHO, include_captions=True))`.

### Module Attributes

| [`CAPTION_LICENSE`](#foley.sources.clotho.CAPTION_LICENSE)   | it is never a sound's licence, only the reason captions stay out of a commercial index).   |
|--------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| [`CLOTHO`](#foley.sources.clotho.CLOTHO)            | The Clotho-eval Ring-0 adapter (audio licensed per clip; captions excluded).               |

### Classes

| [`ClothoEvalCorpus`](#foley.sources.clotho.ClothoEvalCorpus)(name, ring, ...[, ...])   | Ring-0 Clotho-eval adapter: per-clip Freesound licences; captions opt-in (NC).   |
|---------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|

### foley.sources.clotho.CAPTION_LICENSE *= 'Tampere-University-Clotho-captions (non-commercial only)'*

it is never a
sound’s licence, only the reason captions stay out of a commercial index).

* **Type:**
  What the caption text is licensed under (not a LICENSE_FLAGS row

### foley.sources.clotho.CLOTHO *= ClothoEvalCorpus(name='clotho', ring=0, default_license_id='CC-BY-4.0', source='clotho', rights_verified=True, tag_hints_from_path=False, include_captions=False)*

The Clotho-eval Ring-0 adapter (audio licensed per clip; captions excluded).

### *class* foley.sources.clotho.ClothoEvalCorpus(name, ring, default_license_id, source, rights_verified=True, tag_hints_from_path=False, include_captions=False)

Bases: [`UniformCorpus`](foley.sources.base.md#foley.sources.base.UniformCorpus)

Ring-0 Clotho-eval adapter: per-clip Freesound licences; captions opt-in (NC).

#### include_captions *: [bool](https://docs.python.org/3/builtins/functions.html#bool)* *= False*

Put the (non-commercial) human captions into the keyword index. Off by default.

#### iter_clips(root)

Yield clips carrying their per-file licence (and caption, when opted in).

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`ClipSpec`](foley.sources.base.md#foley.sources.base.ClipSpec)]

#### resolve_license(spec)

The clip’s own licence from its metadata row (`unknown` when absent).

* **Return type:**
  [`LicenseRecord`](foley.base.md#foley.base.LicenseRecord)
