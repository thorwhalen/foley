# Audio Embeddings, Indexing, Vector Search, Taxonomies & the Sound Metadata Schema

*Research brief for **foley** — the searchable-SFX facade. Focus: how to make a sound
library searchable by keyword **and** by meaning, local-first, on a `dol`-style
`Mapping` abstraction that scales to the cloud without rewriting business logic.*

*Compiled 2026-07. Versions and dates are noted inline; prefer re-checking model
cards and library changelogs before pinning.*

---

## Abstract

The core capability foley needs is **text-query → audio retrieval** ("distant
thunder rumble", "glass shattering on tile") plus **audio ↔ audio similarity**
("more sounds like this one"). Both fall out of a single mechanism: a **joint
text–audio embedding space**. The state of the art for this is **CLAP**
(Contrastive Language–Audio Pretraining) [1][2][3], which projects audio and text
into one shared vector space so a text query and a matching sound land near each
other. This brief recommends **LAION-CLAP `larger_clap_general`** (512-d,
Apache-2.0) as foley's default embedder [1][4][5], with audio-only encoders
(PANNs, PaSST, OpenL3, VGGish) [6][7][8][9] kept as swappable alternatives behind
an `Embedder` protocol.

For the index, foley should be **hybrid**: pure vector search alone misses exact
tokens (UCS CatIDs, product names, onomatopoeia) that matter for SFX, so a
**BM25 keyword index over tags + caption** is fused with **CLAP vector search**
via **Reciprocal Rank Fusion (RRF, k=60)** [10][11][12]. The recommended
local-first store is **LanceDB** [13][14] — one embedded dependency that provides
vector search, BM25 full-text search, metadata filtering, and RRF reranking in a
single query plan, backed by files that run **unchanged on local disk or S3**.
That last property is the exact match to foley's `dol` philosophy: the sound
library is a `Mapping`, and every backing store swaps local→cloud behind a stable
interface. **sqlite-vec + FTS5** [15] is the pure-single-file minimalist
fallback. Taxonomies (**AudioSet ontology** [16] and **UCS** [17][18]) become the
controlled vocabulary for foley's category filters and hierarchical browse.

---

## 1. Text–Audio Joint Embeddings (the retrieval engine)

### 1.1 Why a joint space

A joint (multimodal) embedding trains an **audio encoder** and a **text encoder**
with a contrastive loss so that a clip and its caption are pulled together and
mismatches pushed apart [1][3]. Two payoffs for foley from **one** model:

- **Zero-shot text→audio search**: embed the query string, nearest-neighbour the
  audio embeddings. No per-tag classifier, no training — arbitrary natural-language
  queries work out of the box [3].
- **Audio→audio similarity**: embed a reference clip, nearest-neighbour the rest.
  Same vectors, no extra model.

Audio-only encoders (§1.4) give you only the second capability; CLAP gives both,
which is why it is foley's default.

### 1.2 LAION-CLAP (recommended default)

- **Architecture**: HTS-AT (Swin-Transformer) audio encoder + RoBERTa text
  encoder, each projected to a shared latent space [1][4].
- **Embedding dimension**: **512** (`projection_dim=512`) [4].
- **Training data**: LAION-Audio-630K (~630k audio–text pairs, ~4,300 h) spanning
  music, speech, and **environmental / general sound** — the last is what matters
  for SFX [1].
- **License**: **Apache-2.0** [5] — clean for a library others `pip install`.
- **Checkpoints on the Hub** [5]:

  | Checkpoint | Notes | Downloads (rank) |
  |---|---|---|
  | `laion/larger_clap_general` | general audio incl. environmental SFX — **foley default** | 10.7M |
  | `laion/clap-htsat-unfused` | original 512-d baseline | 6.0M |
  | `laion/clap-htsat-fused` | feature-fusion variant (variable-length audio) | — |
  | `laion/larger_clap_music` | music-specialised | — |
  | `laion/larger_clap_music_and_speech` | music + speech | 1.0M |

- **Retrieval quality** (text→audio, higher = better): larger LAION-CLAP reaches
  roughly **R@1 ≈ 36–41 on AudioCaps** and lower on Clotho (harder, out-of-distribution
  captions) [1][19]. AudioCaps numbers are flattered because AudioCaps overlaps the
  training distribution [19] — treat cross-dataset Clotho as the more honest signal.
- **How to load/run** (HF `transformers`, the clean path) [4]:

  ```python
  import torch, librosa
  from transformers import ClapModel, ClapProcessor

  model = ClapModel.from_pretrained("laion/larger_clap_general")
  proc  = ClapProcessor.from_pretrained("laion/larger_clap_general")

  # text -> 512-d embedding
  t = proc(text=["distant thunder rumble"], return_tensors="pt", padding=True)
  text_emb = model.get_text_features(**t)          # (1, 512)

  # audio -> 512-d embedding (48 kHz mono expected)
  wav, _ = librosa.load("thunder.wav", sr=48000, mono=True)
  a = proc(audios=wav, sampling_rate=48000, return_tensors="pt")
  audio_emb = model.get_audio_features(**a)        # (1, 512)
  ```
  `ClapAudioModelWithProjection` / `ClapTextModelWithProjection` expose the same
  outputs if you want only one branch [4]. The alternative `laion_clap` pip package
  works too, but the `transformers` API is the more maintainable dependency.
  **Always L2-normalise** embeddings before cosine/inner-product search.

### 1.3 Microsoft MS-CLAP (strong alternative — but license caveat)

- **Versions**: `2022` (CNN14 audio + BERT text), `2023` (HTS-AT audio + GPT-2
  text), and `clapcap` (audio-captioning head) [2][3][20].
- **Embedding dimension**: **1024** [20].
- **Training**: ~128k pairs from FSD50K, Clotho v2, AudioCaps, MACS — heavier on
  curated sound-event data than LAION [3].
- **License**: **MS-PL (Microsoft Public License)** [20] — permissive-ish but
  **non-OSI-standard**; a friction point for a broadly-distributed façade. This is
  the main reason foley defaults to LAION (Apache-2.0) rather than MS-CLAP.
- **Load**: `pip install msclap`; `CLAP(version='2023')`, then
  `get_audio_embeddings()` / `get_text_embeddings()` [2].

MS-CLAP 2023 is often competitive or better on curated sound-event retrieval;
keep it available as a swappable backend, not the default.

### 1.4 Audio-only encoders (similarity, tagging, fallback)

Use these when you need audio→audio similarity, cheap CPU inference, or
AudioSet-label prediction — but note they give **no text query** capability alone.

| Model | Encoder | Emb. dim | Trained on | Best for | Ref |
|---|---|---|---|---|---|
| **PANNs (CNN14)** | CNN | **2048** | AudioSet | strong general SFX embeddings + 527 AudioSet-label tagging head | [6] |
| **PaSST** | Transformer (patchout) | ~768 | AudioSet | SOTA-ish audio repr; beats PANNs at equal data | [7] |
| **OpenL3** | CNN (self-sup A/V) | 512 / 6144 | AudioSet (audio+video) | music-leaning, easy `openl3` pip | [8] |
| **VGGish** | VGG CNN | **128** | YouTube-8M/AudioSet | legacy baseline, tiny, ubiquitous | [9] |

**Verdict for foley:** default to **CLAP** for the joint space (query + similarity
in one model). Optionally attach a **PANNs CNN14** tagging head to *auto-populate
AudioSet labels* on ingest (§4/§5), so untagged sounds still get structured tags.

---

## 2. Indexing Infrastructure (vector store comparison)

The decision axes for foley: **local-first/embeddable** (no server to run),
**metadata filtering**, **keyword/BM25 in the same engine**, **scale**, and a
**cloud path that preserves the `dol` Mapping abstraction** (ideally the same code
against local files or S3).

| Store | Type | Local-first / embed | Keyword (BM25) built in | Metadata filter | Scale | Cloud path | `dol`/store fit | Ref |
|---|---|---|---|---|---|---|---|---|
| **LanceDB** | Embedded, columnar (Lance) | **Yes — in-process, no server** | **Yes (Tantivy FTS)** | Yes (SQL predicates) | ↑ billions | **Same API on local dir *or* `s3://`** | **Excellent — files are the store; local→S3 unchanged** | [13][14] |
| **sqlite-vec** | SQLite extension | **Yes — one `.db` file** | Via SQLite **FTS5** (separate table) | Yes (SQL `WHERE`, KNN-aware bitmaps) | ~≤1M comfortably | Ship the file / litestream; no native S3 index | **Excellent — a single file behind a Mapping** | [15] |
| **FAISS** | Index **library** (not a DB) | Yes (in-proc) | **No** | **No** (indices only) | ↑ billions (ANN research-grade) | Roll your own persistence | Poor as-is — needs wrapper for ids/meta/persist | [21] |
| **Chroma** | Embedded / server | Yes (embedded mode) | Basic full-text | Yes | ~millions | Chroma Cloud / self-host | Good for quick start; less columnar/S3-native | [22] |
| **Qdrant** | Server (Rust) | Runs local via Docker/binary | Sparse vectors / payload text | **Rich payload filtering** | ↑ billions | Qdrant Cloud | Good cloud backend; a server, not a file | [23] |
| **Milvus** | Distributed server | Milvus-Lite (embedded) exists | Limited | Yes | ↑↑ massive | Zilliz Cloud | Overkill locally; strong at huge scale | [24] |
| **pgvector** | Postgres extension | Needs Postgres | Postgres **FTS (tsvector)** in same DB | Yes (SQL joins) | ≤ few M vectors comfortably | Managed Postgres (Supabase/RDS) | Great if you already run Postgres; SQL joins on meta | [25] |

**Reading of the table for foley:**

- **FAISS** is a fast ANN *library*, not a database: no persistence, no metadata,
  no keyword search [21]. Rejected as the default (you'd hand-build everything
  around it) but fine as an internal ANN engine if ever needed.
- **LanceDB** uniquely covers **vector + BM25 + metadata filtering + RRF
  reranking in one embedded dependency**, and its Lance files run **byte-identical
  on local disk or S3** [13][14]. That is precisely the local→cloud story `dol`
  wants: one interface, storage location is a config detail.
- **sqlite-vec** is the **minimalist single-file** option — the whole index is one
  SQLite file you can hand to a Mapping [15]. Trade-off: BM25 lives in a separate
  FTS5 table and you fuse ranks yourself (a few lines).
- **Qdrant / Milvus / pgvector** are the natural **cloud/scale backends** behind a
  `VectorIndex` protocol when a single machine is outgrown.

---

## 3. Hybrid Search (keyword + vector + fusion)

### 3.1 Why hybrid beats pure-vector for SFX

Dense CLAP vectors nail **semantic paraphrase** ("eerie wind" ≈ "spooky breeze")
but **underweight short literal tokens** — a UCS CatID like `WEATHRain`, a library
name, an onomatopoeia ("boing"), a specific product ("Nokia ringtone") [10][11].
BM25 nails those exact-match cases but cannot bridge synonyms. SFX metadata is a
mix of both: free-text captions (semantic) **and** terse controlled tags / IDs
(literal). Combining them consistently beats either alone — on standard IR
benchmarks hybrid RRF yields higher NDCG than BM25-only or vector-only [12].

### 3.2 Fusion: Reciprocal Rank Fusion (RRF)

Do **not** average BM25 scores (unbounded) with cosine similarity ([-1,1]) — the
scales are incompatible and one drowns the other [11][12]. **RRF fuses on *rank
position*, not score** [10]:

```
score(d) = Σ over rankers r  of  1 / (k + rank_r(d)),   k = 60 (standard)
```

A document ranked high by *either* the vector list or the BM25 list floats up;
k=60 damps the tail [10]. RRF is one line, parameter-light, and robust — the right
first-stage fusion for foley.

### 3.3 Optional second-stage rerank

For top-of-list precision, rerank the fused top-N (e.g. 50–100) with a more
expensive scorer [12]:

- **CLAP audio↔query rerank** (domain-native, no extra model): re-score the fused
  candidates by cosine(query_text_emb, audio_emb).
- or a **cross-encoder** reranker over caption text.

### 3.4 Where it runs

- **LanceDB**: `table.search(query, query_type="hybrid")` runs vector + BM25 and
  fuses with a built-in `RRFReranker()` (or a custom/cross-encoder reranker) in one
  call [14]. This is the least-code path.
- **sqlite-vec + FTS5**: run the KNN query and the FTS5 `MATCH` query, fuse the two
  id→rank lists with a ~10-line RRF function.

---

## 4. The Sound Metadata Schema (canonical record)

The metadata record is foley's **SSOT** per sound; the audio bytes and the vector
live in separate stores keyed by the same `id`. Proposed canonical record
(embeddings referenced/optional so the record stays lightweight in list views):

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SoundRecord:
    # --- identity & provenance ---
    id: str                              # stable UUID / content hash (primary key)
    source: str                          # 'freesound' | 'bbc' | 'ucs_library' | 'user' ...
    uri: str                             # blob-ref: local path OR s3://... OR https://...
    license: str                         # SPDX id or 'CC0'/'CC-BY-4.0'/'proprietary'
    attribution: Optional[str] = None    # required credit string (CC-BY etc.)
    provenance: dict = field(default_factory=dict)  # {orig_id, url, downloaded_at, ...}

    # --- descriptive text (feeds BM25 + human display) ---
    caption: Optional[str] = None        # free-text description / one-liner
    tags: list[str] = field(default_factory=list)     # free + controlled tags

    # --- controlled taxonomy (feeds filters & browse) ---
    ucs_category: Optional[str] = None   # UCS CatID, e.g. 'WEATHRain'
    ucs_subcategory: Optional[str] = None
    audioset_labels: list[str] = field(default_factory=list)  # AudioSet MIDs / names

    # --- audio technical facts ---
    duration_s: Optional[float] = None
    sample_rate: Optional[int] = None    # Hz
    channels: Optional[int] = None       # 1=mono, 2=stereo
    loudness_lufs: Optional[float] = None  # integrated, ITU-R BS.1770-4 / EBU R128
    format: Optional[str] = None         # 'wav' | 'flac' | 'mp3' | 'ogg'

    # --- retrieval index refs (NOT stored inline in list views) ---
    embedding_model: Optional[str] = None   # 'laion/larger_clap_general'
    embedding_dim: Optional[int] = None     # 512
    embedding_ref: Optional[str] = None     # id into the vector index (or inline vector)

    schema_version: int = 1
```

| Field | Purpose | Feeds |
|---|---|---|
| `id` | primary key across all stores | everything |
| `source`, `uri`, `license`, `attribution`, `provenance` | sourcing & legal reuse | filter, compliance |
| `caption`, `tags` | human + machine description | **BM25 keyword index** |
| `ucs_category/subcategory` | industry taxonomy | **category filter / browse** [17] |
| `audioset_labels` | ontology labels (auto via PANNs) | **hierarchical filter** [16] |
| `duration_s`, `sample_rate`, `channels`, `format` | technical selection | filter/sort |
| `loudness_lufs` | perceptual level for mixing into narration | filter/normalise [26] |
| `embedding_*` | CLAP vector linkage | **vector index** |

**Design notes (progressive disclosure):** only `id` + `uri` are strictly
required; everything else is optional and can be **auto-enriched on ingest** —
duration/sample_rate/channels from the audio header, `loudness_lufs` via
`pyloudnorm` (ITU-R BS.1770-4) [26], `audioset_labels` via a PANNs tagging head
[6], `ucs_*` parsed from a UCS-conformant filename [17][18], and the CLAP
`embedding_*` from the default embedder (§1.2). The record deliberately stores a
**blob-ref (`uri`), not audio bytes**, so the metadata store stays small and the
bytes live in the `dol` blob store (local files → S3 unchanged).

---

## 5. Taxonomies (controlled vocabulary for filters & browse)

foley should carry **two complementary taxonomies** — machine-oriented and
industry-oriented — rather than invent its own.

### 5.1 AudioSet ontology (machine labels, hierarchical)

- **What**: Google's ontology of **632 audio event classes** (527 are used as
  trainable labels) arranged in a hierarchy up to **6 levels deep**, released as
  **JSON** [16]. Each node has a **MID** (`/m/...`) identifier and a `child_ids`
  list encoding the tree (e.g. *Animal → Domestic → Dog → Bark*) [16].
- **Why for foley**: it is the label space of PANNs/PaSST/VGGish, so tagging models
  **emit AudioSet labels directly** — free structured tags on ingest. The hierarchy
  powers "show me all *Vehicle* sounds" (roll up children) filters.
- **License**: ontology is **CC-BY** [16].

### 5.2 UCS — Universal Category System (industry standard)

- **What**: the sound-design industry's de-facto taxonomy — **~82 main
  Categories** (Air…Wood) and **750+ SubCategories**, each with a short **CatID**,
  plus a **filename convention** that encodes category into the file name
  (`CatID_FXName_...`) [17][18]. **Public-domain** initiative; adopted by Pro Sound
  Effects, Soundminer, Sound Ideas, etc. [17].
- **Why for foley**: real SFX libraries already ship UCS-tagged; parsing the
  filename yields `ucs_category`/`ucs_subcategory` for **zero-cost structured
  metadata**, and UCS is the natural facet for the primary category filter/browse
  tree that sound designers expect.

### 5.3 How they structure foley's filters

- **UCS** = the **primary user-facing category tree** (what humans browse/filter).
- **AudioSet** = the **auto-generated label layer** (what models emit; a secondary
  filter and a bridge to ML tooling).
- Keep both as fields on `SoundRecord` (§4); maintain a small mapping table where
  they overlap. Neither should be foley's *identity* — the CLAP vector + BM25 tags
  do the heavy retrieval; taxonomies do faceting and browse.

---

## 6. Recommendations for foley (local-first index that scales to cloud)

### 6.1 The `dol`-native architecture: a facade over three Mappings + two indexes

Model the sound library as a **facade** composing stores that are all `Mapping`s,
so each swaps local→cloud behind a stable interface:

```
SoundLibrary (facade)
├── sounds : Mapping[id -> bytes]        # audio blobs   (dol.Files  → S3Store)
├── meta   : Mapping[id -> SoundRecord]  # canonical SSOT (JSON files → S3 / Postgres)
├── vindex : VectorIndex                 # CLAP 512-d     (LanceDB local dir → s3://)
└── kindex : KeywordIndex (BM25)         # tags+caption   (LanceDB FTS  → same table)
```

Public surface (progressive disclosure — the simple thing is one call):

```python
lib = foley.SoundLibrary()                 # sensible local defaults, works out of the box
lib.search("distant thunder rumble", k=10) # hybrid: CLAP vector ⊕ BM25 tags, RRF-fused
lib.similar(sound_id, k=10)                # audio↔audio via CLAP embeddings
lib[sound_id]                              # -> SoundRecord (from meta)
lib.audio(sound_id)                        # -> bytes       (from sounds)
lib.filter(ucs_category="WEATH", min_lufs=-30)   # metadata facets
```

`search()` internally: embed query with the default CLAP embedder → vector KNN on
`vindex` **and** BM25 on `kindex` → **RRF (k=60)** fuse → optional CLAP
audio-rerank → hydrate `SoundRecord`s from `meta`. All three storage concerns are
injected, so nothing in `search()`/`similar()` changes when you move to the cloud.

### 6.2 Two backend tiers (same façade, swapped stores)

- **Tier 0 — default, zero-server, single machine.** `sounds` = `dol.Files` under
  `~/.local/share/foley/audio/`; `meta` = JSON (or SQLite); **`vindex`+`kindex` =
  one LanceDB table** (vector column + text columns → vector search, BM25 FTS,
  metadata filter, RRF reranker in a single dependency, no server) [13][14].
  *Ultra-minimal variant:* **sqlite-vec + FTS5** in a single `.db` file [15], with a
  ~10-line RRF fuser — pick this if "one file, stdlib-adjacent" matters more than
  built-in fusion.
- **Tier 1 — cloud / scale.** Flip config, not code: LanceDB `connect("s3://…")`
  keeps the **identical API** on object storage [13][14]; or bind the `VectorIndex`
  protocol to **Qdrant/Milvus/pgvector** [23][24][25] for very large or
  multi-writer deployments. `sounds`/`meta` swap `dol.Files` → an S3 store (or
  Postgres for `meta`) with no change to retrieval logic.

Keep the boundary as **small protocols** (`Embedder`, `VectorIndex`,
`KeywordIndex`, and the two `Mapping`s). That is what lets foley honour "simple
things simple, complex things possible": the defaults just work; every piece is
replaceable via keyword-only injection.

### 6.3 Default embedding model

**`laion/larger_clap_general`** (LAION-CLAP, **512-d**, **Apache-2.0**), loaded via
HF `transformers` `ClapModel`/`ClapProcessor` [4][5]. Rationale: (1) **one joint
space** serves both text→audio search and audio↔audio similarity; (2) **general
audio** training suits environmental SFX, not just music/speech; (3) **Apache-2.0**
license is clean for a widely-installed façade (vs MS-CLAP's non-standard MS-PL)
[5][20]; (4) trivial to load and CPU-runnable for modest libraries. Keep it behind
an `Embedder` protocol so **MS-CLAP 2023** (1024-d, curated-SFX strength) [2][3] or
**PANNs** (2048-d + AudioSet tagging) [6] can be dropped in — and store
`embedding_model`/`embedding_dim` on every record so mixed-model libraries stay
coherent.

### 6.4 Ingest enrichment (fills the schema automatically)

On add: read audio header → `duration_s`/`sample_rate`/`channels`/`format`;
`pyloudnorm` → `loudness_lufs` (BS.1770-4/R128) [26]; parse UCS filename → `ucs_*`
[17]; PANNs head → `audioset_labels` [6]; default CLAP → `embedding_*` [4]; index
`tags`+`caption` into BM25 [14]. Untagged, foreign sounds thus become fully
searchable with no manual tagging.

---

## REFERENCES

1. Wu Y, Chen K, Zhang T, et al. *Large-Scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation* (LAION-CLAP), arXiv:2211.06687, 2022–2023. [arxiv.org/abs/2211.06687](https://arxiv.org/abs/2211.06687)
2. Microsoft. *CLAP: Learning audio concepts from natural language supervision* (GitHub, `msclap` package). [github.com/microsoft/CLAP](https://github.com/microsoft/CLAP)
3. Elizalde B, Deshmukh S, Al Ismail M, Wang H. *CLAP: Learning Audio Concepts From Natural Language Supervision*, arXiv:2206.04769, 2022; and *Natural Language Supervision for General-Purpose Audio Representations* (MS-CLAP 2023), arXiv:2309.05767. [arxiv.org/abs/2206.04769](https://arxiv.org/abs/2206.04769) · [arxiv.org/abs/2309.05767](https://arxiv.org/abs/2309.05767)
4. Hugging Face. *CLAP — Transformers documentation* (`ClapModel`, `ClapProcessor`, `get_audio_features`/`get_text_features`, `projection_dim=512`). [huggingface.co/docs/transformers/model_doc/clap](https://huggingface.co/docs/transformers/model_doc/clap)
5. LAION. Model cards: [laion/larger_clap_general](https://huggingface.co/laion/larger_clap_general), [laion/clap-htsat-unfused](https://huggingface.co/laion/clap-htsat-unfused), [laion/larger_clap_music_and_speech](https://huggingface.co/laion/larger_clap_music_and_speech) (Apache-2.0).
6. Kong Q, Cao Y, Iqbal T, et al. *PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition* (CNN14, 2048-d, AudioSet tagging), arXiv:1912.10211, 2020. [arxiv.org/abs/1912.10211](https://arxiv.org/abs/1912.10211)
7. Koutini K, Schlüter J, Eghbal-zadeh H, Widmer G. *Efficient Training of Audio Transformers with Patchout* (PaSST), arXiv:2110.05069, 2021; *Learning General Audio Representations with Large-Scale Training of Patchout Audio Transformers*, arXiv:2211.13956. [arxiv.org/abs/2110.05069](https://arxiv.org/abs/2110.05069)
8. Cramer J, Wu H-H, Salamon J, Bello JP. *Look, Listen, and Learn More: Design Choices for Deep Audio Embeddings* (OpenL3, 512/6144-d). [github.com/marl/openl3](https://github.com/marl/openl3)
9. Hershey S, Chaudhuri S, Ellis DPW, et al. *CNN Architectures for Large-Scale Audio Classification* (VGGish, 128-d), 2017. [research.google/pubs/pub45611](https://research.google/pubs/cnn-architectures-for-large-scale-audio-classification/)
10. Cormack GV, Clarke CLA, Büttcher S. *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods* (RRF, k=60), SIGIR 2009. [cormack.uwaterloo.ca/cormacksigir09-rrf.pdf](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
11. Weaviate. *Hybrid Search Explained* (BM25 + vector, score incompatibility). [weaviate.io/blog/hybrid-search-explained](https://weaviate.io/blog/hybrid-search-explained)
12. Microsoft Learn. *Hybrid search scoring (RRF) — Azure AI Search*. [learn.microsoft.com/azure/search/hybrid-search-ranking](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
13. LanceDB (GitHub) — embedded multimodal retrieval on the Lance columnar format; local dir or S3. [github.com/lancedb/lancedb](https://github.com/lancedb/lancedb)
14. LanceDB Docs — *Hybrid Search* (vector + BM25 FTS + `RRFReranker`, custom rerankers). [docs.lancedb.com/search/hybrid-search](https://docs.lancedb.com/search/hybrid-search)
15. Asg017. *sqlite-vec* — vector search as a SQLite extension (BLOB vectors, KNN, metadata bitmaps; pair with FTS5). [github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
16. Gemmeke JF, Ellis DPW, Freedman D, et al. *Audio Set: An Ontology and Human-Labeled Dataset for Audio Events* (632 classes, 6-level hierarchy, JSON w/ `child_ids`, CC-BY), ICASSP 2017. [research.google.com/pubs/archive/45857.pdf](https://research.google.com/pubs/archive/45857.pdf) · ontology JSON: [github.com/audioset/ontology](https://github.com/audioset/ontology)
17. Universal Category System (UCS) — official site (82 categories, 750+ subcategories, CatID + filename convention, public domain). [universalcategorysystem.com](https://universalcategorysystem.com/)
18. *Sound Effects Dataset Unification With the Universal Category System*, arXiv:2606.05571, 2026. [arxiv.org/abs/2606.05571](https://arxiv.org/abs/2606.05571)
19. LAION-CLAP v4 (feature fusion + keyword-to-caption) — retrieval results on AudioCaps/Clotho and the in-distribution caveat. [arxiv.org/html/2211.06687v4](https://arxiv.org/html/2211.06687v4)
20. Microsoft. *microsoft/msclap* model card (versions 2022/2023/clapcap, 1024-d, license MS-PL). [huggingface.co/microsoft/msclap](https://huggingface.co/microsoft/msclap)
21. Johnson J, Douze M, Jégou H. *FAISS: Billion-scale similarity search* (ANN library — no metadata/persistence/keyword). [github.com/facebookresearch/faiss](https://github.com/facebookresearch/faiss)
22. Chroma — embeddings database for LLM apps. [trychroma.com](https://www.trychroma.com/)
23. Qdrant — vector search engine (Rust) with rich payload filtering. [qdrant.tech](https://qdrant.tech/)
24. Milvus — distributed vector database (Milvus-Lite for embedded). [milvus.io](https://milvus.io/)
25. pgvector — vector similarity search for Postgres (SQL joins on metadata + `tsvector` FTS). [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
26. Steinmetz CJ, Reiss JD. *pyloudnorm* — ITU-R BS.1770-4 / EBU R128 integrated loudness (LUFS) meter in Python. [github.com/csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm)
27. dol — Python data-object-layer: storage as `Mapping`, local→cloud behind one interface. [github.com/i2mint/dol](https://github.com/i2mint/dol)
