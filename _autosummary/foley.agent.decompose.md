# foley.agent.decompose

`decompose_context` — narrative passage → a sparse, salience-ranked event list.

The moat of the SELECT stage (report 05 §2): turning prose into a \*tastefully sparse,
correctly-diegetic\* [`SoundEvent`](foley.base.md#foley.base.SoundEvent) list is the hard, defensible part —
not the CLAP encoder. Two impls sit behind the [`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer)
seam:

* [`KeywordDecomposer`](#foley.agent.decompose.KeywordDecomposer) — the deterministic default *and* the hermetic CI fake:
  a built-in cue lexicon, zero dependencies, same passage → identical list.
* [`AnthropicDecomposer`](#foley.agent.decompose.AnthropicDecomposer) — the LLM-backed impl behind the `foley[agent]` extra;
  `anthropic` is imported lazily **inside** `.decompose` only, so `import foley`
  stays dol-only.

[`decompose_context()`](#foley.agent.decompose.decompose_context) is the pure tool wrapper (Python-API == agent == future-MCP
surface): it resolves the default decomposer, calls it, and records the GenAI span on
the real path.

### Functions

| [`decompose_context`](#foley.agent.decompose.decompose_context)(context, \*[, max_events, ...])   | Decompose a passage into `<= max_events` sparse `SoundEvent`s.   |
|------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|

### Classes

| [`AnthropicDecomposer`](#foley.agent.decompose.AnthropicDecomposer)(\*[, client, model, ...])   | LLM-backed decomposer (`foley[agent]`): Claude → a structured event list.       |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`KeywordDecomposer`](#foley.agent.decompose.KeywordDecomposer)()                             | Deterministic cue-lexicon decomposer — the zero-dependency default and CI fake. |

### *class* foley.agent.decompose.AnthropicDecomposer(, client=None, model='claude-opus-4-8', max_tokens=2000)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

LLM-backed decomposer (`foley[agent]`): Claude → a structured event list.

`anthropic` is imported lazily inside [`decompose()`](#foley.agent.decompose.AnthropicDecomposer.decompose) so `import foley` stays
dol-only. Stashes the returned `Message` on `self.last_response` so
[`decompose_context()`](#foley.agent.decompose.decompose_context) can record the GenAI span (token usage / model /
stop_reason). Model, thinking, and structured-output shape follow the `claude-api`
conventions (`claude-opus-4-8`, adaptive thinking — never `budget_tokens`).

#### decompose(context, , max_events=6, seconds=None)

Call Claude and round-trip each event through `SoundEvent.from_dict()`.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`SoundEvent`](foley.base.md#foley.base.SoundEvent)]

### *class* foley.agent.decompose.KeywordDecomposer

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Deterministic cue-lexicon decomposer — the zero-dependency default and CI fake.

Scans the passage against `_CUE_LEXICON`, emits one `SoundEvent` per
matched cue in first-appearance order (so salience descends with reading order),
dedupes by canonical query, and truncates to `max_events` (the sparse density
budget). No RNG, no network, no `anthropic` — same passage → identical list.

#### decompose(context, , max_events=6, seconds=None)

Return `<= max_events` deterministic `SoundEvent`s for `context`.

* **Parameters:**
  * **context** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The narrative passage.
  * **max_events** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – The sparse density cap (the salience budget).
  * **seconds** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – Accepted for signature parity (the per-second density window is a
    later refinement); ignored here.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`SoundEvent`](foley.base.md#foley.base.SoundEvent)]

### foley.agent.decompose.decompose_context(context, , max_events=6, seconds=None, decomposer=None, \_span=None)

Decompose a passage into `<= max_events` sparse `SoundEvent`s.

The pure SELECT tool (Python-API == agent == future-MCP surface): resolves the
default decomposer when `decomposer` is `None`, calls it, and records the GenAI
span on the real path (the fake’s `last_response` is `None` → no-op).

* **Parameters:**
  * **context** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The narrative passage.
  * **max_events** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – The sparse density cap.
  * **seconds** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – Optional passage duration (density-window hint; forwarded, else ignored).
  * **decomposer** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer)]) – An injected [`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer) (the DI seam);
    defaults to `_default_decomposer()`.
  * **\_span** – Internal — the obs span handle `find()` opens for GenAI recording.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`SoundEvent`](foley.base.md#foley.base.SoundEvent)]
