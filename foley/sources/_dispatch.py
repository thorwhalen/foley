"""The one path every source call goes through: translate, note, gate, cache (#53 #57 #59).

Before this module each adapter hand-read its own config: ``on_unsupported_param`` was
declared everywhere and read nowhere, clamps were silent, Freesound dropped unknown
search kwargs, and nothing knew what a call cost. Now :func:`foley.generate` (and so
the MCP and agent paths, which call it) and :func:`foley.add_from` go through here:

1. **Egress** — :func:`~foley.sources.registry.require_source_egress` at call time, so
   an adapter fetched online and called inside :func:`foley.offline` is refused.
2. **Translate** — :func:`translate_affordances` keeps what the source's
   ``supported_affordances`` lists, clamps ``duration`` to the declared window, and
   applies the unsupported-parameter policy: a parameter whose
   :class:`~foley.base.Affordance` ``carries_meaning`` (``seed``, ``negative_prompt``)
   **raises** by default, anything else is dropped with a note (and a warning when
   the source's ``on_unsupported_param`` is ``'warn'``). Every drop and clamp becomes a
   note, and the notes reach the caller's result.
3. **Cost** — :func:`foley.cost.estimate_call` prices the call from
   ``SOURCE_CONFIG['pricing']``; :func:`foley.cost.authorize` refuses it before it is
   made if the run's cap would be exceeded or the cost is unknown and not approved.
4. **Cache** — a paid call is keyed by :func:`request_digest` (backend, model version,
   prompt, the affordances sent, and the adapter's ``request_salt()``); an identical
   request is served from the :class:`~foley.stores.GenerationsCache` without calling
   the provider, and every paid response is written there **before** QC or ingest.

The translator is the fleet's ``param_map`` translator (copied from ocracy's
``translation.py`` per the facade-design skill, with the ``note`` policy and
meaning-carrying raise that thorwhalen/ocracy#7 proposes for the shared kit).
"""

from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import dataclass, field
from typing import Optional

from ..base import GENERATION_AFFORDANCES, QUERY_AFFORDANCES

__all__ = [
    "UNSUPPORTED_POLICIES",
    "UnsupportedParameter",
    "translate_affordances",
    "request_digest",
    "GenerationPlan",
    "plan_generation",
    "run_generation",
    "plan_search",
]

#: How a parameter the source cannot honour is handled (``None`` = the source's default).
UNSUPPORTED_POLICIES = ("raise", "warn", "note")


class UnsupportedParameter(ValueError):
    """Raised when a backend cannot honour a parameter and the policy says not to drop it."""


def _carries_meaning(name: str, config: dict, vocabulary: dict) -> bool:
    aff = vocabulary.get(name)
    return bool(aff and aff.carries_meaning) or name in config.get("meaning_carrying", ())


def _is_default(name: str, value, vocabulary: dict) -> bool:
    aff = vocabulary.get(name)
    return value is None or (aff is not None and aff.default is not None and value == aff.default)


def translate_affordances(
    config: dict,
    affordances: dict,
    *,
    on_unsupported: Optional[str] = None,
    vocabulary: Optional[dict] = None,
) -> "tuple[dict, list[str]]":
    """Split ``affordances`` into what the source receives and a note for every change.

    Args:
        config: The source's ``SOURCE_CONFIG`` (``supported_affordances``,
            ``on_unsupported_param``, ``native_defaults`` duration window,
            optional ``meaning_carrying``).
        affordances: The canonical kwargs the caller passed.
        on_unsupported: ``'raise'`` | ``'warn'`` | ``'note'``; ``None`` (default):
            meaning-carrying parameters raise, others follow the source's
            ``on_unsupported_param`` (``'warn'`` = note + ``warnings.warn``).
        vocabulary: The canonical vocabulary (default: :data:`GENERATION_AFFORDANCES`).

    Returns:
        ``(kwargs for the adapter, notes)``.

    Raises:
        UnsupportedParameter: Per the policy.
        ValueError: If ``on_unsupported`` is not a known policy.
    """
    if on_unsupported is not None and on_unsupported not in UNSUPPORTED_POLICIES:
        raise ValueError(f"on_unsupported must be one of {UNSUPPORTED_POLICIES}")
    vocabulary = GENERATION_AFFORDANCES if vocabulary is None else vocabulary
    supported = set(config.get("supported_affordances") or ())
    source = config.get("name", "this source")
    kept: dict = {}
    notes: "list[str]" = []
    for name, value in affordances.items():
        if name in supported:
            kept[name] = value
            continue
        if _is_default(name, value, vocabulary):
            continue  # not asked for: nothing to drop
        kind = "not supported by" if name in vocabulary else "not a parameter of"
        msg = f"{name}={value!r} is {kind} {source}; dropped"
        policy = on_unsupported
        if policy is None:
            if _carries_meaning(name, config, vocabulary):
                policy = "raise"
            else:
                policy = "warn" if config.get("on_unsupported_param") == "warn" else "note"
        if policy == "raise":
            raise UnsupportedParameter(
                f"{name}={value!r} is {kind} {source}, and dropping it would change what "
                "you get. Remove it, pick a backend that supports it, or pass "
                "on_unsupported='warn' to drop it with a note."
            )
        if policy == "warn":
            warnings.warn(msg, UserWarning, stacklevel=4)
        notes.append(msg)
    _clamp_duration(kept, config, notes)
    return kept, notes


def _clamp_duration(kept: dict, config: dict, notes: list) -> None:
    """Clamp ``kept['duration']`` to the source's declared window, with a note."""
    duration = kept.get("duration")
    if duration is None:
        return
    nd = config.get("native_defaults") or {}
    lo, hi = nd.get("duration_min_s"), nd.get("duration_max_s")
    clamped = float(duration)
    if lo is not None:
        clamped = max(float(lo), clamped)
    if hi is not None:
        clamped = min(float(hi), clamped)
    if clamped != float(duration):
        notes.append(
            f"duration={duration!r} s is outside {config.get('name')}'s "
            f"[{lo}, {hi}] s window; clamped to {clamped:g} s"
        )
        kept["duration"] = clamped


def request_digest(backend: str, prompt: str, config: dict, affordances: dict, salt=None) -> str:
    """The cache key of a generation request (canonical JSON, SHA-256).

    Covers everything that decides the bytes and their licence: the backend, its model
    version, the prompt, the affordances sent, and the adapter's ``request_salt()``
    (ElevenLabs: the account plan, which decides the licence).
    """
    nd = config.get("native_defaults") or {}
    payload = {
        "backend": backend,
        "model": nd.get("generator_version") or nd.get("model_id"),
        "prompt": prompt,
        "affordances": affordances,
        "salt": salt,
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _is_paid(config: dict) -> bool:
    pricing = config.get("pricing") or {}
    return pricing.get("unit") != "free"


@dataclass
class GenerationPlan:
    """A generation call, fully decided before anything is spent (see :func:`plan_generation`)."""

    backend: str
    prompt: str
    config: dict
    affordances: dict
    notes: list = field(default_factory=list)
    estimate_usd: Optional[float] = None
    request_key: Optional[str] = None  # set for a paid call (the cache key)
    cached: object = None  # a GeneratedClip served from the cache, or None


def plan_generation(
    backend: str,
    prompt: str,
    *,
    adapter,
    config: Optional[dict] = None,
    on_unsupported: Optional[str] = None,
    cache=None,
    reuse_cached: bool = True,
    **affordances,
) -> GenerationPlan:
    """Decide a generation call: egress, translation, price, cache lookup, budget.

    Everything that can refuse the call happens here, before any provider is called.

    Args:
        backend: The source name.
        prompt: The prompt.
        adapter: The adapter that will run it (its ``config`` and ``request_salt``).
        config: The source config (default: ``adapter.config``, else the registry's).
        on_unsupported: See :func:`translate_affordances`.
        cache: A :class:`~foley.stores.GenerationsCache` (default: the local one).
        reuse_cached: Serve an identical paid request from the cache (default ``True``).
        **affordances: The canonical generation affordances.

    Raises:
        EgressBlocked: Under :func:`foley.offline` for an external source.
        UnsupportedParameter: Per the unsupported-parameter policy.
        CostApprovalRequired / BudgetExceeded: When the run cannot afford the call.
        SourceConfigurationError: When the adapter is not configured (key, plan).
    """
    from ..cost import authorize, estimate_call
    from .registry import SOURCE_REGISTRY, require_source_egress

    if config is None:
        config = getattr(adapter, "config", None) or SOURCE_REGISTRY.get(backend, {}).get(
            "config", {}
        )
    require_source_egress(backend, config)
    kept, notes = translate_affordances(config, affordances, on_unsupported=on_unsupported)
    plan = GenerationPlan(
        backend=backend,
        prompt=prompt,
        config=config,
        affordances=kept,
        notes=notes,
        estimate_usd=estimate_call(config, **kept),
    )
    if not _is_paid(config):
        return plan
    salt_fn = getattr(adapter, "request_salt", None)
    salt = salt_fn() if callable(salt_fn) else None  # may raise SourceConfigurationError
    plan.request_key = request_digest(backend, prompt, config, kept, salt)
    cache = cache if cache is not None else _default_cache()
    if reuse_cached:
        plan.cached = _cached_clip(cache, plan.request_key)
        if plan.cached is not None:
            return plan
    authorize(plan.estimate_usd, what=f"generate via {backend!r}")
    return plan


def run_generation(plan: GenerationPlan, adapter, *, cache=None):
    """Run a :class:`GenerationPlan`: call the adapter (or serve the cache) and keep the bytes.

    A paid response is written to the generations cache **before** it is returned (so
    before QC / ingest), and the request key is noted on the clip.

    Returns:
        The :class:`~foley.sources.base.GeneratedClip`, its notes prefixed with the
        plan's, and ``candidate.cost_estimate_usd`` / ``cost_actual_usd`` set.
    """
    from ..cost import charge

    if plan.cached is not None:
        clip = plan.cached
        clip.candidate.cost_estimate_usd = plan.estimate_usd
        clip.candidate.cost_actual_usd = 0.0
        clip.notes = [*plan.notes, *clip.notes]
        return clip
    clip = adapter.generate(plan.prompt, **plan.affordances)
    charge(plan.estimate_usd)
    clip.notes = [*plan.notes, *clip.notes]
    clip.candidate.cost_estimate_usd = plan.estimate_usd
    if plan.request_key is not None:
        cache = cache if cache is not None else _default_cache()
        _store_clip(cache, plan, clip)
        clip.notes.append(f"paid generation kept in the generations cache: {plan.request_key}")
    return clip


def _default_cache():
    from ..stores import make_generations_store

    return make_generations_store()


def _store_clip(cache, plan: GenerationPlan, clip) -> None:
    from ..stores import content_key

    key = content_key(clip.audio_bytes)
    cache.audio[key] = clip.audio_bytes
    sound = clip.candidate.sound
    cache.requests[plan.request_key] = {
        "content_key": key,
        "backend": plan.backend,
        "prompt": plan.prompt,
        "affordances": plan.affordances,
        "license": sound.license.to_dict(),
        "caption": sound.caption,
        "tags": list(sound.tags or []),
        "notes": list(clip.notes),
        "estimate_usd": plan.estimate_usd,
    }


def _cached_clip(cache, request_key: str):
    """Rebuild the :class:`GeneratedClip` of a cached request, or ``None``."""
    from ..base import Candidate, CandidateOrigin, LicenseRecord, SoundRecord
    from .base import GeneratedClip

    entry = cache.requests.get(request_key) if hasattr(cache.requests, "get") else None
    if not entry or entry.get("content_key") not in cache.audio:
        return None
    record = SoundRecord(
        id=f"{entry['backend']}:pending",
        license=LicenseRecord.from_dict(entry["license"]),
        caption=entry.get("caption"),
        tags=list(entry.get("tags") or []),
    )
    return GeneratedClip(
        audio_bytes=cache.audio[entry["content_key"]],
        candidate=Candidate(sound=record, origin=CandidateOrigin.generated),
        notes=[f"served from the generations cache ({request_key}); no paid call"],
    )


def plan_search(
    source: str, config: dict, affordances: dict, *, on_unsupported: Optional[str] = None
) -> "tuple[dict, list[str]]":
    """Egress check + translation for a retrieve source's ``search`` (the same policy).

    Returns:
        ``(kwargs for adapter.search, notes)``.
    """
    from .registry import require_source_egress

    require_source_egress(source, config)
    return translate_affordances(
        config, affordances, on_unsupported=on_unsupported, vocabulary=QUERY_AFFORDANCES
    )
