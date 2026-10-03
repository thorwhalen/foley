# 15 — foley facade audit (read-only)

Target: `thorwhalen/foley` at `main` 65d230e (v0.0.26). Paths below are relative to that root unless they name another repo. Open issues read: #40, #42, #43, #44, #45, #48, #49. Docs read: `misc/docs/roadmap.md`, `misc/docs/design.md`, `misc/docs/research/10-facade-architecture.md` (skimmed).

Bottom line: foley's **licence model is the strongest in the fleet**. It has a per-item `LicenseRecord`, a fail-closed `keep()`, `cache_bytes_ok` kept apart from `redistribute_standalone_ok` and `ai_training_ok`, and TASL credits. The **facade mechanics are weaker** than arioso/ocracy/falaw. `param_map` is declared but nothing interprets it, and `on_unsupported_param` is never read. Drops go into notes that the public `generate()` then throws away. There is no cost model at all. Offline mode is enforced only inside one MCP tool. Paid generation bytes are lost whenever ingest does not store them. The CLI and MCP surfaces are written by hand and have already drifted from the Python defaults.

## Summary table

| # | Checklist item | Verdict | One-line fix |
|---|---|---|---|
| 1 | One root verb per job, free/keyless default | PARTIAL | Make LLM/paid upgrades opt-in (`llm="auto"` must not mean "key present"); say Stable Audio is gated and heavy |
| 2 | Backends as data + thin adapter, registry, template, `register_source` | PARTIAL | One generic `translate(param_map, kwargs)` in the base path; adapters stop hand-reading config |
| 3 | Canonical vocabulary via declarative `param_map`, ≥2-provider rule | PARTIAL | Prune single-provider canonicals to `provider_params`; implement or delete dead query affordances |
| 4 | Unsupported-param policy enforced in the single path, raise on meaning, report drops | FAIL | Enforce in a `_dispatch()` every surface calls; return notes on the public result; raise for `seed`/`negative_prompt` |
| 5 | Capability declaration of what adapters EMIT + capability query | FAIL | `capabilities` block per `SOURCE_CONFIG` (emits, deterministic, max_duration…) + `list_backends(supports=...)` |
| 6 | Escape hatches: canonical → provider_params → raw; `raw` kept | FAIL | `provider_params=` merged last; `Candidate.raw` / `GeneratedClip.raw` with the native response |
| 7 | Cost: estimate, None=unknown, estimate≠actual, cumulative budget, live-test gate | FAIL | `estimate()` per adapter (None for unknown), `Budget.max_usd` cumulative across events, autouse env scrub in tests |
| 8 | Licence & terms | PARTIAL | Fix the four widening paths (user-owned default, CC version collapse, PDM→CC0, ElevenLabs tier); ToS ledger |
| 9 | Credentials chain + informative missing-key error | PARTIAL | Add ContextVar/store rungs; put the env-var message in `GenerationError` and raise from `add_from` on auth errors |
| 10 | Optional deps: light core, extras, lazy, probe, guidance | PASS (minor gaps) | Probe each backend's extras in `check_requirements` (torch/diffusers/requests/lancedb) |
| 11 | Content-keyed caching; "no cache" still saves paid results | PARTIAL | Request-keyed cache for paid generations; persist paid bytes even when QC-quarantined or `store=False` |
| 12 | Surfaces from one registry; MCP tool list pinned | FAIL | Generate CLI + MCP from one verb table; pin tool *names* in a test that runs in CI |
| 13 | Fan-out / partial failure keeps paid results | PARTIAL | Same fix as 11; record paid-but-unstored clips in the report |
| 14 | Docs honesty | FAIL | Refresh roadmap/design; drop the EnCLAP claim; surface FakeAligner degradation on `WeaveResult` |
| 15 | Machine-readable ledger of targets beside the registry | FAIL | `foley.ledger()` computing implemented/planned per verb×backend from the registry |

## Details per item

### 1. One root verb per job, free/keyless default — PARTIAL

- Verbs exist and are distinct: `find`, `search`, `similar`, `generate`, `ingest`, `add_from`, `plan`, `weave`, `score`, plus `bootstrap`/`demo`/`credits`/`evaluate*` (`foley/__init__.py:459-729`, `foley/score.py`). The surface is broad: 18 callable verbs at the root, not a few.
- `search`/`find` default to the local library with deterministic fakes, which is free (PASS).
- `find`/`score` **auto-upgrade to paid Anthropic calls when the key exists**. `_anthropic_available()` returns True when the SDK is installed and `ANTHROPIC_API_KEY` is set (`foley/agent/decompose.py:231-251`). The same applies to judge and refiner (`foley/agent/verify.py` `_default_judge`, `refine.py`). Key presence is being treated as consent to spend, which is the exact anti-pattern behind the fleet's live-test rule.
- `generate` defaults to `stable_audio` (`foley/__init__.py:605`), which is local and free. But it needs `foley[stable-audio]` (torch + diffusers), and `stabilityai/stable-audio-open-1.0` is gated on Hugging Face (accept terms + HF token). The config comment says a token is needed "only if the repo is gated" (`foley/sources/stable_audio/config.py:29`). So the default is "free" but not out of the box, even though the docstring says "works out of the box" (`foley/__init__.py:617`).
- `add_from` has no default source. Its only source, Freesound, needs a free key.
- Fix: an explicit `llm=` seam whose default is the fake unless `FOLEY_LLM=anthropic` or `llm="anthropic"` is set. Document Stable Audio's gating in `check_requirements`.

### 2. Backends as data + thin adapter + registry — PARTIAL

- PASS: `SOURCE_CONFIG` dicts (`foley/sources/{freesound,elevenlabs,stable_audio}/config.py`). Discovery scans subpackages for `config.py` (`foley/sources/registry.py:35-65`), adapters load lazily (`registry.py:191-209`), out-of-tree plugins use `register_source` (`registry.py:68-81`), and there is a template skill (`skills/foley-dev-add-source/SKILL.md`).
- The adapters are not thin. Each one hand-codes its translation: Freesound builds filters from `param_map[...]["to_native"]` strings by hand (`foley/sources/freesound/adapter.py:169-187`), and ElevenLabs and Stable Audio hard-code body dicts (`elevenlabs/adapter.py:134-146`, `stable_audio/adapter.py:126-140`). The `param_map` entries for `prompt`, `steps`, `negative_prompt` and `duration` are decorative, because no code walks them.
- There are two disjoint registries: `CORPUS_REGISTRY` (bulk, `sources/base.py:510`) and `SOURCE_REGISTRY` (live). Fine by design, but `list_sources()` never shows the corpora.
- Fix: a base `translate(config, canonical_kwargs) -> (native, notes)` that reads `param_map`, and adapters that only do transport plus licence.

### 3. Canonical vocabulary — PARTIAL

- PASS on the mechanism: `QUERY_AFFORDANCES` / `GENERATION_AFFORDANCES` registries (`foley/base.py:136-175`).
- The ≥2-provider rule is violated. Of the 8 generation affordances, `negative_prompt`, `steps` and `seed` are Stable-Audio-only, and `loop` and `output_format` are effectively ElevenLabs-only (`stable_audio/config.py:52-62`, `elevenlabs/config.py:53-61`). Only `prompt`, `duration` and `prompt_influence` are genuinely shared.
- Dead canonicals: `QUERY_AFFORDANCES` declares `license`, `sort`, `audioset_label` and `semantic_text`, but `foley.search` accepts none of them (`foley/__init__.py:565-575`). The canonical name is `text` (`base.py:137`), while Freesound's `param_map` keys on `query` (`freesound/config.py:36`), so the vocabulary has drifted inside the SSOT itself.
- Fix: move single-provider knobs to `provider_params`. Either implement `license`/`sort`/`audioset_label` in `search` or remove them. Rename the Freesound key to `text`.

### 4. Unsupported-parameter policy in the single path — FAIL

- `on_unsupported_param: "warn"` is declared in every config but **read nowhere**. The only hits are in docstrings (`sources/base.py:181`, `sources/generate.py:176`, `freesound/adapter.py:162`).
- Python API, generate path: each adapter writes drops into `GeneratedClip.notes` by hand (`elevenlabs/adapter.py:193-202`, `stable_audio/adapter.py:164-182`). `_generate` copies them into `IngestResult.notes` (`sources/generate.py:323-324`). Then the public `foley.generate` returns `candidate_of(res)`, which is just `Candidate(sound, origin)` (`foley/__init__.py:678-679`, `sources/generate.py:98-112`). **The notes are dropped at the facade**, so callers never see them.
- Meaning-carrying args never raise. A `seed` passed to ElevenLabs (a reproducibility promise) and a `negative_prompt` (a content constraint) become notes and nothing more.
- Silent clamps with no note at all: ElevenLabs duration is clamped to 0.5–30 s (`elevenlabs/adapter.py:141-142, 204-208`) and Stable Audio to 47.55 s (`stable_audio/adapter.py:127-130`). `prompt_influence` is never range-checked.
- Python API, retrieve path: `FreesoundAdapter.search(**kw)` ignores extras silently (`freesound/adapter.py:147, 162`). Any `license` other than `"cc0"` sends no filter and produces no note (`freesound/adapter.py:175`). `add_from` forwards `**affordances` straight into that (`sources/pull.py:91-93`).
- CLI: it has no `generate`/`add_from` commands, so this does not apply. `ingest --license X` accepts any string and stamps `rights_verified=True` (`foley/cli.py:82-85`). That fails closed only because unknown ids get all-False flags.
- MCP: `foley_generate` exposes no affordances at all (`foley/agent/mcp.py:291-323`). Policy is surface-specific: the **offline check exists only in this MCP tool** (`mcp.py:302`). `foley.generate(..., backend="elevenlabs")` and `add_from("freesound")` inside `with foley.offline():` still egress, because nothing in `sources/` consults `current_runtime().offline`. The LLM decomposer default ignores offline too.
- Fix: one `_dispatch(verb, backend, **kw)` in `sources/` that applies offline/egress, translation, the unsupported policy (warn | raise | ignore, with a per-arg `meaning=True` escalation to raise), clamps-with-notes, and returns notes. `foley.generate` returns a result type that carries `notes` (or attaches them to `Candidate`).

### 5. Capability declaration + query — FAIL

- Configs declare `supported_affordances` (vendor knobs mapped), not what the adapter **emits**. Nothing records deterministic vs non-deterministic output, max duration, output format/sample rate, loopable output, stereo, or whether a watermark is present. Research report 10 §4.1 planned a `capabilities` and `cost` block (`misc/docs/research/10-facade-architecture.md:493, 535`); it never landed.
- Query API: only `list_sources(egress_allow=...)` (`registry.py:112-129`) and `capability_report()` (installed/degraded, `requirements.py`). There is no "which backends support `seed`/`loop`/by-value storage".
- Fix: a `capabilities` dict in each `SOURCE_CONFIG`, computed facts asserted by tests against fakes, and `list_backends(kind=..., supports=...)`.

### 6. Escape hatches — FAIL

- Rung 1 (canonical kwargs) exists. Rung 2 (`provider_params`) does not: unknown kwargs become notes and are dropped (`elevenlabs/adapter.py:200-202`). Rung 3 (raw native call): adapters have `_invoke` (`elevenlabs/adapter.py:210-228`, `stable_audio/adapter.py:184-203`), but it is private and undocumented.
- `raw` on the result: absent. `Candidate`, `SoundRecord` and `GeneratedClip` carry no native response (`base.py:434-452`, `sources/base.py:148-190`). Freesound's item JSON is discarded after `_candidate_from_item` (`freesound/adapter.py:242-292`). Partial credit: `LicenseRecord.generation_params` records the *resolved native* params (`elevenlabs/adapter.py:150-156`).
- Fix: `provider_params: dict` merged after translation (and recorded in `generation_params`), `Candidate.raw` / `GeneratedClip.raw`, and a public `adapter.invoke_native(...)`.

### 7. Cost — FAIL

- No estimate anywhere. `rg cost|estimate|usd` finds only QC/eval uses. ElevenLabs is paid per generation and Anthropic per token, yet no adapter has a `cost` or `estimate()` (configs lack the key that report 10 §4.1 specified).
- `Budget` counts *generations and refines per event* and **resets every event** (`foley/agent/policy.py:80-120`, `foley/agent/tools.py:380`). `find(max_events=6, backend="elevenlabs")` can therefore make 6 paid generations plus LLM decompose/judge/refine calls, with no cumulative bound and no dollar unit. This is the fleet's "$0.50 × 400" trap.
- Live tests: none exist (all fakes), so there is no opt-in gate. But tests are **not isolated from the key-presence upgrade**: there is no autouse fixture scrubbing `ANTHROPIC_API_KEY` (`tests/conftest.py`). `tests/test_mcp.py:329-339` calls `mcp.foley_find(...)` with default decomposer/judge, so on a dev machine with `anthropic` installed and a key set, the suite makes real paid calls. In this shell `anthropic` is installed and the key happens to be unset.
- Fix: `estimate(**kw) -> float | None` per adapter, with None treated as unknown and forcing approval. Record actual separately on the result. Add `Budget.max_usd` cumulative across the whole call. Add an autouse fixture deleting `ANTHROPIC_API_KEY` / `ELEVENLABS_API_KEY` / `FREESOUND_API_KEY` unless `FOLEY_LIVE_API_TESTS=1`.

### 8. Licence & terms — PARTIAL (best in class on structure, four widening paths)

- PASS: per-item `LicenseRecord` (`base.py:273-341`). Fail-closed `keep()` checks `rights_verified` first (`licensing.py:274-307`). Unknown/ND/SA map to `('unknown', False)` (`licensing.py:124-137`). `cache_bytes_ok` (ToS) is separate from `redistribute_standalone_ok` (copyright) and `ai_training_ok` (`licensing.py:7-16`, Freesound override `freesound/adapter.py:259-264`, honouring `gen_ai_preference`). Persistence: the `SoundRecord` round-trips through the meta store with its licence (`tests/test_stores.py:93-101`, `tests/test_base.py:226`). TASL credits live in `foley/provenance/credits.py`.
- Widening 1, the **default ingest licence is fail-open**. `foley.ingest(folder)` with no licence stamps `user-owned` + `rights_verified=True` (`foley/index/ingest.py:242-257, 380`), which grants commercial use, standalone redistribution and AI training to *any* folder: downloaded packs, ripped clips, anything. an#318 states the opposite rule ("With no licence the sound is unknown. Nothing is guessed").
- Widening 2, **CC version collapse**. Any `/by/` URL maps to `CC-BY-4.0`, and `by-nc` to `CC-BY-NC-4.0` (`licensing.py:85-87, 135-136`). `bulk_license` has no `license_url` parameter (`sources/base.py:261-301`), so FSD50K's many CC BY **3.0** clips are credited as "CC BY 4.0" with the 4.0 URL (`provenance/credits.py:132-137`). That is a misattribution.
- Widening 3: the `publicdomain` needle maps the Public Domain **Mark** (a label, not a grant) to `CC0-1.0`, verified (`licensing.py:81`).
- Widening 4: the **ElevenLabs tier is assumed paid** (`elevenlabs/config.py:81`, row `licensing.py:60`). Free-plan outputs are NC + attribution, and nothing checks the account tier. `an` already distinguishes `elevenlabs-free-plan` (`an/an/ir/assets.py:103-114`).
- ToS ledger per (model, backend) is absent. Terms live as comments in configs.
- Attribution: a source-supplied `attribution_text` is returned verbatim plus the modified/AI tail, and it may not name the licence (`credits.py:226-227`).
- The MCP boundary loses rights: `_license_summary` omits `license_url`, `creator_name`, `source_url`, `cache_bytes_ok`, `ai_training_ok` and `revenue_cap_usd` (`mcp.py:86-95`), so an MCP caller cannot build TASL credits from rows.
- Rights intent defaults disagree: `find()` uses `IntendedUse()` with commercial True (`tools.py:357`, `base.py:464`), while `score()` and MCP default to `commercial_ok=False` (`score.py:86,128`, `mcp.py:168`). NC sounds are therefore admitted by default on two surfaces and refused on the third.

### 9. Credentials — PARTIAL

- Chain: explicit `api_key=` then env (`freesound/adapter.py:104-114`, `elevenlabs/adapter.py:76-86`). There is no ContextVar rung (foley does have a `RuntimeConfig` ContextVar it could reuse) and no store rung.
- The missing-key message is good: it names `$FREESOUND_API_KEY` and the sign-up URL. It is **buried**, though. `_generate` catches every exception into `IngestResult.error` (`sources/generate.py:222-241`), and the public `generate` raises `GenerationError("... yielded no stored sound (error)")` (`foley/__init__.py:685-689`), whose message does not carry the cause. `add_from` never raises: a missing key returns a report with one error row (`sources/pull.py:88-98`).
- Swallowed exceptions: `_weave_result_row` sets `audio_ref=None` on any exception (`mcp.py:136-145`). Watermark and captioner failures degrade to notes, which is acceptable.
- Fix: chain `raise GenerationError(...) from original` and include the original message. Treat auth errors as raise in `add_from` (an auth error is not a transient per-hit failure).

### 10. Optional deps — PASS (minor gaps)

- Core is `dol` only (`pyproject.toml` dependencies), with one extra per backend (`freesound`, `elevenlabs`, `stable-audio`, `agent`, …). Heavy deps are imported lazily inside methods (`stable_audio/adapter.py:71-72`). Probes use `find_spec`/`which`/env without importing (`requirements.py:46-50`). `check_requirements(verbose=True)` prints install hints.
- Gap: the importable probes cover only `py2mcp` (`requirements.py:35-43`), not torch/diffusers (stable-audio), requests (freesound/elevenlabs), lancedb or transformers (clap). The HF gating of Stable Audio is not surfaced. There is no `foley[all]`, although `design.md:176` mentions it.

### 11. Caching — PARTIAL

- PASS: the byte store is keyed by the sha256 of bytes (`stores.py:76-90`). Record ids are the hash of canonical decoded PCM, not of the FLAC container (`index/ingest.py:225-240, 349-357`). Freesound uses stable `freesound:<id>` ids rather than URLs (`freesound/adapter.py:278`). No `json.dumps(default=str)` in a key path (the only hit is CLI printing, `cli.py:38`).
- FAIL on paid results. There is no request-keyed cache, so the same `(backend, prompt, params)` re-pays (ElevenLabs is non-deterministic, so output-hash dedup cannot save the call). Paid bytes are **discarded** in three cases: QC quarantine (`index/ingest.py:364-370`), an ingest/decode error after a successful paid call (`sources/generate.py:309-313`), and `store=False` previews (`sources/generate.py:158-159`).
- Fix: write every paid response to a `generations` byte store keyed by `content_key(bytes)`, with a request-digest index, before QC/ingest runs. Record the key on the report even when status is quarantined or error.

### 12. Surfaces from one registry — FAIL

- MCP: 22 hand-written wrapper functions (`mcp.py:164-538`, `TOOLS` at `mcp.py:541-564`) with their own defaults. `commercial_ok=False` diverges from `find`. `foley_generate` has a fixed `backend="stable_audio"` and no affordances. The offline check lives only here.
- CLI: hand-written argparse with 7 subcommands (`demo`, `bootstrap`, `ingest`, `eval`, `eval-fit`, `search`, `agent-install`; `cli.py:199-284`). There is no `find`/`score`/`generate`/`add_from`/`weave`, despite the README's "same capabilities drive the agent, a CLI…" (`README.md:56-57`).
- Pin: `test_build_mcp_server_registers_the_full_tool_surface` asserts `len(...) == 22` and a few names (`tests/test_mcp.py:273-285`), but it starts with `pytest.importorskip("py2mcp")`, and CI installs only the `test` extra (`pyproject.toml [tool.wads.ci.install]`). **The pin is skipped in CI.** `_resolve_tools(include=...)` silently drops unknown names (`mcp.py:567-572`).
- Fix: one verb table (name → callable + JSON projection + surface flags) generating both argparse and the py2mcp list. Add a name-list snapshot test that needs no py2mcp.

### 13. Fan-out / partial failure — PARTIAL

- PASS: `add_from` isolates each hit (`sources/pull.py:114-135`). `find(stream=True)` yields per event and falls back to the best verified retrieval when generation fails (`tools.py:480-490`). `ingest_folder` is per-file resilient.
- FAIL: a paid generation whose ingest fails or is quarantined leaves no recoverable artefact (see 11). The report records `status` but not the bytes or their key.

### 14. Docs honesty — FAIL

- `misc/docs/roadmap.md`: every checkbox in Phases 1–6 is unchecked, while the README says "Status: v1 … Epic #13 complete".
- `misc/docs/design.md:113` says "WEAVE … not yet researched" and `:121` says "Public façade API (sketch — not yet implemented)". Both are stale.
- README over-claims: "EnCLAP" in the Index stack (`README.md:50`), although pyproject says the captioning extra ships "no default yet". "Five research reports" (`README.md:92`), where there are 12. "Zero-dep at its core" (`README.md:109`), which is `dol`.
- Silent degradation: "align to the voice … forced-alignment" (`README.md:52`). Without `foley[align]`, the default is `FakeAligner`, which spaces words evenly (`weave/align.py:141-143`), and `WeaveResult` has no `notes` field to say so (`weave/__init__.py:66-86`). So a user gets mistimed cues with no warning.
- The README example `foley.generate(..., backend="stable_audio", duration=3)` needs torch, diffusers and a gated HF model. `foley.add_from(..., license="cc0")` needs a key. Neither is flagged next to the example.
- Fix: refresh roadmap/design (or replace them with the ledger from item 15), add `WeaveResult.notes` with a degraded-aligner note, and annotate the examples.

### 15. Machine-readable ledger — FAIL

- No ledger exists. Planned targets live in prose (roadmap Phase 2 "stub adapters for Epidemic/Storyblocks…", research 01/02 backends such as AudioGen and fal), and research 10 §4.1 fields (`capabilities`, `cost`, `offline_capable`) never landed.
- Fix: `foley/data/targets.json` (planned backends × verbs) plus `foley.ledger()`, which joins it with the live registry so "implemented" is computed, not typed. Expose it as an MCP `foley_capabilities` field.

## Integration with `an`'s sounds store (first customer: an an/cutan film)

What an expects (`an/an/sounds.py:109-133`, `an/an/ir/assets.py:177-218`): `add_sound(store, key, wav_bytes, source=AssetSource|Mapping)`, where the bytes are PCM WAV only. `AssetSource` fields are `provider, id, url, license, license_url, attribution, source_page_url, author, author_url, cacheable(=True default), sha256, cost_usd, extra`. The licence is classified by `license_class()` into free/attribution/private/unknown, and `an credits` walks the store. The shared type now exists: `lacing.Rights` (`t/lacing/lacing/artifact.py:120-200`; lacing#34 closed), with field names pinned literal-for-literal to `AssetSource`.

**Can a foley `Candidate`/`SoundRecord` be handed over with provenance intact today? No.** There is no exporter, and a hand-mapping loses or distorts rights:

| foley `LicenseRecord` | an `AssetSource` / `lacing.Rights` | Status |
|---|---|---|
| `source` | `provider` | maps |
| `source_id` | `id` | maps |
| `source_url` | `source_page_url` (+ `url`) | maps |
| `license_id` (`CC0-1.0`, `CC-BY-4.0`, `Stability-Community`, `ElevenLabs-SFX`, `user-owned`, …) | `license` | partial: an lowercases, so `cc-by-4.0` works, but `cc-by-nc-4.0` is not in an's `ATTRIBUTION_REQUIRING_LICENSES` (only `cc-by-nc`). `elevenlabs-sfx` ≠ an's `elevenlabs-paid-plan`. `stability-community` and `user-owned` classify as unknown |
| `license_url` | `license_url` | maps (but wrong version for FSD50K, see 8) |
| `attribution_text` | `attribution` | maps |
| `creator_name` / `creator_url` | `author` / `author_url` | maps |
| `cache_bytes_ok` | `cacheable` | maps, but **an's default is `True` and `add_sound` never reads it**, so a Freesound by-reference sound copied into an's store breaks the ToS that foley enforces |
| `content_sha256` (of foley's FLAC archive) | `sha256` (of an's WAV) | breaks: the WAV re-encode changes the digest. The chain needs `extra={"foley_id": ..., "foley_sha256": ...}` or a lacing `was_derived_from` edge |
| `transformations` | an#318's recorded cut | no shared shape |
| `commercial_ok`, `redistribute_standalone_ok`, `ai_training_ok`, `revenue_cap_usd`, `rights_verified`, `notice_text_required` | none | lost; an re-derives from the code, so foley's derived flags and overrides (Freesound `no-gen-ai`, cache override) vanish |
| `is_ai_generated`, `generator_model`, `generation_prompt`, `generation_seed`, `watermark`, `c2pa_manifest_ref`, `disclosure_recommended` | none in `AssetSource`; `lacing.Rights` is `extra="forbid"` | lost, so AI disclosure disappears from `an credits` |
| (no cost) | `cost_usd` (None = unknown) | foley has no cost to give, so it is correctly None |

There are also mechanical gaps. foley stores FLAC (by-value) or nothing at all (by-reference: `library.audio(id)` raises for Freesound, `sources/pull.py:10-14`), while an needs mono-compatible PCM WAV. There is also a semantic trap in lacing: `rights is None` means "we made this", yet a Stable Audio output is generated *and* bound by the Stability Community licence's $1M revenue cap. So "generated" does not mean "nothing owed".

**Where to build each piece:**

- **foley** owns the exporter, because only foley knows its own vocabulary and its derived flags: `to_rights(record) -> dict` with `lacing.Rights` field names (no hard lacing dependency; follow the pinned-names precedent, with an optional `foley[lacing]` that returns a real `Rights`). It also owns `export_wav(sound_id) -> bytes` for by-value sounds, raising for `cache_bytes_ok=False`. Licence codes should be emitted in a form consumers can classify (`elevenlabs-paid-plan` vs `-free-plan` once the tier is known), and the AI-generation block goes in a provenance dict beside the rights.
- **an** owns the intake: an#318's `fetcher=` seam should accept a foley fetcher (`foley:<sound_id>` → bytes + `AssetSource`). `add_sound` must refuse `cacheable=False`. an needs `PROVIDER_TERMS` rows for `stable_audio`/`stability-community` (with the revenue-cap restriction), and its attribution set needs the versioned NC codes. Classification stays in an, per lacing's rule.
- **lacing** owns the open question of how a *generated-under-terms* artifact records its obligations: `Rights` with `provider="stable_audio"`, or a provenance field. Raise this on lacing rather than encoding it in foley or an. The shared record is already there, so no new type is needed.
- Order: the foley exporter first (small, unblocks everything), then an#318 with a foley fetcher. braidio's yt-dlp ingest converging on the same fetcher seam is an#318's own scope.

## Candidate issues to file on `thorwhalen/foley`

Open issues checked for overlap: #40 golden set, #42 MCP deployment, #43 aligner alternatives, #44 C2PA signer, #45 downstream integration (braidio/nw), #48 audio-LM judge, #49 fit baseline. None covers the items below except where noted.

| # | Title | Checklist | Overlap |
|---|---|---|---|
| A | Enforce the unsupported-parameter policy in one dispatch path and return notes from `foley.generate` | 2, 3, 4 | new |
| B | Offline/egress posture is enforced only in the MCP `foley_generate` tool | 4 | new |
| C | `foley.ingest()` defaults to user-owned + verified rights (fail-open) | 8 | new |
| D | Licence normalisation widens rights: CC version collapse, PDM→CC0, ElevenLabs tier assumed paid | 8 | new |
| E | Cost model: per-adapter `estimate()` (None=unknown), actual vs estimate, cumulative `Budget.max_usd` | 7 | new |
| F | Key presence silently upgrades `find`/`score` to paid Anthropic calls; tests are not isolated | 1, 7 | new |
| G | Paid generation bytes are lost on quarantine / ingest error / `store=False`; no request-keyed cache | 11, 13 | new |
| H | Capability declaration + `list_backends(supports=...)` + a computed target ledger | 5, 15 | new |
| I | Escape hatches: `provider_params=` and `raw` native payload on `Candidate`/`GeneratedClip` | 6 | new |
| J | Generate CLI and MCP from one verb table; pin MCP tool names in a CI-run test | 12 | new |
| K | One rights-intent default across `find`/`score`/MCP, and full TASL fields in MCP rows | 8, 12 | new |
| L | Surface the root cause (e.g. missing env var) from `GenerationError` and `add_from` | 9 | new |
| M | Docs honesty: stale roadmap/design, EnCLAP claim, silent FakeAligner degradation | 14 | adjacent to #43 (#43 adds real aligners; this asks that the fake be reported) |
| N | Export a sound + its rights as `lacing.Rights`-shaped data for `an`'s sounds store | integration | adjacent to #45 (#45 is braidio/nw via `score`; this is an asset hand-off to an) |

**A. Enforce the unsupported-parameter policy in one dispatch path and return notes from `foley.generate`**
`on_unsupported_param` is declared in every `SOURCE_CONFIG` but read nowhere. Each adapter hand-writes notes, Freesound's `search(**kw)` drops extras silently, and the public `foley.generate` returns `candidate_of(res)`, which discards them.
Proposal: a `_dispatch()` in `foley/sources/` that interprets `param_map`, applies warn/raise/ignore (raise for meaning-carrying args: `seed` on a non-deterministic backend, `negative_prompt`), notes every clamp (ElevenLabs 0.5–30 s, Stable Audio 47.55 s) and returns notes.
Acceptance: `foley.generate(..., backend="elevenlabs", seed=1)` raises (or warns under `on_unsupported="warn"`), and every drop is visible on the returned object.

**B. Offline/egress posture is enforced only in the MCP `foley_generate` tool**
`with foley.offline(): foley.generate(p, backend="elevenlabs")` and `foley.add_from("freesound", ...)` still make network calls. Only `mcp.py:302` checks `data_egress`, and the default Anthropic decomposer also ignores offline.
Proposal: check `current_runtime().data_egress_allow` in `get_source()`/dispatch and in the LLM default resolution, so every surface inherits it.
Acceptance: a test that external sources and the Anthropic default raise or degrade under `offline()` through the Python API.

**C. `foley.ingest()` defaults to user-owned + verified rights (fail-open)**
`_default_user_license` stamps `user-owned`, `rights_verified=True` (commercial, redistribution, AI training) on any folder ingested without a licence (`index/ingest.py:242-257`).
Proposal: default to `license_id="unknown"`, `rights_verified=False`. Require `license="user-owned"` (or `--license user-owned`) to assert ownership, and validate CLI `--license` against `LICENSE_FLAGS`.
Breaking: existing user libraries need a one-time re-stamp, either by migration or by an explicit `foley ingest --license user-owned` rerun.

**D. Licence normalisation widens rights: CC version collapse, PDM→CC0, ElevenLabs tier assumed paid**
`license_id_from_cc_url` maps every `/by/` URL to `CC-BY-4.0`, and `bulk_license` drops `license_url`, so FSD50K CC BY 3.0 clips are credited as 4.0. The `publicdomain` needle maps the Public Domain Mark to CC0, verified. The `ElevenLabs-SFX` row assumes a paid plan with no tier check.
Proposal: keep the version (`CC-BY-3.0` rows or a `license_version` field plus `license_url` pass-through in `bulk_license`). Map PDM to its own row. Make the ElevenLabs tier an explicit config/env (`elevenlabs-paid-plan` | `elevenlabs-free-plan`, matching `an`'s codes), with unknown failing closed.
Acceptance: credits for a CC BY 3.0 clip name 3.0 and link the 3.0 deed.

**E. Cost model: per-adapter `estimate()` (None=unknown), actual vs estimate, cumulative `Budget.max_usd`**
foley has no cost data. `Budget` counts generations per event and resets per event (`agent/policy.py:80-120`, `agent/tools.py:380`), so `find(max_events=6, backend="elevenlabs")` can make 6 paid calls plus LLM calls with no bound.
Proposal: `cost` in `SOURCE_CONFIG` and `estimate(**kw) -> float | None`, where None forces approval. Record `cost_estimate_usd` and `cost_actual_usd` on the result. Add `Budget.max_usd` cumulative across the whole call (and a separate cap for LLM tokens).
Acceptance: a `find` whose estimate exceeds the budget stops before the first paid call.

**F. Key presence silently upgrades `find`/`score` to paid Anthropic calls; tests are not isolated**
`_anthropic_available()` returns True when the SDK and key exist, and decomposer, judge and refiner then switch to paid calls (`agent/decompose.py:231-251`). `tests/test_mcp.py:329` calls `foley_find` with defaults, and no autouse fixture scrubs keys, so a dev machine with a key runs paid calls in the suite.
Proposal: an explicit `llm=` seam whose default is the fake unless opted in (`FOLEY_LLM=anthropic`). Add an autouse fixture deleting provider keys unless `FOLEY_LIVE_API_TESTS=1`.
Acceptance: the suite makes zero network calls with every key set.

**G. Paid generation bytes are lost on quarantine / ingest error / `store=False`; no request-keyed cache**
A successful ElevenLabs call whose bytes fail QC (`index/ingest.py:364-370`), fail to decode (`sources/generate.py:309-313`), or are requested as a preview (`store=False`) leaves nothing behind. The same request re-pays.
Proposal: persist every paid response to a content-keyed `generations` store, with a request-digest index (canonical JSON of backend + resolved native params), before QC. Report the key on every status.
Acceptance: rerunning an identical paid request is a cache hit, and a quarantined generation's bytes remain retrievable.

**H. Capability declaration + `list_backends(supports=...)` + a computed target ledger**
Configs list mapped vendor knobs, not what each adapter emits (deterministic? loopable? max duration? sample rate? watermarked?). Research 10 §4.1's `capabilities`/`cost`/`offline_capable` never landed, and planned backends live only in prose.
Proposal: a `capabilities` block per `SOURCE_CONFIG`, tested against the fakes. Add `list_backends(kind=, supports=)`, plus `foley/data/targets.json` and `foley.ledger()`, which computes implemented vs planned from the registry, exposed via `foley_capabilities`.
Acceptance: `foley.list_backends(supports="seed")` returns `["stable_audio"]`.

**I. Escape hatches: `provider_params=` and `raw` native payload on `Candidate`/`GeneratedClip`**
Unknown kwargs are dropped to notes, `_invoke` is private, and Freesound's item JSON and ElevenLabs' response metadata are discarded.
Proposal: `provider_params: dict` merged after translation (recorded in `generation_params`), `raw: dict | None` on `Candidate`/`GeneratedClip` (excluded from the meta store if large), and a public `invoke_native()` per adapter.
Acceptance: a Freesound-only filter (e.g. `ac_brightness`) can be passed without editing foley.

**J. Generate CLI and MCP from one verb table; pin MCP tool names in a CI-run test**
The 22 MCP wrappers and the 7-command argparse CLI are hand-written and have drifted. The CLI has no `find`/`score`/`generate`/`weave`/`add_from`. The MCP pin test is `importorskip("py2mcp")` and CI installs only `[test]`, so it never runs. `_resolve_tools(include=)` silently drops unknown names.
Proposal: one verb table (callable, JSON projection, surface flags) that generates both. Add a py2mcp-free snapshot test of tool names and defaults, and make `include=` raise on unknown names.
Acceptance: adding a verb adds it to CLI and MCP with no surface code.

**K. One rights-intent default across `find`/`score`/MCP, and full TASL fields in MCP rows**
`find()` defaults to `commercial=True`, while `score()` and every MCP tool default to `commercial_ok=False`, which admits NC sounds. MCP `_license_summary` omits `license_url`, `creator_name`, `source_url`, `cache_bytes_ok`, `ai_training_ok` and `revenue_cap_usd`, so an MCP caller cannot attribute.
Proposal: one `DEFAULT_INTENDED_USE` SSOT used by every verb and tool, and MCP rows that carry the full TASL plus the derived flags.
Acceptance: the same passage yields the same licence-gated set via `find`, `score` and `foley_find`.

**L. Surface the root cause (e.g. missing env var) from `GenerationError` and `add_from`**
A missing `ELEVENLABS_API_KEY` reaches the user as "generation via 'elevenlabs' yielded no stored sound (error)", because the actionable message sits in `exc.report.results[0].error`. `add_from` with a missing `FREESOUND_API_KEY` returns a report and never raises.
Proposal: chain `from` the original and include its message. Classify auth/config errors as raise (not per-hit transient) in `add_from`.
Acceptance: the exception text names the env var and its sign-up URL.

**M. Docs honesty: stale roadmap/design, EnCLAP claim, silent FakeAligner degradation**
The roadmap has every phase unchecked although v1 shipped, and `design.md` says WEAVE is "not yet researched" and the facade "not yet implemented". The README claims EnCLAP (no captioner ships) and forced alignment (the default is an evenly-spaced `FakeAligner`, with no note on `WeaveResult`).
Proposal: refresh the docs (or replace the roadmap with the ledger from H), add `WeaveResult.notes`, record "aligner=fake" in the run manifest, and annotate the README examples that need keys or gated models. Distinct from #43, which adds real aligners.
Acceptance: `weave()` without `foley[align]` returns a note saying placements are approximate.

**N. Export a sound + its rights as `lacing.Rights`-shaped data for `an`'s sounds store**
`an` (an#318) needs bytes + `AssetSource`. Today a foley `SoundRecord` hand-mapped to `AssetSource` loses `ai_training_ok`, `revenue_cap_usd`, the AI-generation block and the cache override, and the FLAC→WAV re-encode breaks the sha256 chain. lacing#34 is closed: `lacing.Rights` exists, with field names pinned to `AssetSource`.
Proposal: `foley.export(sound_id, fmt="wav") -> (bytes, rights: dict, provenance: dict)`. Use `Rights` field names, keep foley's id and sha in provenance, refuse `cache_bytes_ok=False`, and emit consumer-classifiable licence codes. Its first customer is a foley fetcher behind an#318's `fetcher=` seam. Adjacent to #45 (braidio/nw via `score`).
Acceptance: an `an credits` run on a film with a foley Freesound CC0, a FSD50K CC BY and a Stable Audio clip lists all three correctly, including the AI disclosure and the revenue-cap restriction.

Companion items for other repos (not to file on foley): **an**: `add_sound` must honour `cacheable=False`, and the `AssetSource.cacheable` default should be None rather than True (matching `lacing.Rights`); add `PROVIDER_TERMS` for `stable_audio`/`stability-community` and the versioned `cc-by-nc-*` codes. **lacing**: decide how a generated artifact records the licence terms its generator imposes (`rights is None` currently reads as "nothing owed").
