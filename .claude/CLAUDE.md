# foley — agent guide

**foley** is a retrieval-first façade for sound effects: find (or generate) the right
sound for a moment of narration and weave it in. Four stages —
**SOURCE → INDEX → SELECT → WEAVE** — plus cross-cutting layers (licensing/provenance,
evaluation/QC, observability, `dol` storage). It is the SFX sibling of
[`arioso`](https://github.com/thorwhalen/arioso) (a unified façade over music-gen
backends) and shares its discipline.

**Status:** design-stage. The plan is **[Epic #13](https://github.com/thorwhalen/foley/issues/13)**
with 12 sub-issues (#1–#12). Nothing is implemented yet.

## Read before doing foley work

- **Authoritative architecture** → [`misc/docs/research/10-facade-architecture.md`](../misc/docs/research/10-facade-architecture.md)
  (component diagram, data models, façade API, protocols, module tree, build order).
- **Design map** → [`misc/docs/design.md`](../misc/docs/design.md) ·
  **Roadmap** → [`misc/docs/roadmap.md`](../misc/docs/roadmap.md)
- **Research** → 12 cited reports in [`misc/docs/research/`](../misc/docs/research/)
  (index + the 12-prompt library there).

## Dev skills (the agent toolkit for building foley)

| Skill | Use when |
|-------|----------|
| **`foley-dev-implement`** | implementing any epic subtask — the build loop, module layout, canonical data models, invariants, façade discipline, git flow |
| **`foley-dev-add-source`** | adding a sound source — a retrieve adapter (Freesound/BBC/…) or a generate adapter (Stable Audio Open/ElevenLabs/…) via the `SOURCE_CONFIG` pattern |

These are **dev** skills (for the agent building foley), not skills shipped to end
users. Real files live in `skills/foley-dev-*/`, symlinked into `.claude/skills/`.

## Behavioral rules (the non-negotiables)

- **Git flow:** work on a **feature branch → PR into `main`**. No direct-to-main commits.
- **Follow the architecture; don't fork it.** Build against the module layout,
  protocols, and canonical data models in report 10 / `base.py`. Don't invent parallel
  structures. See `foley-dev-implement`.
- **Licensing is load-bearing** (foley's output gets published): `LicenseRecord` is the
  SSOT for *both* the candidate license-filter *and* each sound's storage mode;
  `redistribute_standalone_ok` (copyright) ≠ `cache_bytes_ok` (TOS); the license gate is
  **fail-closed**. See `foley-dev-add-source` and report 07.
- **Façade discipline:** mirror `arioso` (config-driven plugin adapters, unified
  vocabulary → native params, zero-dep core + lazy optional-extras, `dol` storage) and
  `accompy` (progressive disclosure, protocol-based extensibility, `check_requirements`
  onboarding).
- **Every module needs a top-level docstring** (auto-extracted for docs). Prefer
  functional style; keyword-only args past the 3rd position.

## Where things go (placement test)

Behavioral rules → this file / the skills. Content & context → the named files in
`misc/docs/` referenced above. *If deleting a sentence wouldn't change behavior, it
belongs in a file, not here.*
