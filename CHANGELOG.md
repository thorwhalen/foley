# Changelog

All notable changes to this project are documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/);
each section corresponds to a git version tag (which is also the release
published to PyPI). Entries are commit subjects and PR titles, verbatim.

## [0.0.24] - 2026-09-22

### Fixed

- fix: read/write the eval + bootstrap JSON fixtures as UTF-8, not locale ([#47](https://github.com/thorwhalen/foley/pull/47))

## [0.0.23] - 2026-07-25

- Docs polish: refresh the README install section (quick-start + extras table) ([#39](https://github.com/thorwhalen/foley/pull/39))

## [0.0.22] - 2026-07-25

- Verify C2PA signing + rubberband end-to-end (real deps); document the signer recipe ([#38](https://github.com/thorwhalen/foley/pull/38))

## [0.0.21] - 2026-07-25

- Make foley AI-first: score() contract, agent tools, shipped skill + kit ([#31](https://github.com/thorwhalen/foley/pull/31)) ([#37](https://github.com/thorwhalen/foley/pull/37))

## [0.0.20] - 2026-07-25

- Post-v1: agent production — authenticated HTTP MCP transport + local-LLM SELECT ([#36](https://github.com/thorwhalen/foley/pull/36))

## [0.0.19] - 2026-07-25

- Post-v1: weave production upgrades (ffmpeg master, IR reverb, time-stretch, signed C2PA) ([#35](https://github.com/thorwhalen/foley/pull/35))

## [0.0.18] - 2026-07-25

- Post-v1: scale up the golden retrieval-eval set (6 → 156 items) ([#34](https://github.com/thorwhalen/foley/pull/34))

## [0.0.17] - 2026-07-25

- Post-v1: auto-wire adapter resilience into the registry ([#33](https://github.com/thorwhalen/foley/pull/33))

## [0.0.16] - 2026-07-25

- Adversarial-review hardening: fix 17 CONFIRMED findings (post-v1) ([#32](https://github.com/thorwhalen/foley/pull/32))

## [0.0.15] - 2026-07-25

- MCP server, preview UX, onboarding & offline mode ([#12](https://github.com/thorwhalen/foley/pull/12)) ([#30](https://github.com/thorwhalen/foley/pull/30))

## [0.0.14] - 2026-07-24

- Weave ([#8](https://github.com/thorwhalen/foley/pull/8)) — weave(): resolve→align→anchor→mix→master→render ([#29](https://github.com/thorwhalen/foley/pull/29))

## [0.0.13] - 2026-07-24

- Evaluation Tier-2 — fit-judge, generation fidelity & inter-rater reliability (part of [#10](https://github.com/thorwhalen/foley/pull/10)) ([#28](https://github.com/thorwhalen/foley/pull/28))

## [0.0.12] - 2026-07-24

- Select agent — find(): decompose→search→verify→decide→plan ([#7](https://github.com/thorwhalen/foley/pull/7)) ([#27](https://github.com/thorwhalen/foley/pull/27))

## [0.0.11] - 2026-07-24

- Observability & reproducible run-artifact — the obs skeleton ([#11](https://github.com/thorwhalen/foley/pull/11)) ([#26](https://github.com/thorwhalen/foley/pull/26))

## [0.0.10] - 2026-07-24

- Disclosure, watermarking & safety for generated audio (Part of [#9](https://github.com/thorwhalen/foley/pull/9)) ([#25](https://github.com/thorwhalen/foley/pull/25))

## [0.0.9] - 2026-07-24

- Source adapters — generation (Stable Audio Open + ElevenLabs SFX) ([#6](https://github.com/thorwhalen/foley/pull/6)) ([#24](https://github.com/thorwhalen/foley/pull/24))

## [0.0.8] - 2026-07-24

- Provenance/credits — TASL attribution generator (Part of [#9](https://github.com/thorwhalen/foley/pull/9)) ([#23](https://github.com/thorwhalen/foley/pull/23))

## [0.0.7] - 2026-07-24

- Source contract + Freesound by-reference retrieve adapter ([#5](https://github.com/thorwhalen/foley/pull/5)) ([#22](https://github.com/thorwhalen/foley/pull/22))

## [0.0.6] - 2026-07-24

- Evaluation harness Tier-1 — retrieval metrics + the nDCG PR gate ([#10](https://github.com/thorwhalen/foley/pull/10)) ([#21](https://github.com/thorwhalen/foley/pull/21))

## [0.0.5] - 2026-07-24

- Bootstrap corpora & starter library — the 3-ring source seed ([#4](https://github.com/thorwhalen/foley/pull/4)) ([#20](https://github.com/thorwhalen/foley/pull/20))

## [0.0.4] - 2026-07-24

- Sanitize sound_id at the meta-store boundary + Foundation fast-follows ([#16](https://github.com/thorwhalen/foley/pull/16)) ([#19](https://github.com/thorwhalen/foley/pull/19))

## [0.0.3] - 2026-07-23

- Ingestion pipeline — probe → QC → tag → embed → SoundRecord ([#3](https://github.com/thorwhalen/foley/pull/3)) ([#18](https://github.com/thorwhalen/foley/pull/18))

## [0.0.2] - 2026-07-23

- Index — embeddings, hybrid search, library façade & taxonomy ([#2](https://github.com/thorwhalen/foley/pull/2)) ([#17](https://github.com/thorwhalen/foley/pull/17))
- Foundation: data models, dol stores, audio primitives, Tier-0 QC ([#15](https://github.com/thorwhalen/foley/pull/15))
- Add dev-skills toolkit (agent guide + foley-dev-implement + foley-dev-add-source) ([#14](https://github.com/thorwhalen/foley/pull/14))
- Add research batch 2 (reports 06-12) and authoritative architecture synthesis
- Add research reports, prompt library, and synthesized design/roadmap
- Initial project setup via wads
