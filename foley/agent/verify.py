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
