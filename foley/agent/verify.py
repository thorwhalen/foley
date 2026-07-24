"""``verify_match`` — the retrieve→verify ladder (clap → listen → judge) + ``Judge`` impls.

Retrieval gives a ranked shortlist; verification confirms the *intent* before a clip is
accepted (report 05 §3). Three rungs, cheapest first:

* ``clap`` — :class:`ClapJudge`, the zero-config gate on the retrieval cosine (no ML).
* ``listen`` — an audio-LM "does this contain {event}?" check; **#7 ships the
  deterministic :class:`StringOverlapJudge`** here (caption/tag overlap). The real
  Qwen2-Audio impl is a future :class:`~foley.agent.protocols.Judge` behind this same
  ``VerifyLevel`` seam — no orchestrator change.
* ``judge`` — :class:`AnthropicJudge`, an LLM arbiter (ties + scene consistency),
  ``foley[agent]``; ``anthropic`` imported lazily.

The ladder is AND-confirming: the ``clap`` gate must pass before a higher rung is asked
to confirm. **This module is the extension point #10b (the Tier-2 fit-judge) plugs
into** — a new ``Judge`` bound at ``level=judge`` via the ``judge=`` keyword, with its
own fit-precision metric; it does not touch retrieval ranking (the nDCG@10 gate).
"""

from __future__ import annotations

import re
from typing import Optional

from ..base import Candidate, SoundEvent, Verdict, VerifyLevel
from ._genai import DEFAULT_AGENT_MODEL, record_genai
from .protocols import Judge


def _tokens(text: Optional[str]) -> "set[str]":
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


class ClapJudge:
    """The zero-config ``clap`` rung: gate on the retrieval cosine (no ML, no network).

    ``match`` iff the candidate's ``clap_score`` clears ``tau_clap``; ``confidence`` is
    the score clamped to ``0..1`` so it is comparable to the higher rungs' 0..1 scores.
    """

    def judge(
        self,
        event: SoundEvent,
        candidate: Candidate,
        *,
        level: VerifyLevel = VerifyLevel.clap,
        tau_clap: float = 0.35,
    ) -> Verdict:
        """Return the ``clap``-rung :class:`Verdict` for ``candidate``."""
        score = candidate.clap_score if candidate.clap_score is not None else 0.0
        confidence = min(max(score, 0.0), 1.0)
        match = score >= tau_clap
        return Verdict(
            match=match,
            confidence=confidence,
            reason=f"clap_score={score:.3f} vs tau={tau_clap:.2f}",
            level=VerifyLevel.clap,
        )


class StringOverlapJudge:
    """Deterministic stand-in for the ``listen``/``judge`` rungs (the hermetic CI fake).

    Jaccard token overlap of the event query vs the candidate's caption + tags. Lets the
    full ladder + :func:`~foley.agent.policy.decide` branch run with zero ML/network. The
    returned :class:`Verdict` echoes back the requested ``level``.
    """

    def __init__(self, *, threshold: float = 0.3):
        self.threshold = threshold

    def judge(
        self,
        event: SoundEvent,
        candidate: Candidate,
        *,
        level: VerifyLevel = VerifyLevel.listen,
    ) -> Verdict:
        """Return the token-overlap :class:`Verdict` at the requested ``level``."""
        want = _tokens(event.query)
        sound = candidate.sound
        have = _tokens(sound.caption) | {
            t for tag in (sound.tags or []) for t in _tokens(tag)
        }
        union = want | have
        overlap = len(want & have) / len(union) if union else 0.0
        return Verdict(
            match=overlap >= self.threshold,
            confidence=overlap,
            reason=f"{overlap:.2f} token overlap",
            level=VerifyLevel(level),
        )


# ---------------------------------------------------------------------------
# The real, LLM-backed judge rung (behind foley[agent]; anthropic imported lazily)
# ---------------------------------------------------------------------------

_JUDGE_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "match": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["match", "confidence", "reason"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "You are an audio-match judge. Given a wanted sound EVENT and a candidate clip's "
    "description, decide whether the clip genuinely depicts the event (the right object, "
    "not merely a similar vibe) and is consistent with the scene. Return a structured "
    "verdict: match (bool), confidence (0..1), and a one-line reason."
)


class AnthropicJudge:
    """LLM arbiter for the ``judge`` rung (``foley[agent]``): Claude → a :class:`Verdict`.

    ``anthropic`` imported lazily inside :meth:`judge`. Stashes the ``Message`` on
    ``self.last_response`` for the GenAI span.
    """

    def __init__(
        self, *, client=None, model: str = DEFAULT_AGENT_MODEL, max_tokens: int = 500
    ):
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.last_response = None

    def judge(
        self,
        event: SoundEvent,
        candidate: Candidate,
        *,
        level: VerifyLevel = VerifyLevel.judge,
    ) -> Verdict:
        """Call Claude to arbitrate the match; returns a :class:`Verdict` at ``level``."""
        import json

        client = self._client
        if client is None:
            import anthropic  # lazy — only on the real path

            client = anthropic.Anthropic()
        sound = candidate.sound
        desc = sound.caption or ""
        if sound.tags:
            desc += " [tags: " + ", ".join(sound.tags) + "]"
        user = f"Wanted event: {event.query}\nCandidate clip: {desc}"
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={
                "format": {"type": "json_schema", "schema": _JUDGE_JSON_SCHEMA}
            },
        )
        self.last_response = resp
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text")
        data = json.loads(text)
        return Verdict(
            match=bool(data["match"]),
            confidence=float(data["confidence"]),
            reason=str(data.get("reason", "")),
            level=VerifyLevel(level),
        )


def _default_judge(level: "str | VerifyLevel") -> Judge:
    """The zero-config judge for a rung: ClapJudge for ``clap``; else Anthropic or the fake."""
    level = VerifyLevel(level)
    if level == VerifyLevel.clap:
        return ClapJudge()
    from .decompose import _anthropic_available

    return AnthropicJudge() if _anthropic_available() else StringOverlapJudge()


# ---------------------------------------------------------------------------
# Tier-2 fit-judge (#10b) — the audio-LM "listen-and-confirm" rung
# ---------------------------------------------------------------------------
# The one capability the #7 roster lacks: ingest the ACTUAL clip bytes and answer
# "does this audio contain {event}?" (the AQAScore pattern, report 08 §2.1), catching
# CLAP's right-vibe-wrong-object failure. transformers/torch/torchaudio (foley[fit]) are
# imported lazily INSIDE the method only, so `import foley` stays dol-only; a fake
# ``pipeline=`` is injected in tests so the whole path is hermetically unit-tested
# without torch. The LLM arbiter (AnthropicJudge, level=judge) is left untouched.


def _audiolm_available() -> bool:
    """True iff the audio-LM stack (``foley[fit]``: transformers + torch) is importable."""
    import importlib.util

    return (
        importlib.util.find_spec("transformers") is not None
        and importlib.util.find_spec("torch") is not None
    )


def _load_candidate_audio(candidate: Candidate):
    """Decode the candidate's clip to ``(wav, sr)`` (lazy ``foley.audio.load``)."""
    from ..audio import load

    return load(candidate.sound.uri)


def _aqa_yes_probability(pipeline, wav, sr, query: str) -> "tuple[float, object]":
    """Pose the AQAScore yes/no question to the audio-LM and read P(yes).

    Returns ``(p_yes, raw)`` — the injected pipeline may return ``{'p_yes': float}``
    directly (the fake, and a real wrapper that reads the yes-token probability) or raw
    text that is parsed to a hard 0/1 (a conservative fallback).
    """
    prompt = f"Does this audio contain {query}? Answer strictly yes or no."
    out = pipeline(prompt, wav, sr)
    if isinstance(out, dict) and "p_yes" in out:
        return float(out["p_yes"]), out
    text = str(out).strip().lower()
    return (1.0 if text.startswith("yes") else 0.0), out


class AudioLMJudge:
    """The audio-LM ``listen`` rung (``foley[fit]``): Qwen2-Audio "does this contain {event}?".

    ``transformers``/``torch`` are imported lazily inside :meth:`judge`; an injected
    ``pipeline`` (the test seam, mirroring the Stable-Audio fake-pipeline seam) drives the
    whole byte-decode → prompt → P(yes) → :class:`Verdict` path with no torch. Stashes
    ``self.model`` + ``self.last_response`` so ``verify_match``'s GenAI span stays
    informative (same getattr contract :class:`AnthropicJudge` uses).
    """

    def __init__(
        self,
        *,
        pipeline=None,
        model: str = "Qwen/Qwen2-Audio-7B-Instruct",
        max_tokens: int = 300,
        tau: float = 0.5,
    ):
        self._pipeline = pipeline
        self.model = model
        self.max_tokens = max_tokens
        self.tau = tau
        self.last_response = None

    def judge(
        self, event: SoundEvent, candidate: Candidate, *, level: VerifyLevel = VerifyLevel.listen
    ) -> Verdict:
        """Listen to the clip and return the AQAScore :class:`Verdict` (``P(yes) ≥ tau``)."""
        wav, sr = _load_candidate_audio(candidate)
        pipeline = self._pipeline if self._pipeline is not None else self._build_pipeline()
        p_yes, raw = _aqa_yes_probability(pipeline, wav, sr, event.query)
        self.last_response = raw
        return Verdict(
            match=p_yes >= self.tau,
            confidence=p_yes,
            reason=f"AQAScore P(yes)={p_yes:.2f}",
            level=VerifyLevel(level),
        )

    def _build_pipeline(self):  # pragma: no cover - the real Qwen2-Audio path (foley[fit])
        """Lazily build the real Qwen2-Audio pipeline wrapper (heavy; behind ``foley[fit]``)."""
        raise NotImplementedError(
            "AudioLMJudge needs an injected pipeline or foley[fit] (transformers+torch); "
            "the real Qwen2-Audio wrapper is a deferred #10b follow-up."
        )


def _default_fit_judge(level: "str | VerifyLevel") -> Judge:
    """The zero-config Tier-2 fit-judge: the LLM arbiter when a key is configured, else the fake.

    Auto-upgrades to :class:`AnthropicJudge` when ``anthropic`` + a key are present (the
    nightly/pre-release path); in CI (no key) it resolves to the deterministic
    :class:`StringOverlapJudge`, so ``foley.evaluate_fit()`` is hermetic out of the box.

    :class:`AudioLMJudge` (the audio-LM ``listen`` rung) is **injection-only** in this
    slice: its real Qwen2-Audio pipeline is a deferred #10b follow-up, so the resolver
    does not auto-select it (it would need ``foley[fit]`` *and* a built pipeline). Pass
    ``fit_judge=AudioLMJudge(pipeline=...)`` explicitly to use it. Tests inject explicitly.
    """
    from .decompose import _anthropic_available

    VerifyLevel(level)  # validate the rung
    if _anthropic_available():
        return AnthropicJudge()
    return StringOverlapJudge()


def verify_match(
    event: SoundEvent,
    candidate: Candidate,
    *,
    level: "str | VerifyLevel" = VerifyLevel.clap,
    judge: "Optional[Judge]" = None,
    tau_clap: float = 0.35,
    _span=None,
) -> Verdict:
    """Verify ``candidate`` against ``event`` up to rung ``level`` (AND-confirming ladder).

    Runs the ``clap`` gate always; if ``level`` is higher **and** the clap gate passed,
    escalates to the injected/​default judge for that rung and returns *its* verdict
    (``Verdict.level`` == the producing rung).

    Args:
        event: The wanted :class:`SoundEvent`.
        candidate: A **license-clean** :class:`Candidate` — this MUST run after the
            :func:`~foley.agent.policy.gate_candidates` gate (asserted).
        level: The max rung to climb (``clap`` | ``listen`` | ``judge``).
        judge: An injected :class:`~foley.agent.protocols.Judge` for the higher rungs
            (the DI seam; defaults per :func:`_default_judge`).
        tau_clap: The clap-gate threshold.
        _span: Internal — the obs span handle for GenAI recording on the LLM rung.

    Raises:
        AssertionError: If ``candidate.license_ok`` is not ``True`` (verify-before-gate
            is a bug — the license gate is the fail-closed first pass).
    """
    assert candidate.license_ok is True, (
        "verify_match must run AFTER the license gate (candidate.license_ok is not True)"
    )
    level = VerifyLevel(level)
    clap_verdict = ClapJudge().judge(
        event, candidate, level=VerifyLevel.clap, tau_clap=tau_clap
    )
    if level == VerifyLevel.clap:
        return clap_verdict
    # The clap GATE only blocks a *retrieved* clip whose score is present and failing; a
    # generated clip has no retrieval score (clap_score is None) and escalates directly —
    # the higher rung "listens" to the generated audio (report 05 §4).
    if candidate.clap_score is not None and not clap_verdict.match:
        return clap_verdict
    j = judge or _default_judge(level)
    verdict = j.judge(event, candidate, level=level)
    record_genai(
        _span,
        request_model=getattr(j, "model", DEFAULT_AGENT_MODEL),
        response=getattr(j, "last_response", None),
    )
    return verdict
