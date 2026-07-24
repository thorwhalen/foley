# foley

Find (or generate) the **right sound effect for a moment of narration** — and weave it in.

foley is a **retrieval-first façade for sound effects**: one simple surface over many
sound *sources* (your own library, service APIs, and generative-AI models), a searchable
*index* of every sound (by keyword **and** meaning), an *agent* that picks the right
sound for a narrative context, and a *compositor* that places it under the voice.

It's the SFX sibling of [`arioso`](https://github.com/thorwhalen/arioso) (a unified
façade over AI music-generation backends): same discipline — one entry function,
config-driven plugin adapters, a unified vocabulary translated per-backend, zero
required core deps with lazy optional-deps — but centered on **search** rather than
generation, with generation as just one of several sources.

> **Status: design-stage.** The architecture is researched and specified; the code is
> being built. The API below is the *intended* surface (see the roadmap for what's
> live). Follow along in [`misc/docs/`](misc/docs/).

## The idea

```python
import foley

# The headline — right sounds for a narrative context:
# decompose the passage into salient sound events → search → verify → decide
candidates = foley.find("She pushed open the heavy oak door; rain hammered outside.")

# Direct hybrid search of your library (text query or a reference clip)
hits = foley.search("distant thunder rumble", k=10, commercial_ok=True)

# Generate a sound when nothing fits (arioso-style; pluggable backends)
clip = foley.generate(
    "a single wooden door creak", backend="stable_audio_open", duration=3
)

# Grow the library — ingest auto-tags, captions, and embeds every file
foley.ingest("~/my_sounds/")
foley.add_from("freesound", query="ocean waves", license="cc0")

# Compose (future): render the sound design onto a narration
foley.weave(narration_audio, candidates)
```

## How it works — four stages

| Stage | What it does | Built on |
|-------|--------------|----------|
| **Source** | your own files · Freesound (CC0) · generate (Stable Audio Open / ElevenLabs) | config-driven adapters, per-sound license tracking |
| **Index** | probe → tag → caption → embed every sound; hybrid keyword+semantic search | PANNs · CLAP · EnCLAP · LanceDB (local→cloud via `dol`) |
| **Select** | decompose a narrative context → search → verify → generate-or-retrieve | CLAP retrieval + LLM decomposition + a verification ladder |
| **Weave** | align to the voice, duck, place, master *(future)* | forced-alignment · LUFS/EBU-R128 |

The selection tools publish as an **MCP server** (via `py2mcp`) so the same capabilities
drive the agent, a CLI, and external hosts.

## Design & research

foley's design is grounded in five research reports (unified, cited):

- [Design](misc/docs/design.md) · [Roadmap](misc/docs/roadmap.md)
- [Research reports](misc/docs/research/) — sound sources, SFX generation, recognition/
  tagging, embeddings/indexing, and the context-retrieval agent
- [Deep-research prompt library](misc/docs/research/deep-research-prompts.md) — 12
  ready-to-run prompts covering every dimension of the project

## Install

```
pip install foley
```

(Optional per-capability extras — `foley[freesound]`, `foley[clap]`, `foley[stable-audio]`,
`foley[index]`, … — are added as each subsystem lands.)

## License

MIT
