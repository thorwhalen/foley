# foley.sources.elevenlabs

ElevenLabs Sound Effects generate source (hosted; #6).

Auto-discovered by [`foley.sources.registry.discover_sources()`](foley.sources.registry.md#foley.sources.registry.discover_sources), which imports
ONLY [`config`](foley.sources.elevenlabs.config.md#module-foley.sources.elevenlabs.config) (stdlib-only). The
[`ElevenLabsAdapter`](foley.sources.elevenlabs.adapter.md#foley.sources.elevenlabs.adapter.ElevenLabsAdapter) and its lazy
`requests` dependency (the `foley[elevenlabs]` extra) load on first use — never
at `import foley` or during discovery — via the module `__getattr__` below.

### Classes

| `Adapter`                                    |                                                                                                                                                    |
|----------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| `ElevenLabsAdapter`([config, api_key, http]) | ElevenLabs Sound Effects generate adapter (a [`GenerateAdapter`](foley.sources.base.md#foley.sources.base.GenerateAdapter)). |

### Modules

| [`adapter`](foley.sources.elevenlabs.adapter.md#module-foley.sources.elevenlabs.adapter)   | ElevenLabs Sound Effects generate adapter — hosted Text-to-SFX v2 over HTTP.           |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| [`config`](foley.sources.elevenlabs.config.md#module-foley.sources.elevenlabs.config)     | `SOURCE_CONFIG` for the ElevenLabs Sound Effects generator (report 02 · 07 · 10 §4.1). |
