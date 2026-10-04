# foley.agent.llm

Which LLM the SELECT rungs use — one explicit, spend-safe resolver (the `llm=` seam).

The decomposer, refiner and judges each have a hermetic fake and two real
implementations (a local OpenAI-compatible endpoint and Anthropic). Which one runs
used to depend on whether an API key happened to be in the environment, so a machine
with `ANTHROPIC_API_KEY` set turned every `find()` — and the test suite — into
paid calls. This module is the single place that choice is made, and a paid or remote
provider is never chosen implicitly:

1. the explicit `llm=` argument (`'fake'` | `'local'` | `'anthropic'`), else
2. the `$FOLEY_LLM` environment variable (same values), else
3. the free default: `'local'` when `$FOLEY_LLM_BASE_URL` is a loopback endpoint
   (Ollama, llama.cpp on this machine), otherwise `'fake'`. A remote endpoint (an
   OpenAI-compatible cloud API) may cost money, so it needs `llm='local'`.

A key being present never upgrades anything. Asking for a provider that cannot run
(no SDK, no key, no endpoint) raises an error naming what is missing. Under
[`foley.offline()`](foley.md#foley.offline) a provider that sends data off the device raises
[`EgressBlocked`](foley.runtime.md#foley.runtime.EgressBlocked) — at resolution time *and* when a real rung is
called ([`require_llm_egress()`](#foley.agent.llm.require_llm_egress)), so an injected `AnthropicJudge()` is covered too.

[`PROVIDERS`](#foley.agent.llm.PROVIDERS) is the provider table: each provider’s rung classes. It is the one
place a new provider, or per-provider cost data, is added.

### Module Attributes

| [`LLM_ENV_VAR`](#foley.agent.llm.LLM_ENV_VAR)     | The environment variable that opts in to a provider when `llm=` is not passed.          |
|------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| [`PROVIDERS`](#foley.agent.llm.PROVIDERS)       | provider -> rung kind -> `"module:Class"` (imported lazily; the real ones need extras). |
| [`LLM_CHOICES`](#foley.agent.llm.LLM_CHOICES)     | The accepted providers.                                                                 |
| [`RUNG_MAX_TOKENS`](#foley.agent.llm.RUNG_MAX_TOKENS) | Default `max_tokens` of each rung (the classes read these, so estimates match).         |

### Functions

| [`resolve_llm`](#foley.agent.llm.resolve_llm)([llm, implicit_local])            | Resolve which LLM provider the SELECT rungs use (see the module docstring).                                                             |
|------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| [`make_rung`](#foley.agent.llm.make_rung)(kind[, llm, implicit_local])        | Build the `kind` rung (`'decomposer'` | `'refiner'` | `'judge'`) for `llm`.                                                             |
| [`llm_egress`](#foley.agent.llm.llm_egress)(provider)                          | The `data_egress` class (`'local'` | `'external'`) of an LLM provider.                                                                  |
| [`require_llm_egress`](#foley.agent.llm.require_llm_egress)(provider)                  | Raise [`EgressBlocked`](foley.runtime.md#foley.runtime.EgressBlocked) if the runtime forbids `provider` now. |
| [`llm_call_estimate`](#foley.agent.llm.llm_call_estimate)(provider, \*[, model, ...]) | An upper bound on one rung call's USD cost, or `None` when it is unknown.                                                               |
| [`guard_llm_call`](#foley.agent.llm.guard_llm_call)(provider)                      | The call-time egress check every real rung runs before calling its model.                                                               |
| [`metered_create`](#foley.agent.llm.metered_create)(client, \*[, sleep])           | `client.messages.create(**request)`, priced, capped and charged (#57).                                                                  |
| [`is_loopback_host`](#foley.agent.llm.is_loopback_host)(host)                        | Whether `host` is this machine (`localhost`, `127.*`, `::1`, `0.0.0.0`).                                                                |

### foley.agent.llm.LLM_CHOICES *= ('fake', 'local', 'anthropic')*

The accepted providers. `'fake'` is deterministic and free; the other two are real.

### foley.agent.llm.LLM_ENV_VAR *= 'FOLEY_LLM'*

The environment variable that opts in to a provider when `llm=` is not passed.

### foley.agent.llm.PROVIDERS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [str](https://docs.python.org/3/builtins/stdtypes.html#str)]]* *= {'anthropic': {'decomposer': 'foley.agent.decompose:AnthropicDecomposer', 'judge': 'foley.agent.verify:AnthropicJudge', 'refiner': 'foley.agent.refine:AnthropicRefiner'}, 'fake': {'decomposer': 'foley.agent.decompose:KeywordDecomposer', 'judge': 'foley.agent.verify:StringOverlapJudge', 'refiner': 'foley.agent.refine:KeywordRefiner'}, 'local': {'decomposer': 'foley.agent.local_llm:LocalLLMDecomposer', 'judge': 'foley.agent.local_llm:LocalLLMJudge', 'refiner': 'foley.agent.local_llm:LocalLLMRefiner'}}*

provider -> rung kind -> `"module:Class"` (imported lazily; the real ones need extras).

### foley.agent.llm.RUNG_MAX_TOKENS *= {'decomposer': 2000, 'judge': 500, 'refiner': 500}*

Default `max_tokens` of each rung (the classes read these, so estimates match).

### foley.agent.llm.guard_llm_call(provider)

The call-time egress check every real rung runs before calling its model.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### foley.agent.llm.is_loopback_host(host)

Whether `host` is this machine (`localhost`, `127.*`, `::1`, `0.0.0.0`).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### foley.agent.llm.llm_call_estimate(provider, , model=None, max_tokens=None, kind=None, input_chars=0)

An upper bound on one rung call’s USD cost, or `None` when it is unknown.

`0.0` for the fake and an on-device endpoint. For Anthropic: the input-token
bound (`chars / CHARS_PER_TOKEN_FLOOR` of the prompt — the rung’s fixed prompt
and allowance when `kind` is given, plus `input_chars`) × the input price, plus
`max_tokens` × the output price (thinking counts toward `max_tokens`). A remote
endpoint, or an Anthropic model with no listed price, is `None`.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

### foley.agent.llm.llm_egress(provider)

The `data_egress` class (`'local'` | `'external'`) of an LLM provider.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### foley.agent.llm.make_rung(kind, llm=None, , implicit_local=True, \*\*kwargs)

Build the `kind` rung (`'decomposer'` | `'refiner'` | `'judge'`) for `llm`.

* **Parameters:**
  * **kind** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The rung kind (a key of each [`PROVIDERS`](#foley.agent.llm.PROVIDERS) row).
  * **llm** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – The provider (see [`resolve_llm()`](#foley.agent.llm.resolve_llm)).
  * **implicit_local** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Forwarded to [`resolve_llm()`](#foley.agent.llm.resolve_llm).
  * **\*\*kwargs** – Passed to the rung’s constructor.

### foley.agent.llm.metered_create(client, , sleep=None, \*\*request)

`client.messages.create(**request)`, priced, capped and charged (#57).

The bound for *this* request (its real prompt length and `max_tokens`) is
reserved on every budget in force before it is sent, so it can never take a run
past its cap; afterwards the reservation becomes the actual cost from
`response.usage`. A request the API rejects (429 / 5xx — not billed) is retried
up to `METERED_ATTEMPTS` times. Anything else (a timeout, a dropped
connection) keeps the reservation — it may have been billed — and raises. The SDK
never re-sends behind this accounting: foley builds its clients with
`max_retries=0`, and an injected client is used through
`with_options(max_retries=0)`. Tokens the API adds itself (structured-output
grammar, thinking) are not in the bound; [`settle()`](foley.cost.md#foley.cost.settle) records the
true cost from `usage` afterwards.

### foley.agent.llm.require_llm_egress(provider)

Raise [`EgressBlocked`](foley.runtime.md#foley.runtime.EgressBlocked) if the runtime forbids `provider` now.

Called by [`resolve_llm()`](#foley.agent.llm.resolve_llm) and again by each real rung right before it calls its
model, so a rung built online and called inside [`foley.offline()`](foley.md#foley.offline) is refused.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### foley.agent.llm.resolve_llm(llm=None, , implicit_local=True)

Resolve which LLM provider the SELECT rungs use (see the module docstring).

* **Parameters:**
  * **llm** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – `'fake'` | `'local'` | `'anthropic'`, or `None` to read
    `$FOLEY_LLM` and then fall back to the free default.
  * **implicit_local** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Whether the free default may be a loopback local endpoint.
    `False` keeps the default the deterministic fake (the hermetic eval).
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  One of [`LLM_CHOICES`](#foley.agent.llm.LLM_CHOICES).
* **Raises:**
  * [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `llm` (or `$FOLEY_LLM`) is not one of [`LLM_CHOICES`](#foley.agent.llm.LLM_CHOICES).
  * [**RuntimeError**](https://docs.python.org/3/builtins/exceptions.html#RuntimeError) – If the requested provider cannot run (SDK, key or endpoint missing).
  * [**EgressBlocked**](foley.runtime.md#foley.runtime.EgressBlocked) – If the provider sends data off the device under [`foley.offline()`](foley.md#foley.offline).
