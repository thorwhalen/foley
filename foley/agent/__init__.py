"""The SELECT stage — the search-agent that finds the right sound for a context (#7).

The headline capability: a narrative *context* → verified, license-clean sound
candidates, and the sparse plan that places them. The loop (report 05 §5):

    decompose_context → (per event) refine_query / search_sounds
      → gate_candidates (fail-closed license gate, FIRST)
      → verify_match (clap → listen → judge ladder)
      → decide (retrieve-vs-generate, the single branch)
      → place_in_timeline → a sparse SoundDesignTimeline

Design discipline (mirrors ``foley.index``): this package is **dol-only at import** —
the LLM rungs sit behind the :class:`Decomposer` / :class:`Judge` / :class:`Refiner`
protocols with deterministic fakes as defaults, and ``anthropic`` (the ``foley[agent]``
extra) is imported lazily inside the real impls only. So ``foley.find("a paragraph")``
works out of the box and the whole loop is exercisable in CI with no network / key /
heavy dependency. Every ``find()`` opens one ``foley.obs`` run scope, so search +
verify + generate aggregate into a single reproducible run-manifest.
"""

from __future__ import annotations

from .decompose import (
    AnthropicDecomposer,
    KeywordDecomposer,
    decompose_context,
)
from .policy import Budget, DecideAction, Decision, decide, gate_candidates
from .protocols import Decomposer, Judge, Refiner
from .refine import AnthropicRefiner, KeywordRefiner, refine_query
from .tools import (
    find,
    generate_sound,
    place_in_timeline,
    plan,
    search_sounds,
)
from .verify import (
    AnthropicJudge,
    AudioLMJudge,
    ClapJudge,
    StringOverlapJudge,
    verify_match,
)

__all__ = [
    # headline façade
    "find",
    "plan",
    # the pure tools (Python-API == agent == future-MCP surface)
    "decompose_context",
    "refine_query",
    "search_sounds",
    "verify_match",
    "gate_candidates",
    "decide",
    "generate_sound",
    "place_in_timeline",
    # DI seams (protocols)
    "Decomposer",
    "Judge",
    "Refiner",
    # policy shapes
    "Budget",
    "Decision",
    "DecideAction",
    # impls (defaults + fakes + real, behind foley[agent])
    "KeywordDecomposer",
    "AnthropicDecomposer",
    "KeywordRefiner",
    "AnthropicRefiner",
    "ClapJudge",
    "StringOverlapJudge",
    "AnthropicJudge",
    "AudioLMJudge",
]
