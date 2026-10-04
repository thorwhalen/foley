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


def llm_call_estimate(provider: str) -> Optional[float]:
    """The USD cost of one rung call: ``0.0`` for the fake and an on-device endpoint.

    Anthropic's (and a remote endpoint's) per-call cost depends on tokens foley does not
    know in advance, so it is ``None`` — unknown — and needs the run's approval (#57).
    """
    if provider == "fake" or (provider == "local" and _local_endpoint_is_loopback()):
        return 0.0
    return None


def guard_llm_call(provider: str) -> None:
    """The call-time check every real rung runs before calling its model.

    Egress (:func:`require_llm_egress`), then cost: the call is authorized against the
    active run's budget (:func:`foley.cost.authorize`) and charged. An unknown cost
    raises :class:`~foley.cost.CostApprovalRequired` unless the run approves it.
    """
    from ..cost import authorize, charge

    require_llm_egress(provider)
    estimate = llm_call_estimate(provider)
    if estimate != 0.0:
        authorize(estimate, what=f"an LLM call via {provider!r}")
    charge(estimate)


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
