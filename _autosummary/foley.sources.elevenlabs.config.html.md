# foley.sources.elevenlabs.config

`SOURCE_CONFIG` for the ElevenLabs Sound Effects generator (report 02 · 07 · 10 §4.1).

Stdlib-only and declarative — imports nothing heavy, so
[`foley.sources.registry.discover_sources()`](foley.sources.registry.html.md#foley.sources.registry.discover_sources) can read it cheaply (it imports
only `config.py`; the adapter + `requests` load lazily). It declares the hosted
Text-to-SFX v2 endpoint, the `xi-api-key` token auth, maps foley’s unified
[`GENERATION_AFFORDANCES`](foley.base.html.md#foley.base.GENERATION_AFFORDANCES) onto the native request fields, and — as
required for every source — the **license block**: `default_license_id='ElevenLabs-SFX'`
with `cache_bytes_ok=True` (generated audio is stored **by-value** — the opposite
of Freesound).

License note (report 07): the `ElevenLabs-SFX` row assumes a **paid** plan
(SFX royalty-free, embeddable in derivative works, no attribution). Free-tier
outputs are non-commercial + attribution-required — hence `tier_assumption`. The
Prohibited-Use policy forbids standalone redistribution of the raw SFX, which is
why the `LICENSE_FLAGS` row sets `redistribute_standalone_ok=False`.
