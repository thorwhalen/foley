"""``SOURCE_CONFIG`` for the local Stable Audio Open 1.0 generator (report 02 · 07 · 10 §4.1).

Stdlib-only and declarative — imports neither ``torch`` nor ``diffusers``, so
:func:`foley.sources.registry.discover_sources` can read it cheaply (it imports
only ``config.py``; the adapter + the heavy ML stack load lazily on first
generation). It declares the local ``diffusers.StableAudioPipeline`` backend, maps
foley's unified :data:`~foley.base.GENERATION_AFFORDANCES` onto the pipeline's
native ``__call__`` params, and — as required for every source — the **license
block**: ``default_license_id='Stability-Community'`` with ``cache_bytes_ok=True``
(generated audio is stored **by-value** — the generation flywheel).

Commercial guardrail (report 02/07): the Stability AI Community License permits
commercial use free **under $1M annual revenue**; that cap flows automatically from
the ``LICENSE_FLAGS['Stability-Community']`` row (``revenue_cap_usd=1_000_000``,
never hand-set) and is enforced by :func:`foley.keep` at select time.

Two foley affordances have **no** native pipeline param — ``loop`` (a future WEAVE
crossfade) and ``output_format`` (the audio-write layer, not the model) — so they
are listed unsupported and warn-and-drop; the adapter never fabricates a kwarg.
"""

from __future__ import annotations

SOURCE_CONFIG = {
    "name": "stable_audio",
    "kind": "generate",
    "display_name": "Stable Audio Open 1.0 (local diffusers)",
    "website": "https://huggingface.co/stabilityai/stable-audio-open-1.0",
    "auth": None,  # local model (a HF token is only needed if the repo is gated)
    "dependencies": [],
    "optional_dependencies": [
        "torch",
        "diffusers",
        "transformers",
        "soundfile",
        "accelerate",
    ],  # foley[stable-audio]; imported lazily inside the adapter
    # unified foley GENERATION_AFFORDANCES -> StableAudioPipeline native param names.
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {"native_name": "audio_end_in_s"},
        # foley prompt_influence (0..1) -> native guidance_scale via
        #   guidance_scale = 1 + prompt_influence * (cfg_max - 1)
        # NB: the CFG kwarg is 'guidance_scale' (NOT 'cfg_scale'); it must be passed
        # explicitly or the pipeline uses its own default 7.0.
        "prompt_influence": {"native_name": "guidance_scale"},
        "negative_prompt": {"native_name": "negative_prompt"},
        "steps": {"native_name": "num_inference_steps"},
        # foley seed -> a torch.Generator built in the adapter.
        "seed": {"native_name": "generator", "adapter_handled": True},
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "prompt_influence",
        "negative_prompt",
        "steps",
        "seed",
    ],
    # No native pipeline param: loop (future WEAVE crossfade), output_format
    # (audio-write layer). Warn-and-drop.
    "unsupported_affordances": ["loop", "output_format"],
    "on_unsupported_param": "warn",
    "native_defaults": {
        "model_id": "stabilityai/stable-audio-open-1.0",
        "generator_version": "stable-audio-open-1.0",
        "audio_start_in_s": 0.0,
        "duration_default_s": 10.0,  # NOT the 47.55s model max
        "duration_max_s": 47.55,
        "num_inference_steps_default": 200,
        "cfg_max": 15.0,  # prompt_influence=1.0 -> guidance_scale=15.0
        "num_waveforms_per_prompt": 1,
        "output_type": "np",
    },
    "output": {"default_format": "wav", "returns": "bytes", "storage": "by_value"},
    # MANDATORY license block (foley-dev-add-source) — the SSOT seed. cache_bytes_ok
    # True => by-value storage; the $1M revenue cap flows from the license_id row.
    "license": {
        "default_license_id": "Stability-Community",
        "cache_bytes_ok": True,
    },
    "commercial_ok": True,  # generate guardrail (revenue-capped; enforced by keep())
    "data_egress": "local",  # runs entirely on-device (offline-capable; report 12)
}
