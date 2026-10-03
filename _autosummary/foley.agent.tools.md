# foley.agent.tools

The SELECT orchestration: `find()` / `plan()` + the small pure tool wrappers.

This is the one seam that serves the Python API, the agent loop, and the future MCP
server (#12) — the same functions, three surfaces (report 05 §5.2). It OWNS every
side-effecting call (`search` → `gate` → `verify` → `decide` → `generate` →
`place`); [`decide()`](foley.agent.policy.md#foley.agent.policy.decide) is a pure tail step that only branches.

`find()` opens **one** `foley.obs.run('find')` scope, so the nested
[`foley.search()`](foley.md#foley.search) / [`foley.generate()`](foley.md#foley.generate) façade calls aggregate into a single
reproducible run-manifest (report 10 §1.3); each stage emits a typed
[`Step`](foley.obs.run_artifact.md#foley.obs.run_artifact.Step) and each LLM rung a GenAI span. The plan it emits
is the **sparse** [`SoundDesignTimeline`](foley.base.md#foley.base.SoundDesignTimeline) subset — WEAVE (#8) resolves
anchors, mix, and mastering.

`import foley` stays dol-only: `foley.search` / `foley.generate` and the
generation-error hierarchy are imported lazily inside the functions that call them.

### Functions

| [`find`](#foley.agent.tools.find)(context, \*[, max_events, seconds, ...])     | The headline: a narrative context → verified, license-clean sound candidates.             |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| [`generate_sound`](#foley.agent.tools.generate_sound)(query, \*[, backend, library])     | Generate a clip for `query` (the fallback tool) — a thin wrapper over `foley.generate`.   |
| [`place_in_timeline`](#foley.agent.tools.place_in_timeline)(clip, \*[, onset, gain, ...])   | Emit the SPARSE per-item plan subset (`clip_ref·onset·gain·layer·loop`) — no more.        |
| [`plan`](#foley.agent.tools.plan)(candidates, \*[, transcript])                | Fold verified candidates into the SPARSE `SoundDesignTimeline` (the SELECT→WEAVE bridge). |
| [`search_sounds`](#foley.agent.tools.search_sounds)(queries, \*[, k, library, filters]) | Hybrid search for one query, or a multi-query RRF-merge (the SELECT retrieval tool).      |

### foley.agent.tools.find(context, , max_events=6, seconds=None, intended_use=None, backend='auto', verify='listen', stream=False, k=10, tau_retrieve=0.5, tau_clap=0.35, max_refine_loops=1, budget=None, library=None, decomposer=None, judge=None, refiner=None)

The headline: a narrative context → verified, license-clean sound candidates.

`decompose → (per event) refine/search → verify_match ladder → decide (with the
fail-closed license gate FIRST) → place` (report 05 §5). Works out of the box —
`foley.find("She pushed open the heavy oak door; rain hammered outside.")` — with
deterministic defaults; every model / threshold / seam is an optional keyword.

* **Parameters:**
  * **context** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The narrative passage.
  * **max_events** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – The sparse density cap on decomposed events.
  * **seconds** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – Optional passage duration (density-window hint; forwarded).
  * **intended_use** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`IntendedUse`](foley.base.md#foley.base.IntendedUse)]) – The caller’s rights intent (default: a conservative
    `IntendedUse` — `allow_voice_or_trademark` stays `False`).
  * **backend** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Generation backend for the fallback (`'auto'` → `foley.generate`’s default).
  * **verify** (`Union`[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`VerifyLevel`](foley.base.md#foley.base.VerifyLevel)]) – The max verify rung — `'clap'` | `'listen'` | `'judge'`.
  * **stream** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If `True`, return a generator yielding one `Candidate` per
    resolved event; else return the collected `list`.
  * **k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Retrieval shortlist depth per query.
  * **tau_retrieve** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Confidence threshold to auto-accept a retrieved clip.
  * **tau_clap** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – The `clap`-rung gate threshold.
  * **max_refine_loops** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Max refine→re-retrieve passes per event (also the default
    `Budget`).
  * **budget** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Budget`](foley.agent.policy.md#foley.agent.policy.Budget)]) – An explicit `Budget` (overrides `max_refine_loops`).
  * **library** – Target `SoundLibrary` (default: the process-wide default).
  * **refiner** (*decomposer / judge /*) – Injected DI seams
    ([`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer) / `Judge` / `Refiner`);
    each defaults to the hermetic fake when `foley[agent]` is absent.
* **Return type:**
  `Union`[[`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Candidate`](foley.base.md#foley.base.Candidate)], [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`Candidate`](foley.base.md#foley.base.Candidate)]]
* **Returns:**
  `list[Candidate]` (`stream=False`) or an `Iterator[Candidate]`
  (`stream=True`) — one verified, license-clean candidate per resolved event.

### foley.agent.tools.generate_sound(query, , backend='auto', library=None)

Generate a clip for `query` (the fallback tool) — a thin wrapper over `foley.generate`.

Returns a `Candidate` (`origin=generated`); raises the `GenerationError`
hierarchy on refusal / no-result (caught fail-closed by `_generate_and_reverify()`).

* **Return type:**
  [`Candidate`](foley.base.md#foley.base.Candidate)

### foley.agent.tools.place_in_timeline(clip, , onset=None, gain=0.0, layer=Layer.sfx_fg, loop=False)

Emit the SPARSE per-item plan subset (`clip_ref·onset·gain·layer·loop`) — no more.

`onset` stays a SYMBOLIC anchor string (never a resolved offset); mix / processing /
alignment / mastering are WEAVE’s (#8) job, not SELECT’s.

* **Return type:**
  [`TimelineItem`](foley.base.md#foley.base.TimelineItem)

### foley.agent.tools.plan(candidates, , transcript=None)

Fold verified candidates into the SPARSE `SoundDesignTimeline` (the SELECT→WEAVE bridge).

One `TimelineItem` per candidate (`onset·gain·layer·loop` only, from its
`SoundEvent`), joined to the run-artifact via `run_manifest_ref` — the
reserved #8 `plan_ref` slot is filled when called inside an active `foley.obs`
run scope (`None`-safe otherwise).

* **Parameters:**
  * **candidates** ([`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Candidate`](foley.base.md#foley.base.Candidate)]) – The candidates returned by [`find()`](#foley.agent.tools.find).
  * **transcript** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Optional narration transcript (WEAVE resolves the reference).
* **Return type:**
  [`SoundDesignTimeline`](foley.base.md#foley.base.SoundDesignTimeline)

### foley.agent.tools.search_sounds(queries, , k=10, library=None, filters=None)

Hybrid search for one query, or a multi-query RRF-merge (the SELECT retrieval tool).

Delegates a single query VERBATIM to `SoundLibrary.search()` (so the retrieval
ranking the [nDCG@10](mailto:nDCG@10) gate measures is untouched); a multi-query list runs each query
and RRF-merges (`k=RRF_K`) — the query-expansion recall lever, exercised only on a
refine pass.

* **Parameters:**
  * **queries** (`Union`[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – One query string, or a list of paraphrases to merge.
  * **k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of results.
  * **library** – Target library (default: the process-wide default).
  * **filters** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Extra `SoundLibrary.search()` kwargs (e.g. the license prefilter).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Candidate`](foley.base.md#foley.base.Candidate)]
