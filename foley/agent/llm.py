"""Which LLM the SELECT rungs use — one explicit, spend-safe resolver (the ``llm=`` seam).

The decomposer, refiner and judges each have a hermetic fake and two real
implementations (a local OpenAI-compatible endpoint and Anthropic). Which one runs
used to depend on whether an API key happened to be in the environment, so a machine
with ``ANTHROPIC_API_KEY`` set turned every ``find()`` — and the test suite — into
paid calls. This module is the single place that choice is made, and a paid or remote
provider is never chosen implicitly:

1. the explicit ``llm=`` argument (``'fake'`` | ``'local'`` | ``'anthropic'``), else
2. the ``$FOLEY_LLM`` environment variable (same values), else
3. the free default: ``'local'`` when ``$FOLEY_LLM_BASE_URL`` is a loopback endpoint
   (Ollama, llama.cpp on this machine), otherwise ``'fake'``. A remote endpoint (an
   OpenAI-compatible cloud API) may cost money, so it needs ``llm='local'``.

A key being present never upgrades anything. Asking for a provider that cannot run
(no SDK, no key, no endpoint) raises an error naming what is missing. Under
:func:`foley.offline` a provider that sends data off the device raises
:class:`~foley.runtime.EgressBlocked` — at resolution time *and* when a real rung is
called (:func:`require_llm_egress`), so an injected ``AnthropicJudge()`` is covered too.

:data:`PROVIDERS` is the provider table: each provider's rung classes. It is the one
place a new provider, or per-provider cost data, is added.
"""

from __future__ import annotations

import importlib
import os
import warnings
from typing import Optional
from urllib.parse import urlparse

__all__ = [
    "LLM_ENV_VAR",
    "LLM_CHOICES",
    "PROVIDERS",
    "resolve_llm",
    "make_rung",
    "llm_egress",
    "require_llm_egress",
    "llm_call_estimate",
    "guard_llm_call",
    "charge_llm_call",
    "RUNG_MAX_TOKENS",
    "is_loopback_host",
]

#: The environment variable that opts in to a provider when ``llm=`` is not passed.
LLM_ENV_VAR = "FOLEY_LLM"

#: provider -> rung kind -> ``"module:Class"`` (imported lazily; the real ones need extras).
PROVIDERS: "dict[str, dict[str, str]]" = {
    "fake": {
        "decomposer": "foley.agent.decompose:KeywordDecomposer",
        "refiner": "foley.agent.refine:KeywordRefiner",
        "judge": "foley.agent.verify:StringOverlapJudge",
    },
    "local": {
        "decomposer": "foley.agent.local_llm:LocalLLMDecomposer",
        "refiner": "foley.agent.local_llm:LocalLLMRefiner",
        "judge": "foley.agent.local_llm:LocalLLMJudge",
    },
    "anthropic": {
        "decomposer": "foley.agent.decompose:AnthropicDecomposer",
        "refiner": "foley.agent.refine:AnthropicRefiner",
        "judge": "foley.agent.verify:AnthropicJudge",
    },
}

#: The accepted providers. ``'fake'`` is deterministic and free; the other two are real.
LLM_CHOICES = tuple(PROVIDERS)

#: Credentials that, when set without an opt-in, suggest the user expected the old upgrade.
_PAID_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
_warned_unused_key = False


def is_loopback_host(host: Optional[str]) -> bool:
    """Whether ``host`` is this machine (``localhost``, ``127.*``, ``::1``, ``0.0.0.0``)."""
    if not host:
        return False
    return host in ("localhost", "::1", "0.0.0.0") or host.startswith("127.")


def _local_endpoint_is_loopback() -> bool:
    return is_loopback_host(urlparse(os.environ.get("FOLEY_LLM_BASE_URL", "")).hostname)


def llm_egress(provider: str) -> str:
    """The ``data_egress`` class (``'local'`` | ``'external'``) of an LLM provider."""
    from ..runtime import EXTERNAL, LOCAL

    if provider == "fake":
        return LOCAL
    if provider == "local":
        return LOCAL if _local_endpoint_is_loopback() else EXTERNAL
    return EXTERNAL


def require_llm_egress(provider: str) -> None:
    """Raise :class:`~foley.runtime.EgressBlocked` if the runtime forbids ``provider`` now.

    Called by :func:`resolve_llm` and again by each real rung right before it calls its
    model, so a rung built online and called inside :func:`foley.offline` is refused.
    """
    from ..runtime import require_egress

    require_egress(llm_egress(provider), what=f"LLM provider {provider!r}")


#: Anthropic first-party prices, USD per million tokens ``(input, output)``. Source: the
#: Claude API model table (claude-api reference, cached 2026-09-25). A model not listed
#: here has an unknown price, so its calls need the run's approval.
ANTHROPIC_PRICES_PER_MTOK: "dict[str, tuple[float, float]]" = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
PRICES_SEEN = "2026-09-25"

#: The input-token bound assumed for one rung call (system prompt + schema + passage).
#: The rungs send short prompts; this is a deliberately generous ceiling.
INPUT_TOKEN_BOUND = 4000

#: Default ``max_tokens`` of each rung (the classes read these, so estimates match).
RUNG_MAX_TOKENS = {"decomposer": 2000, "refiner": 500, "judge": 500}


def llm_call_estimate(
    provider: str, *, model: Optional[str] = None, max_tokens: Optional[int] = None
) -> Optional[float]:
    """An upper bound on one rung call's USD cost, or ``None`` when it is unknown.

    ``0.0`` for the fake and an on-device endpoint. For Anthropic:
    ``INPUT_TOKEN_BOUND`` × input price + ``max_tokens`` × output price (thinking
    tokens count toward ``max_tokens``, so the bound holds). A remote endpoint, or an
    Anthropic model with no listed price, is ``None``.
    """
    if provider == "fake" or (provider == "local" and _local_endpoint_is_loopback()):
        return 0.0
    if provider != "anthropic":
        return None
    from ._genai import DEFAULT_AGENT_MODEL

    prices = ANTHROPIC_PRICES_PER_MTOK.get(model or DEFAULT_AGENT_MODEL)
    if prices is None:
        return None
    tokens_out = max_tokens if max_tokens is not None else max(RUNG_MAX_TOKENS.values())
    return (INPUT_TOKEN_BOUND * prices[0] + tokens_out * prices[1]) / 1e6


def _usage_cost(model: Optional[str], response) -> Optional[float]:
    """The actual USD cost of an Anthropic response from its ``usage``, if priceable."""
    from ._genai import DEFAULT_AGENT_MODEL

    usage = getattr(response, "usage", None)
    prices = ANTHROPIC_PRICES_PER_MTOK.get(model or DEFAULT_AGENT_MODEL)
    tin = getattr(usage, "input_tokens", None)
    tout = getattr(usage, "output_tokens", None)
    if prices is None or not isinstance(tin, int) or not isinstance(tout, int):
        return None
    return (tin * prices[0] + tout * prices[1]) / 1e6


def guard_llm_call(
    provider: str, *, model: Optional[str] = None, max_tokens: Optional[int] = None
) -> Optional[float]:
    """The call-time check every real rung runs before calling its model.

    Egress (:func:`require_llm_egress`), then cost: the call's upper bound
    (:func:`llm_call_estimate`) is authorized against every budget in force
    (:func:`foley.cost.authorize`) — so paid LLM calls count toward the run's
    ``max_usd`` — and an unknown cost needs approval. Call :func:`charge_llm_call`
    after the response.

    Returns:
        The estimate (pass it to :func:`charge_llm_call`).
    """
    from ..cost import authorize

    require_llm_egress(provider)
    estimate = llm_call_estimate(provider, model=model, max_tokens=max_tokens)
    if estimate != 0.0:
        authorize(estimate, what=f"an LLM call via {provider!r}")
    return estimate


def charge_llm_call(estimate: Optional[float], *, model=None, response=None) -> None:
    """Charge a rung call: its actual cost from ``response.usage`` when priceable, else the estimate."""
    from ..cost import charge

    actual = _usage_cost(model, response) if response is not None else None
    charge(actual if actual is not None else estimate)


def resolve_llm(llm: Optional[str] = None, *, implicit_local: bool = True) -> str:
    """Resolve which LLM provider the SELECT rungs use (see the module docstring).

    Args:
        llm: ``'fake'`` | ``'local'`` | ``'anthropic'``, or ``None`` to read
            ``$FOLEY_LLM`` and then fall back to the free default.
        implicit_local: Whether the free default may be a loopback local endpoint.
            ``False`` keeps the default the deterministic fake (the hermetic eval).

    Returns:
        One of :data:`LLM_CHOICES`.

    Raises:
        ValueError: If ``llm`` (or ``$FOLEY_LLM``) is not one of :data:`LLM_CHOICES`.
        RuntimeError: If the requested provider cannot run (SDK, key or endpoint missing).
        EgressBlocked: If the provider sends data off the device under :func:`foley.offline`.
    """
    origin = "llm="
    if llm is None:
        llm = os.environ.get(LLM_ENV_VAR) or None
        origin = f"${LLM_ENV_VAR}="
    if llm is None:
        _warn_once_if_key_unused()
        use_local = implicit_local and _local_endpoint_is_loopback()
        return "local" if use_local else "fake"
    if llm not in LLM_CHOICES:
        raise ValueError(f"{origin} must be one of {LLM_CHOICES}, got {llm!r}")
    if llm == "anthropic":
        _require_anthropic()
    elif llm == "local" and not os.environ.get("FOLEY_LLM_BASE_URL"):
        raise RuntimeError(
            f"{origin}'local' needs an OpenAI-compatible endpoint: set "
            "$FOLEY_LLM_BASE_URL (e.g. http://localhost:11434/v1 for Ollama)."
        )
    require_llm_egress(llm)
    return llm


def make_rung(
    kind: str, llm: Optional[str] = None, *, implicit_local: bool = True, **kwargs
):
    """Build the ``kind`` rung (``'decomposer'`` | ``'refiner'`` | ``'judge'``) for ``llm``.

    Args:
        kind: The rung kind (a key of each :data:`PROVIDERS` row).
        llm: The provider (see :func:`resolve_llm`).
        implicit_local: Forwarded to :func:`resolve_llm`.
        **kwargs: Passed to the rung's constructor.
    """
    provider = resolve_llm(llm, implicit_local=implicit_local)
    module_name, _, class_name = PROVIDERS[provider][kind].partition(":")
    return getattr(importlib.import_module(module_name), class_name)(**kwargs)


def _warn_once_if_key_unused() -> None:
    """Tell a user whose key used to switch on Claude that it no longer does (once)."""
    global _warned_unused_key
    if _warned_unused_key or not any(os.environ.get(v) for v in _PAID_KEY_VARS):
        return
    _warned_unused_key = True
    warnings.warn(
        "ANTHROPIC_API_KEY is set but foley's SELECT rungs use the free fakes: a key no "
        f"longer opts in to paid calls. Pass llm='anthropic' or set {LLM_ENV_VAR}=anthropic.",
        UserWarning,
        stacklevel=4,
    )


def _require_anthropic() -> None:
    """Raise unless the ``anthropic`` SDK is importable and a credential is set."""
    import importlib.util

    if importlib.util.find_spec("anthropic") is None:
        raise RuntimeError("llm='anthropic' needs the SDK: pip install 'foley[agent]'.")
    if not any(os.environ.get(v) for v in _PAID_KEY_VARS):
        raise RuntimeError(
            "llm='anthropic' needs a key: set $ANTHROPIC_API_KEY "
            "(get one at https://console.anthropic.com/settings/keys)."
        )
