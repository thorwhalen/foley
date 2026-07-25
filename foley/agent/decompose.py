"""``decompose_context`` — narrative passage → a sparse, salience-ranked event list.

The moat of the SELECT stage (report 05 §2): turning prose into a *tastefully sparse,
correctly-diegetic* :class:`~foley.base.SoundEvent` list is the hard, defensible part —
not the CLAP encoder. Two impls sit behind the :class:`~foley.agent.protocols.Decomposer`
seam:

* :class:`KeywordDecomposer` — the deterministic default *and* the hermetic CI fake:
  a built-in cue lexicon, zero dependencies, same passage → identical list.
* :class:`AnthropicDecomposer` — the LLM-backed impl behind the ``foley[agent]`` extra;
  ``anthropic`` is imported lazily **inside** ``.decompose`` only, so ``import foley``
  stays dol-only.

:func:`decompose_context` is the pure tool wrapper (Python-API == agent == future-MCP
surface): it resolves the default decomposer, calls it, and records the GenAI span on
the real path.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from ..base import Layer, Salience, SoundEvent
from ._genai import DEFAULT_AGENT_MODEL, record_genai
from .protocols import Decomposer

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


# ---------------------------------------------------------------------------
# The deterministic default / CI fake
# ---------------------------------------------------------------------------

#: Cue lexicon: a matched keyword → ``(canonical query, layer, diegetic, loop)``.
#: Ambience beds loop; a heartbeat is a non-diegetic tension cue (audience-only). The
#: KeywordDecomposer scans a passage against these and emits one event per matched cue
#: in first-appearance order (so the salience ranking falls out of reading order).
_CUE_LEXICON: "tuple[tuple[str, str, Layer, bool, bool], ...]" = (
    # keyword,   canonical query,                 layer,          diegetic, loop
    ("door", "heavy wooden door creaking open", Layer.sfx_fg, True, False),
    ("creak", "wood creaking", Layer.sfx_fg, True, False),
    ("footstep", "footsteps on a hard floor", Layer.sfx_fg, True, False),
    ("thunder", "distant thunder rumble", Layer.sfx_fg, True, False),
    ("rain", "steady rain ambience", Layer.ambience, True, True),
    ("storm", "howling storm wind bed", Layer.ambience, True, True),
    ("wind", "gusting wind ambience", Layer.ambience, True, True),
    ("ocean", "ocean waves on a shore", Layer.ambience, True, True),
    ("wave", "ocean waves on a shore", Layer.ambience, True, True),
    ("fire", "crackling fire", Layer.ambience, True, True),
    ("gun", "gunshot", Layer.sfx_fg, True, False),
    ("shot", "gunshot", Layer.sfx_fg, True, False),
    ("glass", "glass shattering", Layer.sfx_fg, True, False),
    ("bell", "a ringing bell", Layer.sfx_fg, True, False),
    ("phone", "a ringing telephone", Layer.sfx_fg, True, False),
    ("clock", "a ticking clock", Layer.sfx_fg, True, False),
    ("bird", "birds chirping", Layer.ambience, True, True),
    ("dog", "a dog barking", Layer.sfx_fg, True, False),
    ("bark", "a dog barking", Layer.sfx_fg, True, False),
    ("cat", "a cat meowing", Layer.sfx_fg, True, False),
    ("car", "a passing car", Layer.sfx_fg, True, False),
    ("engine", "an engine running", Layer.sfx_fg, True, False),
    ("crowd", "a murmuring crowd", Layer.ambience, True, True),
    ("footsteps", "footsteps on a hard floor", Layer.sfx_fg, True, False),
    ("heartbeat", "a slow heartbeat", Layer.stinger, False, True),
    ("scream", "a distant scream", Layer.sfx_fg, True, False),
    ("water", "running water", Layer.ambience, True, True),
)

#: Salience by first-appearance rank (report 05 §2.3: cap density, rank by prominence).
_SALIENCE_BY_RANK: "tuple[Salience, ...]" = (
    Salience.high,
    Salience.medium,
    Salience.low,
)


class KeywordDecomposer:
    """Deterministic cue-lexicon decomposer — the zero-dependency default and CI fake.

    Scans the passage against :data:`_CUE_LEXICON`, emits one :class:`SoundEvent` per
    matched cue in first-appearance order (so salience descends with reading order),
    dedupes by canonical query, and truncates to ``max_events`` (the sparse density
    budget). No RNG, no network, no ``anthropic`` — same passage → identical list.
    """

    def decompose(
        self, context: str, *, max_events: int = 6, seconds: Optional[float] = None
    ) -> "list[SoundEvent]":
        """Return ``<= max_events`` deterministic :class:`SoundEvent`\\ s for ``context``.

        Args:
            context: The narrative passage.
            max_events: The sparse density cap (the salience budget).
            seconds: Accepted for signature parity (the per-second density window is a
                later refinement); ignored here.
        """
        text = context.lower()
        matched: "list[tuple[int, str, Layer, bool, bool]]" = []
        seen_queries: "set[str]" = set()
        for keyword, query, layer, diegetic, loop in _CUE_LEXICON:
            m = re.search(r"\b" + re.escape(keyword), text)
            if m is None or query in seen_queries:
                continue
            seen_queries.add(query)
            matched.append((m.start(), query, layer, diegetic, loop))
        matched.sort(
            key=lambda t: t[0]
        )  # first-appearance order == descending salience
        events: "list[SoundEvent]" = []
        for rank, (pos, query, layer, diegetic, loop) in enumerate(
            matched[:max_events]
        ):
            salience = _SALIENCE_BY_RANK[min(rank, len(_SALIENCE_BY_RANK) - 1)]
            keyword = re.findall(r"[a-z0-9]+", text[pos:])[:1]
            onset = f"on '{keyword[0]}'" if keyword else None
            events.append(
                SoundEvent(
                    query=query,
                    layer=layer,
                    diegetic=diegetic,
                    salience=salience,
                    onset=onset,
                    loop=loop,
                )
            )
        return events


# ---------------------------------------------------------------------------
# The real, LLM-backed impl (behind foley[agent]; anthropic imported lazily)
# ---------------------------------------------------------------------------

#: The structured-output schema for one decomposed event. Keys MUST equal
#: ``SoundEvent`` field names exactly (``ucs_catid`` not ``ucs_category``; ``audioset`` a
#: list) — :meth:`SoundEvent.from_dict` coerces enums and silently drops unknown keys.
_EVENT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "layer": {
                        "type": "string",
                        "enum": ["voice", "sfx_fg", "ambience", "stinger", "music"],
                    },
                    "diegetic": {"type": "boolean"},
                    "salience": {"type": "string", "enum": ["high", "medium", "low"]},
                    "onset": {"type": ["string", "null"]},
                    "loop": {"type": "boolean"},
                    "era_place": {"type": ["string", "null"]},
                },
                "required": ["query", "layer", "diegetic", "salience"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}

_DECOMPOSE_SYSTEM = (
    "You are a Foley sound designer. Given a narrative passage, list the discrete, "
    "physically-audible sound EVENTS a listener would hear — not every clause, only the "
    "salient ones. Rank by narrative salience (high|medium|low) and keep the list SPARSE. "
    "Tag each event: diegetic (true = exists in the story world; false = a non-diegetic, "
    "audience-only mood cue that will be generated, not retrieved). Mark loop=true for a "
    "sustained ambience bed. Set onset to a short SYMBOLIC anchor phrase quoting the words "
    "the sound lands on (e.g. \"on 'pushed open'\"), never a number. If the passage fixes an "
    "era or place, set era_place so anachronistic sounds are avoided. Return ONLY the "
    "structured event list."
)


class AnthropicDecomposer:
    """LLM-backed decomposer (``foley[agent]``): Claude → a structured event list.

    ``anthropic`` is imported lazily inside :meth:`decompose` so ``import foley`` stays
    dol-only. Stashes the returned ``Message`` on ``self.last_response`` so
    :func:`decompose_context` can record the GenAI span (token usage / model /
    stop_reason). Model, thinking, and structured-output shape follow the ``claude-api``
    conventions (``claude-opus-4-8``, adaptive thinking — never ``budget_tokens``).
    """

    def __init__(
        self, *, client=None, model: str = DEFAULT_AGENT_MODEL, max_tokens: int = 2000
    ):
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.last_response = None

    def decompose(
        self, context: str, *, max_events: int = 6, seconds: Optional[float] = None
    ) -> "list[SoundEvent]":
        """Call Claude and round-trip each event through :meth:`SoundEvent.from_dict`."""
        import json

        client = self._client
        if client is None:
            import anthropic  # lazy — only on the real path, behind foley[agent]

            client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=_DECOMPOSE_SYSTEM
            + f" Emit at most {max_events} events, most salient first.",
            messages=[{"role": "user", "content": context}],
            output_config={
                "format": {"type": "json_schema", "schema": _EVENT_JSON_SCHEMA}
            },
        )
        self.last_response = resp
        text = next(b.text for b in resp.content if getattr(b, "type", None) == "text")
        data = json.loads(text)
        return [SoundEvent.from_dict(e) for e in data.get("events", [])][:max_events]


# ---------------------------------------------------------------------------
# Default resolution + the pure tool wrapper
# ---------------------------------------------------------------------------


def _anthropic_available() -> bool:
    """True iff the ``anthropic`` SDK is importable AND a credential is configured.

    Mirrors foley's progressive-disclosure rule: auto-upgrade to the LLM path only when
    it can actually run (``foley[agent]`` installed + a key), else the hermetic fake.
    """
    import importlib.util
    import os

    if importlib.util.find_spec("anthropic") is None:
        return False
    return bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


def _default_decomposer() -> Decomposer:
    """The zero-config decomposer: local LLM if configured, else Anthropic, else the fake."""
    from .local_llm import LocalLLMDecomposer, local_llm_configured

    if local_llm_configured():
        return LocalLLMDecomposer()
    return AnthropicDecomposer() if _anthropic_available() else KeywordDecomposer()


def decompose_context(
    context: str,
    *,
    max_events: int = 6,
    seconds: Optional[float] = None,
    decomposer: "Optional[Decomposer]" = None,
    _span=None,
) -> "list[SoundEvent]":
    """Decompose a passage into ``<= max_events`` sparse :class:`SoundEvent`\\ s.

    The pure SELECT tool (Python-API == agent == future-MCP surface): resolves the
    default decomposer when ``decomposer`` is ``None``, calls it, and records the GenAI
    span on the real path (the fake's ``last_response`` is ``None`` → no-op).

    Args:
        context: The narrative passage.
        max_events: The sparse density cap.
        seconds: Optional passage duration (density-window hint; forwarded, else ignored).
        decomposer: An injected :class:`~foley.agent.protocols.Decomposer` (the DI seam);
            defaults to :func:`_default_decomposer`.
        _span: Internal — the obs span handle ``find()`` opens for GenAI recording.
    """
    decomposer = decomposer or _default_decomposer()
    events = decomposer.decompose(context, max_events=max_events, seconds=seconds)
    record_genai(
        _span,
        request_model=getattr(decomposer, "model", DEFAULT_AGENT_MODEL),
        response=getattr(decomposer, "last_response", None),
    )
    return events
