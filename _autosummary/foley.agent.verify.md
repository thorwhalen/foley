# foley.agent.verify

`verify_match` — the retrieve→verify ladder (clap → listen → judge) + `Judge` impls.

Retrieval gives a ranked shortlist; verification confirms the *intent* before a clip is
accepted (report 05 §3). Three rungs, cheapest first:

* `clap` — [`ClapJudge`](#foley.agent.verify.ClapJudge), the zero-config gate on the retrieval cosine (no ML).
* `listen` — an audio-LM “does this contain {event}?” check; **#7 ships the
  deterministic :class:\`StringOverlapJudge\`** here (caption/tag overlap). The real
  Qwen2-Audio impl is a future [`Judge`](foley.agent.protocols.md#foley.agent.protocols.Judge) behind this same
  `VerifyLevel` seam — no orchestrator change.
* `judge` — [`AnthropicJudge`](#foley.agent.verify.AnthropicJudge), an LLM arbiter (ties + scene consistency),
  `foley[agent]`; `anthropic` imported lazily.

The ladder is AND-confirming: the `clap` gate must pass before a higher rung is asked
to confirm. \*\*This module is the extension point #10b (the Tier-2 fit-judge) plugs
into\*\* — a new `Judge` bound at `level=judge` via the `judge=` keyword, with its
own fit-precision metric; it does not touch retrieval ranking (the [nDCG@10](mailto:nDCG@10) gate).

### Functions

| [`verify_match`](#foley.agent.verify.verify_match)(event, candidate, \*[, level, ...])   | Verify `candidate` against `event` up to rung `level` (AND-confirming ladder).   |
|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|

### Classes

| [`AnthropicJudge`](#foley.agent.verify.AnthropicJudge)(\*[, client, model, max_tokens])   | LLM arbiter for the `judge` rung (`foley[agent]`): Claude → a `Verdict`.             |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`AudioLMJudge`](#foley.agent.verify.AudioLMJudge)(\*[, pipeline, model, ...])          | The audio-LM `listen` rung (`foley[fit]`): Qwen2-Audio "does this contain {event}?". |
| [`ClapJudge`](#foley.agent.verify.ClapJudge)()                                       | The zero-config `clap` rung: gate on the retrieval cosine (no ML, no network).       |
| [`StringOverlapJudge`](#foley.agent.verify.StringOverlapJudge)(\*[, threshold])               | Deterministic stand-in for the `listen`/`judge` rungs (the hermetic CI fake).        |

### *class* foley.agent.verify.AnthropicJudge(, client=None, model='claude-opus-4-8', max_tokens=500)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

LLM arbiter for the `judge` rung (`foley[agent]`): Claude → a `Verdict`.

`anthropic` imported lazily inside [`judge()`](#foley.agent.verify.AnthropicJudge.judge). Stashes the `Message` on
`self.last_response` for the GenAI span.

#### judge(event, candidate, , level=VerifyLevel.judge)

Call Claude to arbitrate the match; returns a `Verdict` at `level`.

* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)

### *class* foley.agent.verify.AudioLMJudge(, pipeline=None, model='Qwen/Qwen2-Audio-7B-Instruct', max_tokens=300, tau=0.5)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The audio-LM `listen` rung (`foley[fit]`): Qwen2-Audio “does this contain {event}?”.

`transformers`/`torch` are imported lazily inside [`judge()`](#foley.agent.verify.AudioLMJudge.judge); an injected
`pipeline` (the test seam, mirroring the Stable-Audio fake-pipeline seam) drives the
whole byte-decode → prompt → P(yes) → `Verdict` path with no torch. Stashes
`self.model` + `self.last_response` so `verify_match`’s GenAI span stays
informative (same getattr contract [`AnthropicJudge`](#foley.agent.verify.AnthropicJudge) uses).

#### judge(event, candidate, , level=VerifyLevel.listen)

Listen to the clip and return the AQAScore `Verdict` (`P(yes) ≥ tau`).

* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)

### *class* foley.agent.verify.ClapJudge

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The zero-config `clap` rung: gate on the retrieval cosine (no ML, no network).

`match` iff the candidate’s `clap_score` clears `tau_clap`; `confidence` is
the score clamped to `0..1` so it is comparable to the higher rungs’ 0..1 scores.

#### judge(event, candidate, , level=VerifyLevel.clap, tau_clap=0.35)

Return the `clap`-rung `Verdict` for `candidate`.

* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)

### *class* foley.agent.verify.StringOverlapJudge(, threshold=0.3)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Deterministic stand-in for the `listen`/`judge` rungs (the hermetic CI fake).

Jaccard token overlap of the event query vs the candidate’s caption + tags. Lets the
full ladder + [`decide()`](foley.agent.policy.md#foley.agent.policy.decide) branch run with zero ML/network. The
returned `Verdict` echoes back the requested `level`.

#### judge(event, candidate, , level=VerifyLevel.listen)

Return the token-overlap `Verdict` at the requested `level`.

* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)

### foley.agent.verify.verify_match(event, candidate, , level=VerifyLevel.clap, judge=None, tau_clap=0.35, \_span=None)

Verify `candidate` against `event` up to rung `level` (AND-confirming ladder).

Runs the `clap` gate always; if `level` is higher **and** the clap gate passed,
escalates to the injected/​default judge for that rung and returns *its* verdict
(`Verdict.level` == the producing rung).

* **Parameters:**
  * **event** ([`SoundEvent`](foley.base.md#foley.base.SoundEvent)) – The wanted `SoundEvent`.
  * **candidate** ([`Candidate`](foley.base.md#foley.base.Candidate)) – A **license-clean** `Candidate` — this MUST run after the
    [`gate_candidates()`](foley.agent.policy.md#foley.agent.policy.gate_candidates) gate (asserted).
  * **level** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`VerifyLevel`](foley.base.md#foley.base.VerifyLevel)) – The max rung to climb (`clap` | `listen` | `judge`).
  * **judge** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Judge`](foley.agent.protocols.md#foley.agent.protocols.Judge)]) – An injected [`Judge`](foley.agent.protocols.md#foley.agent.protocols.Judge) for the higher rungs
    (the DI seam; defaults per `_default_judge()`).
  * **tau_clap** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – The clap-gate threshold.
  * **\_span** – Internal — the obs span handle for GenAI recording on the LLM rung.
* **Raises:**
  [**AssertionError**](https://docs.python.org/3/builtins/exceptions.html#AssertionError) – If `candidate.license_ok` is not `True` (verify-before-gate
      is a bug — the license gate is the fail-closed first pass).
* **Return type:**
  [`Verdict`](foley.base.md#foley.base.Verdict)
