"""Offline / local-LLM SELECT rungs — OpenAI-compatible ``Decomposer`` / ``Judge`` / ``Refiner``.

The offline sibling of the Anthropic-backed SELECT rungs: instead of calling the hosted
Claude API, these hit any **OpenAI-compatible** chat endpoint — an on-device server such as
**Ollama** (``http://localhost:11434/v1``), **llama.cpp**'s server, or **vLLM** — so
``foley.find`` can run its LLM decomposition / judging / refinement with **nothing leaving
the device** (report 12's offline posture). They satisfy the same
:mod:`foley.agent.protocols` seams and REUSE the exact system prompts + JSON schemas the
Anthropic rungs use (one prompt SSOT), differing only in the transport.

Zero-config wiring: set ``FOLEY_LLM_BASE_URL`` (+ optionally ``FOLEY_LLM_MODEL`` /
``FOLEY_LLM_API_KEY``) and the SELECT defaults auto-upgrade to these — see
:func:`local_llm_configured`, consulted by ``_default_decomposer`` / ``_default_judge`` /
``_default_refiner``. ``openai`` (the thin OpenAI client, ``foley[local-llm]``) is imported
LAZILY inside the call path only, so ``import foley`` / ``import foley.agent`` stay dol-only;
tests inject a fake ``client`` and never touch the network.
"""

from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..base import Candidate, SoundEvent, Verdict, VerifyLevel

#: The default local model id (override per call or via ``FOLEY_LLM_MODEL``).
DEFAULT_LOCAL_MODEL = "llama3.1"


def local_llm_configured() -> bool:
    """True iff a local OpenAI-compatible endpoint is configured (``FOLEY_LLM_BASE_URL``)."""
    return bool(os.environ.get("FOLEY_LLM_BASE_URL"))


def _default_model() -> str:
    return os.environ.get("FOLEY_LLM_MODEL") or DEFAULT_LOCAL_MODEL


def _make_client(base_url: Optional[str] = None, api_key: Optional[str] = None):
    """Build an OpenAI client pointed at the local endpoint (lazy ``openai`` import)."""
    import openai  # lazy: foley[local-llm]

    return openai.OpenAI(
        base_url=base_url or os.environ.get("FOLEY_LLM_BASE_URL"),
        # local servers ignore the key but the client requires a non-empty one
        api_key=api_key or os.environ.get("FOLEY_LLM_API_KEY") or "local",
    )


def _chat_json(client, *, model: str, system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One OpenAI-compatible chat call returning parsed JSON.

    Uses ``response_format={'type':'json_object'}`` (the broadly-supported local-model
    JSON mode) and appends the JSON Schema to the system prompt so the model shapes its
    output — the same schema the Anthropic rung passes natively, kept as one SSOT.
    """
    import json

    sys_prompt = (
        system
        + "\n\nReturn ONLY a single JSON object conforming to this JSON Schema "
        "(no prose, no markdown fences):\n"
        + json.dumps(schema)
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=max_tokens,
    )
    return json.loads(resp.choices[0].message.content)


class LocalLLMDecomposer:
    """OpenAI-compatible :class:`~foley.agent.protocols.Decomposer` (local endpoint)."""

    def __init__(self, *, client=None, model: Optional[str] = None, max_tokens: int = 2000):
        self._client = client
        self.model = model or _default_model()
        self.max_tokens = max_tokens
        self.last_response = None  # obs stays truthful: no Anthropic-shaped usage to record

    def decompose(
        self, context: str, *, max_events: int = 6, seconds: Optional[float] = None
    ) -> "list[SoundEvent]":
        """Decompose ``context`` into ``<= max_events`` events via the local LLM."""
        from ..base import SoundEvent
        from .decompose import _DECOMPOSE_SYSTEM, _EVENT_JSON_SCHEMA

        client = self._client or _make_client()
        data = _chat_json(
            client,
            model=self.model,
            system=_DECOMPOSE_SYSTEM + f" Emit at most {max_events} events, most salient first.",
            user=context,
            schema=_EVENT_JSON_SCHEMA,
            max_tokens=self.max_tokens,
        )
        return [SoundEvent.from_dict(e) for e in data.get("events", [])][:max_events]


class LocalLLMJudge:
    """OpenAI-compatible :class:`~foley.agent.protocols.Judge` for the ``judge`` rung."""

    def __init__(self, *, client=None, model: Optional[str] = None, max_tokens: int = 500):
        self._client = client
        self.model = model or _default_model()
        self.max_tokens = max_tokens
        self.last_response = None

    def judge(self, event: "SoundEvent", candidate: "Candidate", *, level=None) -> "Verdict":
        """Arbitrate the match via the local LLM; returns a :class:`Verdict` at ``level``."""
        from ..base import Verdict, VerifyLevel
        from .verify import _JUDGE_JSON_SCHEMA, _JUDGE_SYSTEM

        client = self._client or _make_client()
        sound = candidate.sound
        desc = sound.caption or ""
        if sound.tags:
            desc += " [tags: " + ", ".join(sound.tags) + "]"
        data = _chat_json(
            client,
            model=self.model,
            system=_JUDGE_SYSTEM,
            user=f"Wanted event: {event.query}\nCandidate clip: {desc}",
            schema=_JUDGE_JSON_SCHEMA,
            max_tokens=self.max_tokens,
        )
        return Verdict(
            match=bool(data["match"]),
            confidence=float(data["confidence"]),
            reason=str(data.get("reason", "")),
            level=VerifyLevel(level if level is not None else VerifyLevel.judge),
        )


class LocalLLMRefiner:
    """OpenAI-compatible :class:`~foley.agent.protocols.Refiner` (local endpoint)."""

    def __init__(self, *, client=None, model: Optional[str] = None, max_tokens: int = 500):
        self._client = client
        self.model = model or _default_model()
        self.max_tokens = max_tokens
        self.last_response = None

    def refine(self, query: str, *, n: int = 3, hint: Optional[str] = None) -> "list[str]":
        """Return ``n`` paraphrases via the local LLM (the original ``query`` always first)."""
        from .refine import _REFINE_JSON_SCHEMA, _REFINE_SYSTEM

        client = self._client or _make_client()
        user = f"Query: {query}\nParaphrases wanted: {n}"
        if hint:
            user += f"\nPrevious attempt failed because: {hint}"
        data = _chat_json(
            client,
            model=self.model,
            system=_REFINE_SYSTEM,
            user=user,
            schema=_REFINE_JSON_SCHEMA,
            max_tokens=self.max_tokens,
        )
        paraphrases = data.get("paraphrases", [])
        return ([query] + [p for p in paraphrases if p != query])[: max(1, n)]
