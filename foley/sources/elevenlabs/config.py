"""``SOURCE_CONFIG`` for the ElevenLabs Sound Effects generator (report 02 · 07 · 10 §4.1).

Stdlib-only and declarative — imports nothing heavy, so
:func:`foley.sources.registry.discover_sources` can read it cheaply (it imports
only ``config.py``; the adapter + ``requests`` load lazily). It declares the hosted
Text-to-SFX v2 endpoint, the ``xi-api-key`` token auth, maps foley's unified
:data:`~foley.base.GENERATION_AFFORDANCES` onto the native request fields, and — as
required for every source — the **license block**: ``default_license_id='ElevenLabs-SFX'``
with ``cache_bytes_ok=True`` (generated audio is stored **by-value** — the opposite
of Freesound).

License note (report 07): the ``ElevenLabs-SFX`` row assumes a **paid** plan
(SFX royalty-free, embeddable in derivative works, no attribution). Free-tier
outputs are non-commercial + attribution-required — hence ``tier_assumption``. The
Prohibited-Use policy forbids standalone redistribution of the raw SFX, which is
why the ``LICENSE_FLAGS`` row sets ``redistribute_standalone_ok=False``.
"""

from __future__ import annotations

SOURCE_CONFIG = {
    "name": "elevenlabs",
    "kind": "generate",
    "display_name": "ElevenLabs Sound Effects (Text-to-SFX v2)",
    "website": "https://elevenlabs.io/sound-effects",
    "auth": {
        "type": "token",
        "env_var": "ELEVENLABS_API_KEY",
        "header": "xi-api-key",  # 'xi-api-key: <key>' (keeps the key out of URLs)
        "apply_url": "https://elevenlabs.io/app/settings/api-keys",
    },
    "dependencies": [],
    "optional_dependencies": ["requests"],  # foley[elevenlabs]; imported lazily
    # unified foley GENERATION_AFFORDANCES -> ElevenLabs native request fields.
    # 'in' marks whether the field is a JSON body field or a URL query param.
    "param_map": {
        "prompt": {"native_name": "text", "required": True, "in": "body"},
        "duration": {"native_name": "duration_seconds", "in": "body"},  # None => auto
        "prompt_influence": {"native_name": "prompt_influence", "in": "body"},  # 0..1
        "loop": {"native_name": "loop", "in": "body"},  # v2 only (v2 is default)
        "output_format": {
            "native_name": "output_format",
            "in": "query",  # a URL query param, NOT a body field
            # coarse foley token -> concrete native enum (no lossless WAV container
            # in the SFX enum; 'wav' maps to mp3 and ingest re-archives to FLAC).
            "to_native_map": {
                "mp3": "mp3_44100_128",
                "opus": "opus_48000_128",
                "wav": "mp3_44100_128",
            },
        },
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "prompt_influence",
        "loop",
        "output_format",
    ],
    # No native equivalent on this endpoint (non-deterministic, no CFG/steps).
    "unsupported_affordances": ["negative_prompt", "steps", "seed"],
    "on_unsupported_param": "warn",
    "native_defaults": {
        "model_id": "eleven_text_to_sound_v2",  # NOT a foley affordance
        "generator_version": "eleven_text_to_sound_v2",
        "output_format": "mp3_44100_128",
        "duration_min_s": 0.5,
        "duration_max_s": 30.0,
    },
    "api": {
        "base_url": "https://api.elevenlabs.io",  # overridable for data-residency
        "generate_endpoint": {"method": "POST", "path": "/v1/sound-generation"},
    },
    "output": {"default_format": "mp3", "returns": "bytes", "storage": "by_value"},
    # MANDATORY license block (foley-dev-add-source) — the SSOT seed. cache_bytes_ok
    # True => by-value storage (the generation flywheel). commercial guardrail is
    # carried by the LICENSE_FLAGS row (commercial_ok=True, no revenue cap).
    "license": {
        "default_license_id": "ElevenLabs-SFX",
        "cache_bytes_ok": True,
        "tier_assumption": "paid",  # free-tier outputs are NC + attribution-required
    },
    "commercial_ok": True,  # generate guardrail (paid tier; no revenue cap)
    "rate": {"per_min": 60},
    "data_egress": "external",  # for offline/sensitive-narration mode (report 12)
}
