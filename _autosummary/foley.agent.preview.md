# foley.agent.preview

Audition UX — preview a sound, find similar ones, and refine by relevance feedback (#12).

The interactive/agentic layer over the existing retrieval engine, all thin over
[`foley.index.SoundLibrary`](foley.index.md#foley.index.SoundLibrary):

* [`preview()`](#foley.agent.preview.preview) — synthesize a short audition clip for a sound and reference it by a
  **store key** (never raw bytes over the wire); degrades to `preview_uri=None` when
  the audio codec extra is absent.
* [`similar_to()`](#foley.agent.preview.similar_to) — “more like this”: `sound_id` / [`Candidate`](foley.base.md#foley.base.Candidate)
  → by-id neighbours (`SoundLibrary.similar`), or a raw clip → audio-to-audio search
  (`SoundLibrary.search_clip`). A NEW clip/candidate-in entrypoint, distinct from the
  existing by-id `SoundLibrary.similar`.
* [`refine()`](#foley.agent.preview.refine) — TRUE relevance feedback (distinct from the query-paraphrase
  [`foley.refine_query()`](foley.md#foley.refine_query)): expand the query for recall, pull neighbours of the
  > session’s **picks**, drop its **rejects**, and re-rank.

Dol-only core (numpy/soundfile only inside [`preview()`](#foley.agent.preview.preview)’s encode path).

### Module Attributes

| [`PREVIEW_SECONDS`](#foley.agent.preview.PREVIEW_SECONDS)   | Default audition length (seconds).   |
|--------------------------------------------------------------------|--------------------------------------|

### Functions

| [`preview`](#foley.agent.preview.preview)(candidate_or_id, \*[, seconds, ...])    | Produce a short audition of a sound; set its `preview_uri` to a store key.            |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`refine`](#foley.agent.preview.refine)([session, query, picked_ids, ...])       | Relevance-feedback refinement: expand for recall, boost picks, drop rejects, re-rank. |
| [`similar_to`](#foley.agent.preview.similar_to)(clip_or_candidate, \*[, k, library]) | "More like this" — neighbours of a sound id / candidate, or of a raw clip.            |

### Classes

| [`RefineResult`](#foley.agent.preview.RefineResult)(queries, results)   | The output of [`refine()`](#foley.agent.preview.refine): the expanded queries and the re-ranked candidates.   |
|-----------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|

### foley.agent.preview.PREVIEW_SECONDS *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 6*

Default audition length (seconds).

### *class* foley.agent.preview.RefineResult(queries, results)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The output of [`refine()`](#foley.agent.preview.refine): the expanded queries and the re-ranked candidates.

### foley.agent.preview.preview(candidate_or_id, , seconds=6, library=None, byte_store=None, session=None)

Produce a short audition of a sound; set its `preview_uri` to a store key.

Writes the first `seconds` of the clip (FLAC) into `byte_store` under its
content key and points `Candidate.preview_uri` at that key — referencing the
audio, never returning bytes. Fail-safe: if the audio codec extra (`foley[audio]`)
or the clip is unavailable, `preview_uri` is `None` (the sound id + duration
still let a client fetch it).

* **Parameters:**
  * **candidate_or_id** – A [`Candidate`](foley.base.md#foley.base.Candidate) or a sound id.
  * **seconds** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Audition length.
  * **library** – The [`foley.index.SoundLibrary`](foley.index.md#foley.index.SoundLibrary) (default: the shared one).
  * **byte_store** – A `MutableMapping[str, bytes]` to hold the preview (default: none —
    then `preview_uri` stays `None`).
  * **session** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`SessionStore`](foley.agent.session.md#foley.agent.session.SessionStore)]) – Optional session (unused here; accepted for a uniform signature).
* **Return type:**
  [`Candidate`](foley.base.md#foley.base.Candidate)
* **Returns:**
  The candidate with `preview_uri` set (or `None` on graceful degradation).

### foley.agent.preview.refine(session=None, , query=None, picked_ids=(), rejected_ids=(), hint=None, n=3, k=10, library=None, refiner=None)

Relevance-feedback refinement: expand for recall, boost picks, drop rejects, re-rank.

Distinct from [`foley.refine_query()`](foley.md#foley.refine_query) (which only paraphrases a query): this reads
the session’s picks/rejects (or the explicit `picked_ids` / `rejected_ids`),
expands the query into paraphrases for recall, gathers neighbours of every pick, drops
the rejects, and re-ranks by score.

* **Parameters:**
  * **session** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`SessionStore`](foley.agent.session.md#foley.agent.session.SessionStore)]) – The audition session (source of picks/rejects when not passed explicitly).
  * **query** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – The base text query to expand (optional).
  * **rejected_ids** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]) – Explicit feedback (override the session’s).
  * **hint** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – A steer for the query expansion.
  * **n** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Paraphrases to request.
  * **k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Result depth.
  * **library** – The [`foley.index.SoundLibrary`](foley.index.md#foley.index.SoundLibrary) (default: the shared one).
  * **refiner** – The query-expansion seam (default: the deterministic fake).
* **Return type:**
  [`RefineResult`](#foley.agent.preview.RefineResult)
* **Returns:**
  A [`RefineResult`](#foley.agent.preview.RefineResult).

### foley.agent.preview.similar_to(clip_or_candidate, , k=10, library=None)

“More like this” — neighbours of a sound id / candidate, or of a raw clip.

A `str` id or a [`Candidate`](foley.base.md#foley.base.Candidate) uses by-id neighbours
(`SoundLibrary.similar`, self excluded); a raw working-array / bytes clip uses
audio-to-audio search (`SoundLibrary.search_clip`).

* **Parameters:**
  * **clip_or_candidate** – A sound id, a [`Candidate`](foley.base.md#foley.base.Candidate), or a clip.
  * **k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – How many neighbours to return.
  * **library** – The [`foley.index.SoundLibrary`](foley.index.md#foley.index.SoundLibrary) (default: the shared one).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Candidate`](foley.base.md#foley.base.Candidate)]
* **Returns:**
  A list of [`Candidate`](foley.base.md#foley.base.Candidate).
