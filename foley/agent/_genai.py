"""Shared GenAI-span recorder for the SELECT LLM rungs (decompose / refine / judge).

One small helper so the three tool wrappers record ``gen_ai.*`` span attributes the
same way (DRY), without a ``tools`` ↔ ``decompose``/``refine``/``verify`` import cycle.
It indexes the :data:`foley.obs.trace.GENAI` SSOT dict — the semconv strings are never
re-hardcoded here. The deterministic fakes pass ``response=None`` so this is a no-op
for them: obs never records synthetic token usage, staying truthful.
"""

from __future__ import annotations

#: The Anthropic model every real SELECT LLM rung calls (see the ``foley[agent]`` extra).
DEFAULT_AGENT_MODEL = "claude-opus-4-8"


def record_genai(span, *, request_model: str, response) -> None:
    """Set ``gen_ai.*`` attributes on ``span`` from an Anthropic ``Message`` ``response``.

    No-op when ``span`` or ``response`` is ``None`` — the fakes pass ``response=None``,
    so a fake-path ``find()`` records no LLM usage (obs stays truthful).

    Args:
        span: A recorder span handle (``set_attribute``); ``None`` when unrecorded.
        request_model: The model id requested (e.g. ``'claude-opus-4-8'``).
        response: The Anthropic ``Message`` (``.model`` / ``.usage`` / ``.stop_reason``),
            or ``None`` on the fake path.
    """
    if span is None or response is None:
        return
    from ..obs.trace import GENAI

    span.set_attribute(GENAI["operation"], "generate_content")
    span.set_attribute(GENAI["provider"], "anthropic")
    span.set_attribute(GENAI["request_model"], request_model)
    model = getattr(response, "model", None)
    if model:
        span.set_attribute(GENAI["response_model"], model)
    usage = getattr(response, "usage", None)
    if usage is not None:
        it = getattr(usage, "input_tokens", None)
        ot = getattr(usage, "output_tokens", None)
        if it is not None:
            span.set_attribute(GENAI["input_tokens"], it)
        if ot is not None:
            span.set_attribute(GENAI["output_tokens"], ot)
    stop = getattr(response, "stop_reason", None)
    if stop is not None:
        # gen_ai.response.finish_reasons is typed string[] in the semconv — wrap the scalar.
        span.set_attribute(GENAI["finish_reasons"], [stop])
