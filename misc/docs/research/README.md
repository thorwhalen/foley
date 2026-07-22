# foley — research

This folder is foley's research home (same convention as `arioso`'s `misc/docs/`).

## Contents

- **`deep-research-prompts.md`** — the prompt library: 12 ready-to-run deep-research
  prompts covering every dimension of the project (source → index → select → weave,
  plus licensing, evaluation, architecture, and the "what are we forgetting" scan).
  Hand any prompt to a research-capable agent to (re)generate or deepen a report.
- **`01-sfx-source-apis.md`** — where foley gets ready-made sounds (Freesound, BBC,
  Zapsplat, … + UCS taxonomy). *(Prompt 1)*
- **`02-genai-sfx-generation.md`** — generating sounds (local models + hosted APIs:
  AudioGen, Stable Audio, ElevenLabs SFX, …). *(Prompt 2)*
- **`03-sound-recognition-tagging.md`** — turning raw audio into searchable metadata
  (tagging, zero-shot CLAP, captioning, segmentation). *(Prompt 3)*
- **`04-embeddings-indexing-search.md`** — embeddings (CLAP), vector stores, hybrid
  search, and the sound metadata schema. *(Prompt 4)*
- **`05-context-retrieval-and-agent.md`** — the core: narrative-context → right sound,
  and the search-agent / MCP design. *(Prompt 5)*

Reports `06`–`12` are not yet generated — run Prompts 6–12 from the prompt library to
produce them.

## Conventions

- Vancouver-style numbered citations (`[1]`, `[2]`, …) + a `REFERENCES` section with
  `[name](url)` links.
- Primary sources over blogs; note versions/access dates (this landscape moves fast).
- Every report ends with a **"Recommendations for foley"** section mapping findings to
  the façade design.

## Status

Reports 01–05 were produced by an initial background research pass. They are a
*starting point*, meant to be extended by re-running their prompts (and by running the
remaining prompts 06–12).
