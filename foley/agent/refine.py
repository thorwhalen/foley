"""``refine_query`` — one event query → 2–4 paraphrases for multi-query retrieval.

Retrieval quality is sensitive to phrasing (report 05 §2.2): several phrasings of the
same intent raise recall. v1 emits a *multi-query* list that
:func:`~foley.agent.tools.search_sounds` runs and RRF-merges (CLAP text-embedding
mean-pool fusion is a later drop-in behind this same seam). ``refine_query`` is also the
re-retrieval lever in the verify→refine loop, steered by a failure ``hint``.

Two impls behind the :class:`~foley.agent.protocols.Refiner` seam: the deterministic
:class:`KeywordRefiner` (default + CI fake) and the LLM-backed
:class:`AnthropicRefiner` (``foley[agent]``; ``anthropic`` imported lazily inside the
method only, so ``import foley`` stays dol-only).
"""

from __future__ import annotations

import re
from typing import Optional

from ._genai import DEFAULT_AGENT_MODEL, record_genai
from .protocols import Refiner


class KeywordRefiner:
    """Deterministic template-expansion refiner — the default and CI fake.

    Expands a query into ``n`` distinct paraphrases via fixed descriptor templates; a
    verify-failure ``hint`` nudges one extra variant. No RNG, no ``anthropic`` — same
    query → identical paraphrase list.
    """

    def refine(
        self, query: str, *, n: int = 3, hint: Optional[str] = None
    ) -> "list[str]":
        """Return up to ``n`` distinct paraphrases of ``query`` (the first is ``query``).

        Args:
            query: The event query to expand.
            n: How many paraphrases to return (2–4 is typical).
            hint: Optional verify-failure reason to steer re-retrieval.
        """
        variants = [
            query,
            f"sound of {query}",
            f"{query} sound effect",
            f"{query} field recording",
            f"clear {query}",
        ]
        if hint:
            tokens = re.findall(r"[a-z0-9]+", hint.lower())
            keep = [t for t in tokens if len(t) > 3][:2]
            if keep:
                variants.insert(1, f"{query} {' '.join(keep)}")
        out: "list[str]" = []
        for v in variants:
            if v not in out:
                out.append(v)
            if len(out) >= max(1, n):
                break
        return out


# ---------------------------------------------------------------------------
# The real, LLM-backed impl (behind foley[agent]; anthropic imported lazily)
# ---------------------------------------------------------------------------

_REFINE_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "paraphrases": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["paraphrases"],
    "additionalProperties": False,
}

_REFINE_SYSTEM = (
    "You expand a sound-retrieval query into a few short, varied paraphrases that describe "
    "the SAME sound with different wording (synonyms, materials, perspectives) to improve "
    "audio search recall. Return ONLY the structured list — no commentary."
)


class AnthropicRefiner:
    """LLM-backed refiner (``foley[agent]``): Claude → a paraphrase list.

    ``anthropic`` imported lazily inside :meth:`refine`. Stashes the ``Message`` on
    ``self.last_response`` for the GenAI span.
    """

    def __init__(
        self, *, client=None, model: str = DEFAULT_AGENT_MODEL, max_tokens: int = 500
    ):
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.last_response = None

    def refine(
        self, query: str, *, n: int = 3, hint: Optional[str] = None
    ) -> "list[str]":
        """Call Claude for ``n`` paraphrases; the original ``query`` is always first."""
        import json

        client = self._client
        if client is None:
            import anthropic  # lazy — only on the real path

            client = anthropic.Anthropic()
        user = f"Query: {query}\nParaphrases wanted: {n}"
        if hint:
            user += f"\nPrevious attempt failed because: {hint}"
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=_REFINE_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={
                "format": {"type": "json_schema", "schema": _REFINE_JSON_SCHEMA}
            },
        )
        self.last_response = resp
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text")
        paraphrases = json.loads(text).get("paraphrases", [])
        out = [query] + [p for p in paraphrases if p != query]
        return out[: max(1, n)]


def _default_refiner() -> Refiner:
    """The zero-config refiner: :class:`AnthropicRefiner` when usable, else the fake."""
    from .decompose import _anthropic_available

    return AnthropicRefiner() if _anthropic_available() else KeywordRefiner()


def refine_query(
    query: str,
    *,
    n: int = 3,
    hint: Optional[str] = None,
    refiner: "Optional[Refiner]" = None,
    _span=None,
) -> "list[str]":
    """Expand ``query`` into up to ``n`` paraphrases for multi-query retrieval.

    Args:
        query: The event query to expand.
        n: Number of paraphrases.
        hint: Optional verify-failure reason to steer re-retrieval.
        refiner: An injected :class:`~foley.agent.protocols.Refiner` (the DI seam);
            defaults to :func:`_default_refiner`.
        _span: Internal — the obs span handle for GenAI recording.
    """
    refiner = refiner or _default_refiner()
    out = refiner.refine(query, n=n, hint=hint)
    record_genai(
        _span,
        request_model=getattr(refiner, "model", DEFAULT_AGENT_MODEL),
        response=getattr(refiner, "last_response", None),
    )
    return out
