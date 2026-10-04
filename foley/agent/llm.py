"""Which LLM the SELECT rungs use — one explicit, spend-safe resolver (the ``llm=`` seam).

The decomposer, refiner and judges each have a hermetic fake and two real
implementations (a local OpenAI-compatible endpoint and Anthropic). Which one runs
used to depend on whether an API key happened to be in the environment, so a machine
with ``ANTHROPIC_API_KEY`` set turned every ``find()`` — and the test suite — into
paid calls. This module is the single place that choice is made, and a paid provider
is never chosen implicitly:

1. the explicit ``llm=`` argument (``'fake'`` | ``'local'`` | ``'anthropic'``), else
2. the ``$FOLEY_LLM`` environment variable (same values), else
3. the free default: ``'local'`` when a local endpoint is configured
   (``$FOLEY_LLM_BASE_URL``), otherwise ``'fake'``.

A key being present never upgrades anything. Asking for a provider that cannot run
(no SDK, no key, no endpoint) raises an error naming what is missing. Under
:func:`foley.offline` a provider that sends data off the device (Anthropic, or a
local-LLM URL that is not on this machine) raises :class:`~foley.runtime.EgressBlocked`.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

__all__ = ["LLM_ENV_VAR", "LLM_CHOICES", "resolve_llm", "llm_egress"]

#: The environment variable that opts in to a provider when ``llm=`` is not passed.
LLM_ENV_VAR = "FOLEY_LLM"

#: The accepted providers. ``'fake'`` is deterministic and free; the other two are real.
LLM_CHOICES = ("fake", "local", "anthropic")

#: Hosts that count as on-device for a local LLM endpoint.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def llm_egress(provider: str) -> str:
    """The ``data_egress`` class (``'local'`` | ``'external'``) of an LLM provider.

    ``'local'`` is on-device only when ``$FOLEY_LLM_BASE_URL`` points at a loopback
    host; an OpenAI-compatible server elsewhere on the network is external.
    """
    from ..runtime import EXTERNAL, LOCAL

    if provider == "fake":
        return LOCAL
    if provider == "local":
        host = urlparse(os.environ.get("FOLEY_LLM_BASE_URL", "")).hostname or ""
        return LOCAL if host in _LOOPBACK_HOSTS else EXTERNAL
    return EXTERNAL


def resolve_llm(llm: Optional[str] = None) -> str:
    """Resolve which LLM provider the SELECT rungs use (see the module docstring).

    Args:
        llm: ``'fake'`` | ``'local'`` | ``'anthropic'``, or ``None`` to read
            ``$FOLEY_LLM`` and then fall back to the free default.

    Returns:
        One of :data:`LLM_CHOICES`.

    Raises:
        ValueError: If ``llm`` (or ``$FOLEY_LLM``) is not one of :data:`LLM_CHOICES`.
        RuntimeError: If the requested provider cannot run (SDK, key or endpoint missing).
        EgressBlocked: If the provider sends data off the device under :func:`foley.offline`.
    """
    from .local_llm import local_llm_configured

    origin = "llm="
    if llm is None:
        llm = os.environ.get(LLM_ENV_VAR) or None
        origin = f"${LLM_ENV_VAR}"
    if llm is None:
        llm = "local" if local_llm_configured() else "fake"
        _require_egress(llm)
        return llm
    if llm not in LLM_CHOICES:
        raise ValueError(f"{origin} must be one of {LLM_CHOICES}, got {llm!r}")
    if llm == "anthropic":
        _require_anthropic()
    elif llm == "local" and not local_llm_configured():
        raise RuntimeError(
            f"{origin}'local' needs a local OpenAI-compatible endpoint: set "
            "$FOLEY_LLM_BASE_URL (e.g. http://localhost:11434/v1 for Ollama)."
        )
    _require_egress(llm)
    return llm


def _require_anthropic() -> None:
    """Raise unless the ``anthropic`` SDK is importable and a credential is set."""
    import importlib.util

    if importlib.util.find_spec("anthropic") is None:
        raise RuntimeError(
            "llm='anthropic' needs the SDK: pip install 'foley[agent]'."
        )
    if not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        raise RuntimeError(
            "llm='anthropic' needs a key: set $ANTHROPIC_API_KEY "
            "(get one at https://console.anthropic.com/settings/keys)."
        )


def _require_egress(provider: str) -> None:
    """Raise :class:`~foley.runtime.EgressBlocked` if the runtime forbids ``provider``."""
    from ..runtime import require_egress

    require_egress(llm_egress(provider), what=f"LLM provider {provider!r}")
