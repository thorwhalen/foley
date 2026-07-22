# Bootstrap Corpora & Benchmarks for a Starter Library — A Guide for foley

This report specifies **what data to seed foley with so it is useful on day one and
measurable from day one**. It goes beyond the survey in report 01 to make corpus choice
*actionable*: exact sizes, per-clip license breakdowns, download mechanics, and the
distinction between corpora foley can **ship/redistribute**, corpora it can **fetch but
not redistribute**, and corpora that are **benchmarks** (audio + reference captions) for
regression-testing retrieval. The central findings: **(1)** a legally-clean, on-disk
**starter library** is best assembled from the **CC0/CC-BY subset of FSD50K** (labeled,
AudioSet-ontology, ~85 % commercial-safe) plus **Clotho** (which — unlike AudioCaps —
*ships its audio* and doubles as a retrieval benchmark); **(2)** the natural **retrieval
benchmarks** are **Clotho** and **AudioCaps** (the DCASE Task 6b standard), with
**SoundDescs**, **WavCaps**, and **Auto-ACD** as scale-up/complementary sets; **(3)** two
2026 datasets — **EnvSound-UCS** (58 k clips relabeled onto UCS) and **FoleySet** (10 k
CC-BY Foley clips) — are purpose-built for exactly foley's taxonomy and task; and **(4)**
a **golden (narrative-context → expected-sound) eval set** can be bootstrapped cheaply by
**LLM-assisted seeding + a short human accept/reject pass**, anchored to UCS CatIDs and
drawing its "answer" clips from the labeled seed corpora.

> **Access date:** 2026-07-22. Dataset sizes, mirrors, and especially *license terms*
> change; verify each dataset's landing page and license file before shipping. Figures are
> from primary sources (Zenodo records, dataset papers, license pages, model cards) where
> possible; order-of-magnitude engineering estimates (embedding/index build time) are
> labeled as such. This report builds on and deepens report 01 (§"Free bulk corpora").

---

## 1. Free / redistributable SFX corpora (the starter-library candidates)

Two axes matter for foley and are conflated in most listicles: **(a)** may the raw files be
**redistributed** (shipped inside foley or re-hosted), vs. only *used* inside a finished
work?; and **(b)** may the audio feed **AI/ML** (embedding, training, indexing that
persists derived vectors)? A corpus can be commercially usable yet forbid redistribution
*and* forbid AI training (Sonniss), or be freely redistributable but non-commercial per
some clips (FSD50K's CC-BY-NC slice). foley's `LicenseRecord` (report 01 §2) already models
this with `commercial_ok` / `redistribute_ok` / `ai_training_ok` — these corpora are the
first data those flags must gate.

| Corpus | Size | Contents | License (key constraints) | `redistribute` / `ai_training` | How to obtain |
|---|---|---|---|---|---|
| **FSD50K** | 51,197 clips / 108.3 h / ~30 GB WAV | Freesound clips, 200 AudioSet-ontology classes, multi-label | Overall **CC-BY 4.0**; per-clip CC0/BY/BY-NC/Sampling+ (85 % CC0+BY) [6][7] | ✅ (per-clip) / ✅ (research; filter NC) | Zenodo 4060432 (6 zips) / HF mirror [6] |
| **Clotho v2** | 4,981 clips / 15–30 s / ~24,905 captions | Freesound clips **+ 5 captions each**; **ships audio** | Audio: redistributable Freesound subset; captions **CC-BY 4.0** [8][9] | ✅ / ✅ | Zenodo (dev/val/eval zips) [9] |
| **Sonniss GameAudioGDC** | ~160–200 GB cumulative (2015–2024); e.g. 2023 ≈ 40 GB, 2024 ≈ 27.5 GB | Pro game-audio SFX, hi-res WAV, per-vendor folders | Royalty-free commercial; **no standalone resale**; **AI training expressly prohibited** [3][4][5] | ❌ / ❌ | sonniss.com/gameaudiogdc (HTTP + torrent + mirror) [3] |
| **BBC Sound Effects** | 33,000+ (16,000 downloadable WAV) | Broadcast archive SFX | **RemArc = non-commercial** (personal/education/research) [23] | ❌ / ⚠️ | Web only (no bulk API) [23] |
| **FoleySet** (2026) | 10,000 clips | Foley/action sounds, **2-level Foley taxonomy** | **CC-BY 4.0** [19] | ✅ / ✅ | arXiv 2606.25980 (CC resource) [19] |
| **EnvSound-UCS** (2026) | 58,057 clips | AudioSet+FSD50K+ESC-50 **relabeled onto UCS** | Inherits source per-clip licenses (filter) [18] | ⚠️ per-source / ✅ | arXiv 2606.05571 + release [18] |
| **ESC-50** | 2,000 clips / 5 s / 50 classes | Environmental sounds (Freesound-sourced) | **CC-BY-NC** (ESC-10 subset CC-BY) [20] | ✅ (NC) / ⚠️ (NC) | github.com/karolpiczak/ESC-50 [20] |
| **UrbanSound8K** | 8,732 clips / ≤4 s / 10 classes | Urban field recordings | CC-BY-NC 3.0 (research) [21] | ✅ (NC) / ⚠️ | urbansounddataset.weebly.com [21] |
| **Freesound CC0 subset** | (subset of 600 k+; not officially counted) | Live API, per-sound CC0 | **CC0 1.0** (public domain) [1][2] | ✅ / ✅ | Freesound APIv2, `filter=license:"Creative Commons 0"` [1] |

### 1.1 FSD50K — the labeled, commercial-safe backbone

FSD50K (MTG/UPF; Fonseca et al.) is the single best *labeled and redistributable* seed:
**51,197 Freesound clips, 108.3 hours**, multi-labeled with **200 classes from the AudioSet
ontology** (144 leaf + 56 intermediate), 16-bit/44.1 kHz **mono WAV**. [6][7] Its
decisive property for foley is a **known per-clip license split** that ships in the
metadata, so a commercial-safe partition is a one-line filter:

- **Whole dataset:** CC-BY 4.0; per-clip mix. Across all 51,197 clips: **CC0 19,873
  (38.8 %), CC-BY 23,506 (45.9 %), CC-BY-NC 6,041 (11.8 %), CC Sampling+ 1,777 (3.5 %)** —
  so **CC0+CC-BY ≈ 84.7 %** is commercial-safe after dropping the NC/Sampling+ slice. [6]
- **Splits:** dev 40,966 / eval 10,231, with an official dev→(train/val) split. Ground
  truth `dev.csv`/`eval.csv` carry AudioSet MIDs; `vocabulary.csv` lists the 200 classes.
- **Obtain:** Zenodo record **4060432** (DOI `10.5281/zenodo.4060432`), delivered as
  multi-part zips (`FSD50K.dev_audio.z01…`, `FSD50K.eval_audio.zip`, `FSD50K.ground_truth`,
  `FSD50K.metadata`); no login. HF mirrors (`Fhrozen/FSD50k`, `philgzl/fsd50k`) exist. [6]

### 1.2 Clotho — a benchmark that is *also* a seed corpus

Clotho (Drossos et al., ICASSP 2020; v2 for DCASE 2021 Task 6) is unusual and valuable:
because its audio was drawn from the **redistributable** Freesound subset, **the actual
WAVs are hosted on Zenodo** (not just IDs), so Clotho is simultaneously (a) a text↔audio
**retrieval benchmark** with 5 human captions/clip and (b) a small, clean, license-safe
**seed library**. **4,981 clips of 15–30 s, 24,905 captions of 8–20 words**; splits: **dev
3,839 (19,195 caps) / val 1,045 (5,225) / eval 1,045 (5,225)**. [8][9] Captions are
CC-BY 4.0. This makes Clotho the ideal "batteries-included" first ingest: real audio +
gold captions foley can use to smoke-test the whole probe→caption→embed→search pipeline.

### 1.3 Sonniss GameAudioGDC — verified: AI-training prohibited

Report 01 flagged this; it is **confirmed**. The #GameAudioGDC bundle license is
royalty-free, commercial, no-attribution, unlimited projects for life — **but** the
licensee is *"expressly prohibited from using any sound effects … for the purpose of
training artificial intelligence technologies … including technologies capable of
generating sound effects in a similar style,"* and may not *"use, reproduce, or leverage
the licensed sound effects for developing, training, or enhancing artificial intelligence
technologies."* [4][5] Standalone resale of the raw files is also barred. Cumulative archive
is **~160–200 GB** across the 2015–2024 drops (e.g. GDC 2023 ≈ 40 GB, GDC 2024 ≈ 27.5 GB,
GDC 2015 ≈ 10.3 GB), each with HTTP + official torrent + a mirror. [3]

> **Consequence for foley.** Sonniss can back a **human-facing playback/retrieval** library
> **only if** foley's embedding/index step is legally *not* "AI training." This is a genuine
> gray area: computing CLAP vectors and persisting them is derivative ML processing. The
> safe default is to **exclude Sonniss (and BBC) from the shipped/indexed corpus** and treat
> both as opt-in, locally-added, `ai_training_ok=False` sources the user points foley at —
> never bundle them, never feed them to a persisted vector index without the user's explicit
> acknowledgement.

### 1.4 The rest

- **BBC Sound Effects** — 33,000+ (16,000 WAV) under **RemArc = non-commercial**; web-only,
  no bulk API. [23] Great demo breadth; hard-flag `commercial_ok=False`.
- **FoleySet** (2026, CC-BY 4.0, 10 k clips, 2-level Foley taxonomy) and **EnvSound-UCS**
  (2026, 58,057 clips relabeled onto UCS) — see §3; both are new and *directly* on-mission.
- **ESC-50 / UrbanSound8K** — small, tidy, class-labeled CC-BY-NC sets; excellent for
  **classifier/zero-shot-tagger sanity checks** and as a compact 10/50-class fixture, but
  non-commercial. [20][21]
- **Freesound CC0 subset** — the *live* redistributable/commercial/AI-safe tap. Freesound
  does not publish a CC0 count, but with 600 k+ total sounds and CC0 one of three offered
  licenses, the CC0 pool is on the order of **10⁵**. Fetch on demand via
  `filter=license:"Creative Commons 0"`. [1][2]

---

## 2. Benchmark datasets for evaluating retrieval

These provide **(audio, caption)** pairs and **standard splits** so foley can measure
text→audio retrieval with the field's usual metrics (**R@1/5/10, mAP@10, mAP@16**) as used
in **DCASE Task 6b — Language-Based Audio Retrieval**. [10] A crucial practical split runs
through this table: **Clotho / SoundDescs / WavCaps / FSD50K ship audio** (redistributable
or fetchable) → usable as *both* benchmark and corpus; **AudioCaps / Auto-ACD ship only
YouTube IDs + captions** → benchmark-only, and subject to link-rot.

| Dataset | Pairs | Audio len | Captions/clip | Standard splits | Audio shipped? | License | Source |
|---|---|---|---|---|---|---|---|
| **Clotho v2** | 4,981 clips / 24,905 caps | 15–30 s | 5 | dev 3,839 / val 1,045 / eval 1,045 | **Yes** (Zenodo) | caps CC-BY 4.0 | Freesound [8][9] |
| **AudioCaps** | ~50 k clips | 10 s | train 1, val/test 5 | train 49,838 / val 495 / test 975 (≈49,274 / 494 / 957 after rot) | **No** (YT IDs) | caps by authors; audio = YouTube | AudioSet [12][13] |
| **SoundDescs** | 32,979 clips | variable | 1 (rich descr.) | author train/val/test | via BBC | non-commercial (BBC-sourced) | BBC SFX [17] |
| **WavCaps** | ~400 k clips | variable | 1 (ChatGPT-cleaned) | pretraining set (+ eval on Clotho/AudioCaps) | metadata + fetch scripts | **academic-only**; per-source | FreeSound/BBC/SoundBible/AudioSet [14][15] |
| **Auto-ACD** | ~1.9 M pairs | 10 s | 1 (long, ~18 wd) | train/test | **No** (AudioSet/VGGSound IDs) | research | AudioSet+VGGSound [16] |
| **MACS** | 3,930 clips / ~17 k caps | 10 s | ~2–5 | — | Yes (TAU Urban) | CC-BY 4.0 | TAU Urban Acoustic [derived] |

### 2.1 Clotho & AudioCaps — the standard pair

**Clotho** (§1.2) and **AudioCaps** are the two datasets every text↔audio retrieval /
captioning paper reports on, and DCASE Task 6b's evaluation is built on Clotho. [10]
**AudioCaps** (Kim et al., NAACL 2019) is the largest human-captioned SFX set — **~50 k
10-second clips sampled from AudioSet**, **1 caption/clip in train** and **5 in val/test**
(train 49,838 / val 495 / test 975; ~49,274 / 494 / 957 survive YouTube link-rot). [12][13]
Because AudioCaps ships **only YouTube IDs + timestamps**, foley cannot redistribute its
audio and must fetch (with attrition) — so treat it as a **benchmark, not a corpus**. HF
mirrors (e.g. `d0rj/audiocaps`) host captions and, in some cases, cached audio. [13]

### 2.2 Complementary / scale-up sets

- **SoundDescs** (Koepke et al., "Audio Retrieval with Natural Language Queries") —
  **32,979** BBC-sourced (audio, description) pairs, explicitly built to be *complementary*
  to AudioCaps/Clotho (studio SFX, Blitz recordings, Natural History Unit). Good for
  stress-testing on production-style SFX, but BBC-sourced → **non-commercial**. [17]
- **WavCaps** (Mei et al., 2023) — **~400 k** weakly-labeled clips from FreeSound + BBC SFX
  + SoundBible + AudioSet-SL, with **ChatGPT-cleaned captions**; the standard large
  *pretraining* set for CLAP-style models. **Academic use only**, per-source licensing. [14][15]
- **Auto-ACD** (Sun et al., 2023) — **~1.9 M** audio-text pairs with long, scene-rich
  captions (~18 words, 23 k vocab) auto-generated via a multimodal pipeline over
  AudioSet/VGGSound; audio not shipped. Best as a *training* signal, not a clean eval. [16]

> **How foley uses these.** Ship **none** of them by default. Use **Clotho-eval** as the
> built-in, redistributable retrieval regression fixture (audio + 5 caps/clip on disk); use
> **AudioCaps-test** as an optional fetch-when-present benchmark; keep WavCaps/Auto-ACD as
> pointers for anyone training a better embedder. Report **R@1/5/10 + mAP@10** on
> Clotho-eval as the pipeline's headline retrieval numbers.

---

## 3. Taxonomized sets aligned to AudioSet / UCS

foley's index carries two taxonomy axes (design.md §2): **AudioSet ontology** (632 classes,
the auto ML-label layer) and **UCS** (82 cat / ~753 subcat, the human browse tree + the
normalization target). The seed corpora line up neatly on these axes, and two 2026 datasets
do the cross-walk *for* us:

| Set | Taxonomy | Alignment value for foley |
|---|---|---|
| **FSD50K** | 200 classes ⊂ **AudioSet ontology** (with MIDs) | Direct AudioSet labels → free supervised-tag ground truth; the AudioSet↔UCS bridge |
| **AudioSet ontology** (`ontology.json`) | 632 classes, hierarchical, MIDs | The class graph foley's PANNs/CLAP-zero-shot taggers emit into [ref. report 03] |
| **EnvSound-UCS** (2026) | **UCS** (relabeled) | 58,057 clips from AudioSet+FSD50K+ESC-50 mapped to UCS; **ready-made AudioSet→UCS + FSD50K→UCS mapping tables** [18] |
| **FoleySet** (2026) | **2-level Foley taxonomy**, CC-BY | Purpose-built for **Foley classification / retrieval / generation** — foley's exact task family [19] |
| **ESC-50 / UrbanSound8K** | 50 / 10 flat classes | Compact labeled fixtures for tagger sanity checks |

### 3.1 EnvSound-UCS — the AudioSet/FSD50K → UCS Rosetta stone (arXiv 2606.05571)

"Sound Effects Dataset Unification With the Universal Category System" (2026) is the most
directly useful research result for foley's taxonomy layer. It publishes **EnvSound-UCS**, a
UCS-compliant unified dataset of **58,057 clips** from **AudioSet + FSD50K + ESC-50**, built
with a **rule-based multi-stage relabeling pipeline** (mapping table → subcategory match →
category match → synonym match) plus conflict resolution and a stratified split. It maps
**100 % of FSD50K and ESC-50** and **98.49 % of AudioSet** files onto UCS. [18] For foley
this is a gift: it supplies **exactly the AudioSet→UCS and FSD50K→UCS mapping tables** that
report 01 said foley would have to build, and validates the "map heterogeneous tags onto UCS
CatIDs via synonym lists" design. **Adopt its mapping tables directly** for the
`tags→CatID` resolver.

### 3.2 FoleySet — a CC-BY Foley-native dataset (arXiv 2606.25980)

FoleySet (2026) is **10,000 CC-BY-4.0 clips** with a **two-level Foley taxonomy**,
explicitly released to support **data-driven Foley classification, retrieval, and
generation** — i.e., foley's problem, named. [19] It is small enough to ship and redistribute
(CC-BY → attribution only), Foley-focused (footsteps, cloth, prop handling — the diegetic
action sounds narration most needs), and usable as both a labeled seed and a
retrieval/classification fixture. **Strong candidate to bundle.**

---

## 4. A "golden" evaluation set — (narrative-context → expected-sound) pairs

Clotho/AudioCaps measure the **wrong-but-cheap** thing for foley: *caption→clip* retrieval,
where the query already *is* a clean sound description. foley's real task is
**narrative-context → sound(s)**: a *story paragraph* must be decomposed into salient,
correctly-diegetic sound events, each of which then drives retrieval (design.md §3, report
05). No public benchmark tests this. foley needs its own small **golden set** — a regression
fixture of **(context → expected sounds)** items — and it can be built cheaply.

### 4.1 What the golden set is

A versioned fixture (JSON, in-repo under `tests/golden/`) of **~100–200 items**, each:

```python
GoldenItem = {
    "id": "gld_0042",
    "context": "She pushed open the heavy oak door; rain hammered the windows outside.",
    "expected_events": [
        {"query": "heavy wooden door opening creak", "ucs_catid": "DOORWood",
         "audioset": ["/m/02y_763"],  # "Door"
         "layer": "one_shot", "diegetic": True, "salience": "high",
         "onset_hint": "on 'pushed open'"},
        {"query": "heavy rain on window", "ucs_catid": "RAINGeneral",
         "audioset": ["/m/06mb1"],    # "Rain"
         "layer": "bed", "diegetic": True, "salience": "medium"},
    ],
    "negatives": ["thunder crack", "footsteps on gravel"],  # plausible-but-wrong
    "answer_clip_ids": {"DOORWood": ["fsd50k:12345", "clotho:door_02"], ...},
    "grade": {"fsd50k:12345": 2, "clotho:door_02": 1},  # 2=ideal,1=acceptable,0=wrong
    "labeler": "llm+human", "schema_version": 1,
}
```

This fixture exercises **the whole chain**, not just retrieval: `decompose_context`
(did we recover the right *events*, at the right *salience*, with the right *diegetic* flag,
without overcrowding?) **and** `search_sounds` (does an acceptable clip rank in the top-k for
each event's query?).

### 4.2 Cheap construction — LLM-assisted seeding + short human check

The IR-evaluation literature now supports **LLM-generated relevance judgments** as a
low-cost substitute for crowd labels: GPT-4-class models predict searcher preferences about
as well as crowd workers [24], LLM relevance judgments correlate highly with human system
rankings (Kendall's τ ≈ 0.72–0.91) [25][26], and *fully synthetic* test collections have
been built for ~$126 while preserving relative system rankings [26]. The known failure modes
— **absolute-score inflation** and **self-preference bias** — are exactly why foley keeps a
**human accept/reject gate** and uses the set only for **relative regression** (did an
index/model change move the numbers?), not for absolute quality claims. A 5-step recipe:

1. **Seed contexts.** Hand-write or LLM-draft ~150 short narrative paragraphs spanning
   genres (indoor/outdoor, action/ambient, calm/violent) and the common UCS top categories
   (DOOR, FOOT, RAIN, GUN, VEH, CROWD, WATR, FIRE, …). Cheap; a few LLM calls.
2. **LLM-decompose** each context into `expected_events` (the very same `decompose_context`
   prompt foley ships), emitting `query · ucs_catid · audioset · layer · diegetic ·
   salience`. This makes the golden set *and* dog-foods the decomposer.
3. **Auto-attach candidate answer clips** by running foley's own hybrid search for each
   event query against the **labeled seed corpora that ship audio** (FSD50K, Clotho,
   FoleySet), keeping top-5. Because those clips carry AudioSet/UCS labels, agreement between
   an event's `ucs_catid`/`audioset` and a clip's labels is a free pseudo-relevance signal.
4. **Human accept/reject pass** (the gate). A person spends ~15–20 min per 25 items:
   listen to the top candidate(s), set `grade` ∈ {0,1,2}, fix any wrong/missed events,
   confirm `diegetic`/`salience`. This is where cost is spent — and it is small.
5. **Freeze + version.** Commit as a fixture with `schema_version`; re-label only on schema
   change. Track inter-item provenance (`labeler`) so LLM-only vs human-checked items are
   separable.

### 4.3 Metrics the golden set drives (regression harness, cheapest-first)

- **Decomposition:** event **precision/recall** vs. `expected_events`; salience-ranking
  correlation; diegetic-flag accuracy; over/under-crowding (events-per-100-words vs. budget).
- **Retrieval (per event):** **R@1/R@5/R@10** and **mAP@10** using graded `answer_clip_ids`;
  **nDCG@10** since grades are graded (2/1/0).
- **Cheap proxy:** mean **CLAP text↔audio score** of the top-1 as a fast smoke signal
  between full evals (its limits — no temporal reasoning — are why it's a *proxy*, per
  report 05's verification ladder).
- **End-to-end gate:** % of items where every high-salience diegetic event gets an
  `accepted`-grade clip in top-k **or** correctly routes to `generate`.

This mirrors the author's economist/trophy testing philosophy (report 08 / testing-strategy):
run decomposition + retrieval metrics on every commit (cheap, API-level), reserve
audio-LM/LLM fit-judging for release gates.

---

## 5. Practical ingestion — sizes, storage footprint, build time

Concrete numbers for planning the first ingests. Audio bytes dominate storage; the CLAP
**embedding pass is the time bottleneck**; the vector **index build is negligible** at
starter-library scale.

### 5.1 Storage footprint (per record and per corpus)

- **CLAP vector:** 512-d **float32 = 2,048 bytes/clip** (≈ 2 KB). Half that (1 KB) as
  float16; ~256 B under PQ compression.
- **Metadata `SoundRecord`:** ~1–3 KB JSON/row (tags, caption, licence, UCS/AudioSet,
  descriptors).
- **Audio (canonical WAV, mono 16-bit/44.1 kHz):** **≈ 317 MB per hour** (÷~2 as FLAC).

| Corpus | Clips | Vectors (fp32) | Metadata | Audio (WAV / FLAC) | Total on disk |
|---|---|---|---|---|---|
| **Clotho v2** (all) | 4,981 | ~10 MB | ~10 MB | ~10 GB / ~5 GB (15–30 s, stereo) | **~5–10 GB** |
| **FoleySet** | 10,000 | ~20 MB | ~25 MB | ~2–5 GB | **~2–5 GB** |
| **FSD50K** | 51,197 | ~105 MB | ~120 MB | ~30 GB / ~15 GB | **~15–30 GB** |
| **FSD50K (CC0+BY only)** | ~43,400 | ~89 MB | ~100 MB | ~26 GB / ~13 GB | **~13–26 GB** |
| **Sonniss (one year)** | 10⁴–10⁵ | 10s of MB | 10s of MB | ~30 GB | **~30 GB** (do not index by default) |
| **1 M-clip library** (scale target) | 1,000,000 | **~2 GB** | ~2 GB | dominant (TBs) | vectors+meta **~4 GB** |

Takeaway: **the vector index is tiny** (2 GB even at 1 M clips) — it rides comfortably in a
single LanceDB table on a laptop or `s3://`. **Audio blobs are the storage cost**, which is
exactly why foley splits heavy bytes (`sounds` store, `dol` Files→S3) from the light
`meta`/`vindex` (design.md §2). Store-by-reference for API sources (Freesound previews) keeps
the shipped footprint near-zero until a clip is actually used.

### 5.2 Embedding + index build time (order-of-magnitude)

LAION-CLAP's HTSAT variants are **~150–200 M params** (`laion/larger_clap_general` /
`clap-htsat-*`) — small by modern standards and near-real-time per clip. [27][28] Grounded
estimates (validate on target hardware; labeled as engineering estimates, not measured
here):

| Stage | ~throughput | 5 k (Clotho) | 50 k (FSD50K) | 1 M |
|---|---|---|---|---|
| **CLAP embed — modern GPU** (batched) | ~100–300 clips/s | seconds | ~3–8 min | ~1–3 h |
| **CLAP embed — CPU** (single box) | ~2–10 clips/s | ~10–40 min | ~2–7 h | days (batch overnight) |
| **Probe/decode + resample** | I/O-bound | minutes | ~tens of min | hours |
| **LanceDB IVF-PQ build** | ~1 M vec / few min [29][30] | <1 s (brute-force ok) | ~seconds | ~5–10 min |
| **BM25/FTS index** (tags+caption) | fast | <1 s | seconds | minutes |

Notes: at **≤ few-×10⁴ clips, skip ANN entirely** — LanceDB brute-force/flat search over a
few-MB vector column is sub-100 ms, so the starter library needs *no* index tuning; add
**IVF-PQ only past ~10⁵–10⁶** (partitions ≈ √N, sub-vectors ≈ dim/16), where a ~1 M×dim
build is minutes and query stays single-digit-to-tens of ms. [29][30] The end-to-end
first-ingest of the recommended starter library (Clotho + FoleySet + FSD50K-CC0/BY, ~58 k
clips) is therefore **~1 hour on a GPU / an afternoon on CPU**, dominated by CLAP embedding
and audio decode, with the index itself effectively free.

---

## Recommendations for foley

### A. The starter library (what to bundle vs. fetch, and why)

Assemble the day-one library in three concentric rings, gated by the `LicenseRecord` flags:

**Ring 0 — ship inside foley (tiny, redistributable, self-testing):**
- **Clotho-eval** (1,045 clips + 5,225 captions, audio on disk, CC-BY captions / redistributable
  Freesound audio). Doubles as the built-in **retrieval regression fixture**. ~1–2 GB. [8][9]
- **FoleySet** (10 k, **CC-BY 4.0**, Foley-native 2-level taxonomy) — the on-mission core;
  attribution-only, redistributable, AI-ok. ~2–5 GB. [19]

  *Rationale:* both are commercial-safe (CC-BY = credit only), redistributable, and directly
  exercise the pipeline; shipping them means `pip install foley && foley.demo()` works with
  real, licence-clean audio and a real benchmark, offline.

**Ring 1 — fetch on first run (`foley bootstrap`), commercial-safe, indexed:**
- **FSD50K filtered to CC0+CC-BY** (~43 k clips, ~85 % of the set, AudioSet-ontology
  labels). One-line license filter on the shipped per-clip metadata → the labeled backbone
  for tagging ground truth and retrieval eval. [6][7]
- **Freesound CC0 live tap** (`filter=license:"Creative Commons 0"`) for on-demand growth —
  CC0 = the only fetch that is simultaneously commercial-, redistribute-, and AI-safe. [1]
- **EnvSound-UCS mapping tables** — don't necessarily ingest the audio, but **adopt its
  AudioSet→UCS / FSD50K→UCS mapping** as foley's `tags→CatID` resolver. [18]

**Ring 2 — opt-in, user-pointed, `ai_training_ok=False`, never bundled/auto-indexed:**
- **Sonniss GameAudioGDC** (breadth/quality) and **BBC Sound Effects** (RemArc,
  non-commercial). foley must (a) require an explicit user acknowledgement before adding
  these, (b) hard-set `redistribute_ok=False` and `commercial_ok=False`(BBC), and
  (c) treat CLAP-embedding-and-persisting as a training-adjacent act it will not perform on
  `ai_training_ok=False` sources without consent. [3][4][5][23]

**License rationale in one line:** *CC0/CC-BY first (commercial + redistributable + AI-safe),
CC-BY-NC only for local non-commercial use, and Sonniss/BBC quarantined behind an explicit
opt-in because their terms forbid the exact ML processing foley's index performs.*

### B. The golden eval set (construction plan)

1. **Scope:** ~150 (narrative-context → expected-sound) items spanning genres and the top
   ~20 UCS categories; store as a versioned `tests/golden/*.json` fixture.
2. **Seed cheaply:** LLM-draft the contexts; run foley's own `decompose_context` to emit
   `expected_events` (query · UCS CatID · AudioSet · layer · diegetic · salience) — this
   dog-foods the decomposer while building the fixture. [24][25]
3. **Auto-attach answers** by hybrid-searching the Ring-0/Ring-1 corpora (which ship audio +
   AudioSet/UCS labels), keeping top-5 candidates; use label agreement as free
   pseudo-relevance. [26]
4. **Human gate** (~2–3 hours total for 150 items): listen, grade candidates 2/1/0, correct
   missed/spurious events. Keep LLM-only vs human-checked separable.
5. **Regress on every commit:** decomposition precision/recall + diegetic/salience accuracy,
   then per-event R@1/5/10 · mAP@10 · nDCG@10 on Clotho-eval and the golden set; CLAP-score
   as the fast proxy; audio-LM/LLM fit-judging only at release gates. Use the set for
   **relative** regression (guarding against LLM absolute-score inflation and
   self-preference bias). [25][26]

**Net:** foley ships with real, license-clean audio and a real benchmark on day one
(Ring 0), grows into a commercial-safe labeled library on first run (Ring 1), quarantines
the AI-training-forbidden material (Ring 2), reuses a 2026 paper's UCS mapping instead of
building one, and measures itself with both the field-standard Clotho metrics and a bespoke,
cheaply-built narrative-context golden set.

---

## REFERENCES

1. [Freesound APIv2 — Resources (search, `filter=license:…`, fields)](https://freesound.org/docs/api/resources_apiv2.html)
2. [Freesound — Frequently Asked Questions (licenses: CC0/CC-BY/CC-BY-NC)](https://freesound.org/help/faq/)
3. [Sonniss — GameAudioGDC archive (all yearly bundles + torrents + mirrors)](https://sonniss.com/gameaudiogdc/)
4. [Sonniss — #GameAudioGDC Bundle License (royalty-free terms; AI-training prohibition)](https://sonniss.com/gdc-bundle-license/)
5. [Sonniss #GameAudioGDC Bundle Licensing Agreement (PDF, full text incl. AI clause)](https://gamesounds.xyz/Sonniss.com%20-%20GDC%202016%20-%20Game%20Audio%20Bundle/Licensing.pdf)
6. [FSD50K — Zenodo record 4060432 (files, splits, per-clip license counts)](https://zenodo.org/records/4060432)
7. [FSD50K: An Open Dataset of Human-Labeled Sound Events — Fonseca et al., arXiv:2010.00475](https://arxiv.org/abs/2010.00475)
8. [Clotho: an Audio Captioning Dataset — Drossos, Lipping, Virtanen, ICASSP 2020 (arXiv:1910.09387)](https://arxiv.org/abs/1910.09387)
9. [Clotho v2 — Zenodo record (dev/val/eval audio + captions, CC-BY)](https://zenodo.org/records/4783391)
10. [DCASE 2024 Task 6b — Language-Based Audio Retrieval (Clotho, metrics R@k/mAP)](https://dcase.community/challenge2024/task-language-based-audio-retrieval)
11. [DCASE 2022 Task 6a — Automated Audio Captioning (Clotho v2 splits)](https://dcase.community/challenge2022/task-automatic-audio-captioning)
12. [AudioCaps: Generating Captions for Audios in The Wild — Kim et al., NAACL 2019](https://aclanthology.org/N19-1011/)
13. [AudioCaps dataset (captions + splits) — Hugging Face mirror `d0rj/audiocaps`](https://huggingface.co/datasets/d0rj/audiocaps)
14. [WavCaps: A ChatGPT-Assisted Weakly-Labelled Audio Captioning Dataset — Mei et al., arXiv:2303.17395](https://arxiv.org/abs/2303.17395)
15. [WavCaps — GitHub (metadata, sources, academic-only license)](https://github.com/XinhaoMei/WavCaps)
16. [Auto-ACD: A Large-scale Dataset for Audio-Language Representation Learning — arXiv:2309.11500](https://arxiv.org/abs/2309.11500)
17. [Audio Retrieval with Natural Language Queries: A Benchmark Study (SoundDescs) — Koepke et al., arXiv:2112.09418](https://arxiv.org/abs/2112.09418)
18. [Sound Effects Dataset Unification With the Universal Category System (EnvSound-UCS) — arXiv:2606.05571](https://arxiv.org/abs/2606.05571)
19. [FoleySet: A Multi-Level Human-Annotated Foley Sound Dataset — arXiv:2606.25980](https://arxiv.org/abs/2606.25980)
20. [ESC-50: Dataset for Environmental Sound Classification — Piczak (GitHub, CC-BY-NC)](https://github.com/karolpiczak/ESC-50)
21. [UrbanSound8K — Salamon, Jacoby, Bello (dataset page, CC-BY-NC)](https://urbansounddataset.weebly.com/urbansound8k.html)
22. [Universal Category System (UCS) — official site (82 cat / ~753 subcat, public domain)](https://universalcategorysystem.com/)
23. [BBC Sound Effects — Licensing (RemArc, non-commercial)](https://sound-effects.bbcrewind.co.uk/licensing)
24. [Large Language Models Can Accurately Predict Searcher Preferences — Thomas et al., arXiv:2309.10621](https://arxiv.org/abs/2309.10621)
25. [LLMJudge: LLMs for Relevance Judgments — arXiv:2408.08896](https://arxiv.org/abs/2408.08896)
26. [Generative Information Retrieval Evaluation / synthetic test collections — arXiv:2404.08137](https://arxiv.org/abs/2404.08137)
27. [Large-scale Contrastive Language-Audio Pretraining (LAION-CLAP) — Wu et al., arXiv:2211.06687](https://arxiv.org/abs/2211.06687)
28. [`laion/clap-htsat-unfused` — Hugging Face model card (HTSAT + RoBERTa, ~150–200 M params)](https://huggingface.co/laion/clap-htsat-unfused)
29. [Benchmarking LanceDB IVF-PQ (build time, storage, Recall@10) — LanceDB blog](https://www.lancedb.com/blog/benchmarking-lancedb-92b01032874a-2)
30. [LanceDB — Vector Indexes documentation (IVF-PQ partitions/sub-vectors guidance)](https://docs.lancedb.com/indexing/vector-index)
