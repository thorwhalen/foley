# foley.agent.local_llm

Offline / local-LLM SELECT rungs — OpenAI-compatible `Decomposer` / `Judge` / `Refiner`.

The offline sibling of the Anthropic-backed SELECT rungs: instead of calling the hosted
Claude API, these hit any **OpenAI-compatible** chat endpoint — an on-device server such as
**Ollama** (`http://localhost:11434/v1`), **llama.cpp**’s server, or **vLLM** — so
`foley.find` can run its LLM decomposition / judging / refinement with \*\*nothing leaving
the device\*\* (report 12’s offline posture). They satisfy the same
[`foley.agent.protocols`](foley.agent.protocols.md#module-foley.agent.protocols) seams and REUSE the exact system prompts + JSON schemas the
Anthropic rungs use (one prompt SSOT), differing only in the transport.

Zero-config wiring: set `FOLEY_LLM_BASE_URL` (+ optionally `FOLEY_LLM_MODEL` /
`FOLEY_LLM_API_KEY`) and the SELECT defaults auto-upgrade to these — see
[`local_llm_configured()`](#foley.agent.local_llm.local_llm_configured), consulted by `_default_decomposer` / `_default_judge` /
`_default_refiner`. `openai` (the thin OpenAI client, `foley[local-llm]`) is imported
LAZILY inside the call path only, so `import foley` / `import foley.agent` stay dol-only;
tests inject a fake `client` and never touch the network.

### Module Attributes

| [`DEFAULT_LOCAL_MODEL`](#foley.agent.local_llm.DEFAULT_LOCAL_MODEL)   | The default local model id (override per call or via `FOLEY_LLM_MODEL`).   |
|------------------------------------------------------------------------|----------------------------------------------------------------------------|

### Functions

| [`local_llm_configured`](#foley.agent.local_llm.local_llm_configured)()   | True iff a local OpenAI-compatible endpoint is configured (`FOLEY_LLM_BASE_URL`).   |
|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------|

### Classes

| [`LocalLLMDecomposer`](#foley.agent.local_llm.LocalLLMDecomposer)(\*[, client, model, ...])     | OpenAI-compatible [`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer) (local endpoint).   |
|---------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| [`LocalLLMJudge`](#foley.agent.local_llm.LocalLLMJudge)(\*[, client, model, max_tokens])   | OpenAI-compatible [`Judge`](foley.agent.protocols.md#foley.agent.protocols.Judge) for the `judge` rung.         |
| [`LocalLLMRefiner`](#foley.agent.local_llm.LocalLLMRefiner)(\*[, client, model, max_tokens]) | OpenAI-compatible [`Refiner`](foley.agent.protocols.md#foley.agent.protocols.Refiner) (local endpoint).         |

### foley.agent.local_llm.DEFAULT_LOCAL_MODEL *= 'llama3.1'*

The default local model id (override per call or via `FOLEY_LLM_MODEL`).

### *class* foley.agent.local_llm.LocalLLMDecomposer(, client=None, model=None, max_tokens=2000)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

OpenAI-compatible [`Decomposer`](foley.agent.protocols.md#foley.agent.protocols.Decomposer) (local endpoint).

#### decompose(context, , max_events=6, seconds=None)

Decompose `context` into `<= max_events` events via the local LLM.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`SoundEvent`](foley.base.md#foley.base.SoundEvent)]

### *class* foley.agent.local_llm.LocalLLMJudge(, client=None, model=None, max_tokens=500)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

OpenAI-compatible [`Judge`](foley.agent.protocols.md#foley.agent.protocols.Judge) for the `judge` rung.

#### judge(event, candidate, , level=None)

Arbitrate the match via the local LLM; returns a `Verdict` at `level`.

* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)

### *class* foley.agent.local_llm.LocalLLMRefiner(, client=None, model=None, max_tokens=500)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

OpenAI-compatible [`Refiner`](foley.agent.protocols.md#foley.agent.protocols.Refiner) (local endpoint).

#### refine(query, , n=3, hint=None)

Return `n` paraphrases via the local LLM (the original `query` always first).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### foley.agent.local_llm.local_llm_configured()

True iff a local OpenAI-compatible endpoint is configured (`FOLEY_LLM_BASE_URL`).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)
