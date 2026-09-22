# foley.sources.stable_audio.config

`SOURCE_CONFIG` for the local Stable Audio Open 1.0 generator (report 02 · 07 · 10 §4.1).

Stdlib-only and declarative — imports neither `torch` nor `diffusers`, so
[`foley.sources.registry.discover_sources()`](foley.sources.registry.md#foley.sources.registry.discover_sources) can read it cheaply (it imports
only `config.py`; the adapter + the heavy ML stack load lazily on first
generation). It declares the local `diffusers.StableAudioPipeline` backend, maps
foley’s unified [`GENERATION_AFFORDANCES`](foley.base.md#foley.base.GENERATION_AFFORDANCES) onto the pipeline’s
native `__call__` params, and — as required for every source — the \*\*license
block\*\*: `default_license_id='Stability-Community'` with `cache_bytes_ok=True`
(generated audio is stored **by-value** — the generation flywheel).

Commercial guardrail (report 02/07): the Stability AI Community License permits
commercial use free **under $1M annual revenue**; that cap flows automatically from
the `LICENSE_FLAGS['Stability-Community']` row (`revenue_cap_usd=1_000_000`,
never hand-set) and is enforced by [`foley.keep()`](foley.md#foley.keep) at select time.

Two foley affordances have **no** native pipeline param — `loop` (a future WEAVE
crossfade) and `output_format` (the audio-write layer, not the model) — so they
are listed unsupported and warn-and-drop; the adapter never fabricates a kwarg.
