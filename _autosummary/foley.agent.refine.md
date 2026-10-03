# foley.agent.refine

`refine_query` — one event query → 2–4 paraphrases for multi-query retrieval.

Retrieval quality is sensitive to phrasing (report 05 §2.2): several phrasings of the
same intent raise recall. v1 emits a *multi-query* list that
[`search_sounds()`](foley.agent.tools.md#foley.agent.tools.search_sounds) runs and RRF-merges (CLAP text-embedding
mean-pool fusion is a later drop-in behind this same seam). `refine_query` is also the
re-retrieval lever in the verify→refine loop, steered by a failure `hint`.

Two impls behind the [`Refiner`](foley.agent.protocols.md#foley.agent.protocols.Refiner) seam: the deterministic
[`KeywordRefiner`](#foley.agent.refine.KeywordRefiner) (default + CI fake) and the LLM-backed
[`AnthropicRefiner`](#foley.agent.refine.AnthropicRefiner) (`foley[agent]`; `anthropic` imported lazily inside the
method only, so `import foley` stays dol-only).

### Functions

| [`refine_query`](#foley.agent.refine.refine_query)(query, \*[, n, hint, refiner, \_span])   | Expand `query` into up to `n` paraphrases for multi-query retrieval.   |
|--------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|

### Classes

| [`AnthropicRefiner`](#foley.agent.refine.AnthropicRefiner)(\*[, client, model, max_tokens])   | LLM-backed refiner (`foley[agent]`): Claude → a paraphrase list.    |
|------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| [`KeywordRefiner`](#foley.agent.refine.KeywordRefiner)()                                    | Deterministic template-expansion refiner — the default and CI fake. |

### *class* foley.agent.refine.AnthropicRefiner(, client=None, model='claude-opus-4-8', max_tokens=500)

Bases: `object`

LLM-backed refiner (`foley[agent]`): Claude → a paraphrase list.

`anthropic` imported lazily inside [`refine()`](#foley.agent.refine.AnthropicRefiner.refine). Stashes the `Message` on
`self.last_response` for the GenAI span.

#### refine(query, , n=3, hint=None)

Call Claude for `n` paraphrases; the original `query` is always first.

* **Return type:**
  `list`[`str`]

### *class* foley.agent.refine.KeywordRefiner

Bases: `object`

Deterministic template-expansion refiner — the default and CI fake.

Expands a query into `n` distinct paraphrases via fixed descriptor templates; a
verify-failure `hint` nudges one extra variant. No RNG, no `anthropic` — same
query → identical paraphrase list.

#### refine(query, , n=3, hint=None)

Return up to `n` distinct paraphrases of `query` (the first is `query`).

* **Parameters:**
  * **query** (`str`) – The event query to expand.
  * **n** (`int`) – How many paraphrases to return (2–4 is typical).
  * **hint** (`Optional`[`str`]) – Optional verify-failure reason to steer re-retrieval.
* **Return type:**
  `list`[`str`]

### foley.agent.refine.refine_query(query, , n=3, hint=None, refiner=None, \_span=None)

Expand `query` into up to `n` paraphrases for multi-query retrieval.

* **Parameters:**
  * **query** (`str`) – The event query to expand.
  * **n** (`int`) – Number of paraphrases.
  * **hint** (`Optional`[`str`]) – Optional verify-failure reason to steer re-retrieval.
  * **refiner** (`Optional`[[`Refiner`](foley.agent.protocols.md#foley.agent.protocols.Refiner)]) – An injected [`Refiner`](foley.agent.protocols.md#foley.agent.protocols.Refiner) (the DI seam);
    defaults to `_default_refiner()`.
  * **\_span** – Internal — the obs span handle for GenAI recording.
* **Return type:**
  `list`[`str`]
