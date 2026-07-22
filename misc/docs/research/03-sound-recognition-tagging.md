# Sound Recognition, Auto-Tagging, Audio Captioning & Segmentation for `foley`

> Research module 03 — the models that turn a raw sound file into searchable metadata.
> Compiled 2026-07-22. Primary sources cited Vancouver-style; see **REFERENCES**.

## Abstract

`foley` needs to take a directory of un-annotated sound-effect (SFX) files that Thor already owns and make each one findable by keyword **and** by meaning. Three model families do the heavy lifting, and they compose into a pipeline rather than competing:

1. **Supervised audio taggers** map a clip onto a fixed vocabulary — almost universally the **AudioSet** ontology of 527 hierarchical classes [1]. They are fast, cheap, deterministic, and give calibrated per-class probabilities. Representatives (in rough chronological/quality order): **YAMNet** → **PANNs/CNN14** → **AST** → **HTS-AT** / **PaSST** → **BEATs** (current single-model SOTA, mAP ≈ 0.506) [2–8].
2. **Zero-shot taggers (CLAP)** embed audio and free text into a shared space, so you can score a clip against **any** label set you write down — critical for custom SFX taxonomies (UCS, your own tags) that AudioSet does not cover [9–11].
3. **Automated Audio Captioning (AAC)** emits a natural-language sentence ("a heavy wooden door creaks open then slams"). These captions are *gold* for both keyword and semantic (embedding) search. Options span small dedicated seq2seq captioners (**EnCLAP**, **WavCaps** systems, **Pengi**) and large audio-LLMs (**Qwen2-Audio**, **Audio Flamingo 2/3**, **SALMONN**) [12–18]. Benchmarks are **AudioCaps** and **Clotho**, scored by **CIDEr / SPICE / SPIDEr** [19–21].

Two auxiliary tools handle *long or layered* recordings: **Sound Event Detection (SED)** segments a recording into time-stamped events (**DCASE Task 4**) [22–24], and **universal source separation** splits a layered clip into individual stems before tagging [25–27].

The recommended `foley` ingestion pipeline (detailed at the end) is: **(optional) segment/separate → supervised AudioSet tag (PANNs or BEATs) → zero-shot CLAP tag against your taxonomy → caption (EnCLAP default, Qwen2-Audio for richness) → emit a metadata record** carrying tags, scores, a caption, and CLAP embeddings for later semantic search.

---

## Part 1 — Supervised Audio Tagging (the AudioSet family)

### The shared substrate: AudioSet + its ontology

AudioSet is ~2 million 10-second YouTube clips weakly labeled with **527 classes** organized as a **hierarchical ontology** (e.g. `Animal → Domestic animals → Dog → Bark`) [1]. Every model below outputs a 527-dim (YAMNet: 521-dim) vector of per-class probabilities against this ontology, and the ontology's parent/child structure is directly reusable as a facet tree in `foley`'s search index. The standard quality metric is **mAP** (mean average precision) over the 527 classes on the AudioSet eval set — higher is better; the original AudioSet CNN baseline was 0.314 [2].

### Comparison table — supervised taggers

| Model | Arch / params | AudioSet mAP (single) | How to run | License | Notes |
|---|---|---|---|---|---|
| **YAMNet** [3] | MobileNet-v1, 3.7 M | **0.306** (521 cls, balanced) | TF-Hub / TFLite | Apache-2.0 | Tiny, mobile/edge, embeddings + 521 scores; 6 offensive classes dropped |
| **PANNs / CNN14** [2] | CNN, ~81 M | **0.431** (Wavegram-Logmel 0.439; MobileNetV1 0.389) | `pip install panns-inference` | Apache-2.0 | Workhorse backbone; also ships an SED variant with framewise output |
| **AST** [4] | ViT (DeiT-init), 86.6 M | **0.459** (ensemble 0.485) | HF `transformers` | BSD-3-Clause | First conv-free audio transformer; huge HF adoption |
| **HTS-AT** [5] | Swin-style hierarchical, ~28–31 M | **0.471** (ensemble 0.487) | GitHub (RetroCirce) | MIT | 35 % of AST's params, 15 % train time; used as the CLAP audio encoder |
| **PaSST** [6] | ViT + Patchout, ~86 M | **0.471** (up to ~0.496 tuned) | `pip install hear21passt` | MIT | "Patchout" drops patches → faster training + regularization |
| **BEATs** [7,8] | ViT + acoustic tokenizer, ~90 M | **0.486** (iter3+); **0.506** ensemble — **SOTA** | GitHub (microsoft/unilm) | MIT | Self-supervised pretraining; the default embedder for DCASE SED baselines |

> Reading the table: for `foley`, **PANNs/CNN14** is the pragmatic default (one-line install, CPU-friendly, battle-tested), while **BEATs** is the accuracy ceiling if you want the best supervised labels and are willing to manage a GitHub checkpoint. AST sits in between with the smoothest Hugging Face DX.

### Per-model detail + code

#### PANNs / CNN14 — the pragmatic default [2]

CNN14 (Kong et al., 2020) is a 14-layer log-mel CNN, mAP **0.431**. The `panns_inference` package wraps two heads: `AudioTagging` (clip-level 527 scores + 2048-d embedding) and `SoundEventDetection` (framewise 527 scores → timestamps, see Part 4). Checkpoints (`Cnn14_mAP=0.431.pth`) auto-download from Zenodo.

```python
# pip install panns-inference librosa
import librosa
from panns_inference import AudioTagging, labels  # labels = 527 AudioSet class names

audio, _ = librosa.load("door_slam.wav", sr=32000, mono=True)  # PANNs expects 32 kHz
audio = audio[None, :]                                          # (batch, samples)

at = AudioTagging(checkpoint_path=None, device="cpu")          # downloads CNN14
clipwise, embedding = at.inference(audio)                       # (1,527), (1,2048)

top = sorted(zip(labels, clipwise[0]), key=lambda kv: -kv[1])[:5]
# e.g. [('Slam', 0.62), ('Door', 0.41), ('Wood', 0.22), ...]
```

The `embedding` (2048-d) is itself a reusable acoustic fingerprint for nearest-neighbour "sounds like this" search.

#### AST — Audio Spectrogram Transformer [4]

Best Hugging Face ergonomics; single-model mAP **0.459**, ensemble **0.485**. Model: [`MIT/ast-finetuned-audioset-10-10-0.4593`](https://hf.co/MIT/ast-finetuned-audioset-10-10-0.4593) (86.6 M params, BSD-3-Clause).

```python
# pip install transformers torch torchaudio
from transformers import pipeline
clf = pipeline("audio-classification",
               model="MIT/ast-finetuned-audioset-10-10-0.4593")
clf("door_slam.wav", top_k=5)
# [{'score': 0.58, 'label': 'Door'}, {'score': 0.30, 'label': 'Slam'}, ...]
```

#### BEATs — current single-model SOTA [7,8]

BEATs (Microsoft, 2022) uses an iteratively self-distilled **acoustic tokenizer** + masked-audio-modeling pretraining, then fine-tunes on AudioSet to **0.486** single / **0.506** ensemble — the best audio-only result without external data. It is not a first-class `transformers` model; you load the checkpoint from `microsoft/unilm` (or community mirrors) with its own tiny module. It is also the standard **frozen embedder** feeding DCASE SED baselines and audio-LLMs (SALMONN uses BEATs for its non-speech encoder). Use BEATs when label quality matters more than install simplicity.

#### YAMNet / HTS-AT / PaSST — when to reach for them

- **YAMNet** [3]: pick it only for edge/mobile or ultra-cheap first-pass filtering; mAP 0.306 is materially weaker.
- **HTS-AT** [5]: matters less as a standalone tagger and more because it is the **audio tower inside LAION-CLAP** (Part 2) — so you effectively "get it for free" there.
- **PaSST** [6]: strong general-purpose embeddings; the `hear21passt` package exposes both scene embeddings and 527-class logits, and it is the audio encoder behind several top language-based-retrieval systems.

---

## Part 2 — Zero-Shot Tagging with CLAP

### Why it matters for `foley`

Supervised taggers can only ever say one of AudioSet's 527 words. SFX libraries use richer, domain-specific vocabularies — the **Universal Category System (UCS)**, Thor's own tags, onomatopoeia, mood words ("ominous", "whoosh", "retro UI blip"). **CLAP** (Contrastive Language-Audio Pretraining) [9,10] solves this: it trains an audio encoder (HTS-AT) and a text encoder (RoBERTa) with a CLIP-style contrastive loss so that an audio clip and its description land near each other in a shared embedding space. Then **zero-shot classification** is just: embed the clip once, embed each candidate label as a short prompt ("this is a sound of {label}"), and rank labels by cosine similarity. You can swap the label set at query time with zero retraining.

### How accurate is zero-shot vs supervised?

- **ESC-50** (50-class environmental sounds): LAION-CLAP reaches ~**91 %** zero-shot accuracy [10]; Microsoft CLAP-2023 reports **93.9 %** [11]. These rival *supervised* models on the same set — remarkable for never having seen the label list.
- **FSD50K**: Microsoft CLAP-2023 zero-shot mAP ≈ **0.52** [11].
- **Text↔audio retrieval** (the capability `foley` search rides on): LAION-CLAP hits **R@1 = 36.7 %** on AudioCaps and **18.2 %** on Clotho [10].

Rule of thumb: on vocabularies CLAP has seen described in training, zero-shot is within a few points of supervised; on truly novel/fine-grained labels it degrades but still beats keyword matching. **Best practice is hybrid** — use supervised AudioSet tags for the coarse ontology and CLAP zero-shot for your custom taxonomy, keeping both.

### Comparison table — CLAP checkpoints

| Checkpoint | Train data | ESC-50 zero-shot | License | Load |
|---|---|---|---|---|
| [`laion/clap-htsat-unfused`](https://hf.co/laion/clap-htsat-unfused) [10] | LAION-Audio-630K | ~89–91 % | Apache-2.0 | `transformers` |
| [`laion/larger_clap_general`](https://hf.co/laion/larger_clap_general) [10] | 630K + music + AudioSet | ~90 % | Apache-2.0 | `transformers` |
| [`microsoft/msclap`](https://hf.co/microsoft/msclap) (2023) [11] | 4.6 M pairs | **93.9 %** | MS-PL (research) | `pip install msclap` |
| [`davidrrobinson/BioLingual`](https://hf.co/davidrrobinson/BioLingual) | AnimalSpeak | — | (see card) | `transformers` | domain-specialized (bioacoustics) example of CLAP fine-tuning |

> For `foley`, prefer **LAION** checkpoints (Apache-2.0, commercial-friendly, one-line `transformers`). Microsoft CLAP is more accurate but MS-PL is research-oriented — check licensing before shipping.

### Zero-shot code (LAION-CLAP via `transformers`)

```python
# pip install transformers torch librosa
from transformers import ClapModel, ClapProcessor
import librosa, torch

model = ClapModel.from_pretrained("laion/larger_clap_general")
proc  = ClapProcessor.from_pretrained("laion/larger_clap_general")

audio, _ = librosa.load("whoosh.wav", sr=48000, mono=True)  # CLAP expects 48 kHz
# YOUR custom taxonomy — not AudioSet:
labels = ["magical whoosh", "sword swing", "wind gust", "UI swipe", "cloth movement"]
prompts = [f"this is a sound of {l}" for l in labels]

inp = proc(text=prompts, audios=audio, sampling_rate=48000,
           return_tensors="pt", padding=True)
with torch.no_grad():
    logits = model(**inp).logits_per_audio          # (1, n_labels)
    probs  = logits.softmax(dim=-1)[0]
ranked = sorted(zip(labels, probs.tolist()), key=lambda kv: -kv[1])
# [('magical whoosh', 0.71), ('UI swipe', 0.12), ...]
```

The same `model.get_audio_features(...)` / `get_text_features(...)` calls give you the **shared 512-d embeddings** — store the audio embedding per file and you get free natural-language search ("find a metallic scrape") by embedding the query text and doing nearest-neighbour. This is the single most valuable artifact for `foley`'s semantic search.

---

## Part 3 — Automated Audio Captioning (AAC)

### Why captions are gold

A caption ("a heavy wooden door creaks open then slams shut") is simultaneously (a) human-readable metadata, (b) a bag of searchable keywords, and (c) text you can embed for dense semantic retrieval. One caption populates several `foley` index fields at once. Two model classes exist: **dedicated captioners** (small, fast, purpose-built, run locally) and **audio-LLMs** (large, promptable, richer/controllable output, heavier).

### Metrics & benchmarks

- **Datasets**: **AudioCaps** (~50k clips from AudioSet, 1 caption train / 5 test) and **Clotho** (4,981 Freesound clips, 15–30 s, 5 captions each) [19,20]. Clotho is harder (longer, more diverse, no AudioSet leakage).
- **Metrics**: CIDEr (n-gram consensus), SPICE (scene-graph semantic), and the headline **SPIDEr = ½(CIDEr + SPICE)** [21]. Higher is better.

### Comparison table — captioners

| Model | Type / size | AudioCaps (CIDEr / SPIDEr) | Clotho (CIDEr / SPIDEr) | License | Access |
|---|---|---|---|---|---|
| **Pengi** [12] | Audio-LM, ~1 B | 0.752 / 0.271 | 0.416 / 0.271* | MIT | GitHub (microsoft) |
| **WavCaps** (HTSAT-BART) [15] | seq2seq, ~0.2 B | 0.787 / 0.485 | 0.462 / 0.297 | (see card) | GitHub / HF |
| **EnCLAP-large** [13] | EnCodec+CLAP→BART | **0.803 / 0.495** | 0.461 / 0.294 | MIT | GitHub (jaeyeonkim99) |
| **BEATs-Conformer-BART** [—] | seq2seq (DCASE'24) | — | strong | Apache-2.0 | [`slseanwu/beats-conformer-bart-audio-captioner`](https://hf.co/slseanwu/beats-conformer-bart-audio-captioner) |
| **Qwen2-Audio-7B** [16] | Audio-LLM, 8.4 B | competitive, promptable | competitive | Apache-2.0 | [`Qwen/Qwen2-Audio-7B-Instruct`](https://hf.co/Qwen/Qwen2-Audio-7B-Instruct) |
| **SALMONN-13B** [17] | Whisper+BEATs+Vicuna, 13 B | emergent | emergent | Apache-2.0 (code) | GitHub (bytedance) |
| **Audio Flamingo 2 / 3** [14,18] | Audio-LLM, 0.5–8.3 B | SOTA-class | SOTA-class | NVIDIA (non-commercial) | [`nvidia/audio-flamingo-3-hf`](https://hf.co/nvidia/audio-flamingo-3-hf) |

\* Pengi Clotho SPIDEr as reported in follow-up work; original paper reports SPIDEr ≈ 0.26 range. Numbers vary slightly by eval config.

> Take-away: **EnCLAP-large** is the strongest *dedicated* captioner (best AudioCaps CIDEr/SPIDEr, MIT license, runs on a modest GPU) → good `foley` default. The **audio-LLMs** (Qwen2-Audio, Audio Flamingo 3) produce richer, promptable, more "foley-aware" prose ("emphasize material and action") but cost a 7–13 B model per clip. Audio Flamingo's non-commercial license rules it out of a shipped product; Qwen2-Audio (Apache-2.0) is the commercial-safe LLM option.

### Per-model detail + code

#### EnCLAP — recommended dedicated captioner [13]

EnCLAP (Kim et al., ICASSP 2024) fuses two complementary encoders — **EnCodec** discrete acoustic tokens (fine detail) and **CLAP** sequence embeddings (semantics) — into a **BART** decoder, trained with a novel *masked codec modeling* objective. `EnCLAP-large` gets AudioCaps **CIDEr 0.803 / SPIDEr 0.495 / METEOR 0.255 / SPICE 0.188** [13]. Run from the official repo (`jaeyeonkim99/EnCLAP`); weights are on HF.

#### Qwen2-Audio — commercial-safe audio-LLM [16]

[`Qwen/Qwen2-Audio-7B-Instruct`](https://hf.co/Qwen/Qwen2-Audio-7B-Instruct) (8.4 B, Apache-2.0) takes an audio + a text instruction, so you steer the caption ("Describe this sound effect for a library: name the object, material, and action").

```python
# pip install transformers torch librosa
from transformers import Qwen2AudioForConditionalGeneration, AutoProcessor
import librosa, torch

mid = "Qwen/Qwen2-Audio-7B-Instruct"
proc  = AutoProcessor.from_pretrained(mid)
model = Qwen2AudioForConditionalGeneration.from_pretrained(mid, device_map="auto")

audio, sr = librosa.load("door.wav", sr=16000, mono=True)   # 16 kHz
conv = [{"role": "user", "content": [
            {"type": "audio", "audio": audio},
            {"type": "text",  "text": "Describe this sound effect: object, material, action."}]}]
text = proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
inp  = proc(text=text, audios=[audio], sampling_rate=16000, return_tensors="pt").to(model.device)
out  = model.generate(**inp, max_new_tokens=64)
print(proc.batch_decode(out[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0])
# "A heavy wooden door creaks as it swings open, then slams shut with a solid thud."
```

The same model also does **audio QA** ("Is this indoors or outdoors? Is it looped?"), which can populate extra structured fields.

#### Audio Flamingo 3 — highest quality, non-commercial [14,18]

[`nvidia/audio-flamingo-3-hf`](https://hf.co/nvidia/audio-flamingo-3-hf) (8.3 B) is current SOTA-class on many audio-understanding benchmarks and handles **long audio** with reasoning. License is NVIDIA non-commercial — excellent for offline research/enrichment of *your own* library, **not** for a distributed product. Smaller `audio-flamingo-2-0.5B` (MIT) exists for lighter use.

#### SALMONN / Pengi / WavCaps [12,15,17]

- **SALMONN-13B** [17]: Whisper (speech) + BEATs (audio) → Vicuna LLM; strong emergent captioning + reasoning, but speech-leaning and heavy.
- **WavCaps** [15]: as much a **dataset** as a model — 403k ChatGPT-cleaned audio-text pairs mined from FreeSound, BBC Sound Effects, SoundBible, AudioSet. Its HTSAT-BART captioner is a solid, light baseline, and the *dataset* is directly relevant if `foley` ever fine-tunes its own captioner/CLAP on SFX-style data.
- **Pengi** [12]: framed captioning as text-generation across 20+ audio tasks; good general audio-LM, MIT.

---

## Part 4 — Segmentation (SED) & Source Separation

Most SFX files are short, single-event clips where Parts 1–3 suffice. These two tools handle the exceptions: **long field recordings / ambiences** and **layered/mixed** clips.

### 4a. Sound Event Detection (SED) — timestamped events

SED = tagging **+ onset/offset times** ("dog bark 2.1–2.8 s; door slam 5.0–5.3 s"), enabling `foley` to slice a long recording into individually-taggable segments. The canonical benchmark is **DCASE Task 4** (Sound Event Detection in Domestic Environments, **DESED** dataset, 10 classes) [22–24].

- **Metric**: **PSDS** (Polyphonic Sound Detection Score), threshold-independent; PSDS1 rewards precise localization, PSDS2 penalizes cross-class confusion [22,23].
- **Baseline (2024)**: a **CRNN** consuming **frozen BEATs embeddings**, PSDS ≈ **0.483** on the DESED dev set [23]. This BEATs-embedding-into-CRNN recipe is the standard modern SED architecture.
- **Easiest practical route for `foley`**: PANNs' `SoundEventDetection` class already returns **framewise 527-class probabilities**; threshold + merge contiguous frames to get event spans — no training needed [2].

```python
# pip install panns-inference
from panns_inference import SoundEventDetection, labels
import librosa, numpy as np

audio, _ = librosa.load("ambience_2min.wav", sr=32000, mono=True)
sed = SoundEventDetection(checkpoint_path=None, device="cpu")
framewise = sed.inference(audio[None, :])[0]          # (frames, 527), ~50 fps

# turn a class's frame probs into (start,end) spans over a threshold
def spans(cls_idx, thr=0.3, fps=50):
    hot = framewise[:, cls_idx] > thr
    out, s = [], None
    for i, on in enumerate(hot):
        if on and s is None: s = i
        if not on and s is not None: out.append((s/fps, i/fps)); s = None
    return out
```

Newer SED research (multi-stage transformer fine-tuning, e.g. PaSST/AST-for-SED [6]) pushes PSDS higher but adds training complexity `foley` likely does not need at ingestion time.

### 4b. Source separation — splitting layered clips

If a clip mixes several SFX (footsteps *over* rain *over* a car), separating first yields cleaner per-source tags/captions. Options, cheapest→richest:

- **Google FUSS + TDCN++** — "Free Universal Sound Separation": separates an arbitrary mixture into up to 4 variable sources; the classic open baseline [25].
- **Text-/query-guided (2024–25)** — **OmniSep**, **OpenSep** (LLM + textual inversion), **CodecSep**, **USE**: "extract the {glass shatter}" from a mixture via a text prompt [26,27]. These align naturally with CLAP prompts but are heavier and less battle-tested.
- **Demucs** (music/stems) — only relevant if `foley` handles musical stingers; not general SFX.

**Guidance**: treat separation as **opt-in**. Detect "is this layered?" cheaply (e.g. multiple high-confidence, co-occurring AudioSet classes from the SED pass), and only then run separation. For a library of discrete one-shot SFX, skip it entirely.

---

## Recommendations for `foley` — a concrete ingestion pipeline

Design goal: **progressive disclosure** — a great result with zero config, each stage independently swappable via `dol`-style stores and a strategy/DI seam. Every model here is wrapped behind a small pure function `analyze(path) -> MetadataRecord`; heavy models are lazy-loaded (`functools.cached_property`) and results are cached (`dol.cache_this`) so re-ingestion is free.

### Stage 0 — probe (always, cheap)
Load audio, read duration/sr/channels. **Branch on duration**: short (< ~20 s, the SFX common case) → skip SED/separation; long → Stage 1.

### Stage 1 — segment / separate (optional, only when needed)
- **Long recording** → **PANNs `SoundEventDetection`** [2] to cut it into time-stamped event segments; each segment then flows through Stages 2–4 as its own item (retain a `parent_file` + `span` link).
- **Layered clip detected** (multiple strong co-occurring classes) → optional **FUSS/TDCN++** [25] separation, then tag stems individually. Default **off**.

### Stage 2 — supervised AudioSet tagging (always)
- **Default: PANNs / CNN14** [2] — `pip install panns-inference`, CPU-fine, returns 527 calibrated scores + a 2048-d embedding. Keep tags above a threshold **plus** their **ontology ancestors** [1] (so "Bark" also indexes under "Dog"/"Animal").
- **Accuracy upgrade: BEATs** [7,8] when you want the best labels and can host a GitHub checkpoint (or run AST [4] via `transformers` for the middle ground with the nicest DX).
- Emit: `audioset_tags: [{label, score}]`, `audioset_embedding: float[2048]`.

### Stage 3 — zero-shot CLAP tagging (always)
- **Default: [`laion/larger_clap_general`](https://hf.co/laion/larger_clap_general)** [10] (Apache-2.0). Score the clip against **your** taxonomy (UCS / custom tags), keep top-k over threshold.
- **Store the CLAP audio embedding** (512-d) — this is the backbone of natural-language search: embed a text query at search time, nearest-neighbour against these vectors.
- Emit: `custom_tags: [{label, score}]`, `clap_embedding: float[512]`.

### Stage 4 — captioning (always, tiered)
- **Default (local, commercial-safe): EnCLAP-large** [13] (MIT) — best dedicated-captioner SPIDEr, one caption per clip.
- **Richer / promptable tier: Qwen2-Audio-7B-Instruct** [16] (Apache-2.0) when you want steerable, foley-specific prose or audio-QA fields, and have a GPU. **Audio Flamingo 3** [14] for max quality **only** on your own non-distributed library (non-commercial license).
- Emit: `caption: str`, plus a text embedding of the caption for dense retrieval.

### Stage 5 — emit metadata record
```python
@dataclass
class SoundMetadata:
    path: str
    duration_s: float
    audioset_tags: list[tuple[str, float]]      # supervised, ontology-expanded
    custom_tags: list[tuple[str, float]]        # zero-shot CLAP vs your taxonomy
    caption: str                                # natural language
    clap_embedding: list[float]                 # 512-d, for semantic search
    audioset_embedding: list[float]             # 2048-d, "sounds like this"
    events: list[dict] | None = None            # SED spans, if long
    parent_file: str | None = None              # if a segment/stem
```
Store records in a `dol` Mapping (JSON/Parquet locally, growing into a vector DB / S3 later without touching the analysis code). Index: full-text over `caption` + `*_tags`; ANN over `clap_embedding` (semantic) and `audioset_embedding` (acoustic similarity).

### Default-model summary & tradeoffs

| Stage | `foley` default | Why | Upgrade path |
|---|---|---|---|
| Supervised tag | **PANNs/CNN14** [2] | pip, CPU, embedding included, Apache-2.0 | **BEATs** [7] (SOTA) / **AST** [4] (best DX) |
| Zero-shot tag | **LAION `larger_clap_general`** [10] | custom vocab, Apache-2.0, gives search embedding | Microsoft CLAP [11] (more accurate, MS-PL) |
| Caption | **EnCLAP-large** [13] | best dedicated SPIDEr, MIT, modest GPU | **Qwen2-Audio** [16] (promptable, Apache-2.0) |
| Segment (long) | **PANNs SED** [2] | already installed, no training | BEATs-CRNN DCASE recipe [23] |
| Separate (layered) | **off** → **FUSS** [25] | rarely needed for one-shot SFX | text-guided (OmniSep/USE) [26,27] |

**Net**: three always-on models (PANNs + LAION-CLAP + EnCLAP) fit in a lean, mostly-CPU, permissively-licensed pipeline that already makes every file findable by keyword, custom tag, natural-language query, and acoustic similarity — with a clean strategy seam to swap in BEATs/Qwen2-Audio when quality demands it.

---

## REFERENCES

[1] Gemmeke JF, Ellis DPW, Freedman D, et al. *AudioSet: An ontology and human-labeled dataset for audio events.* ICASSP 2017. [research.google/pubs/pub45857](https://research.google/pubs/audio-set-an-ontology-and-human-labeled-dataset-for-audio-events/) · Ontology: [github.com/audioset/ontology](https://github.com/audioset/ontology)

[2] Kong Q, Cao Y, Iqbal T, et al. *PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition.* IEEE/ACM TASLP 2020. [arxiv.org/abs/1912.10211](https://arxiv.org/abs/1912.10211) · Code: [github.com/qiuqiangkong/audioset_tagging_cnn](https://github.com/qiuqiangkong/audioset_tagging_cnn) · Inference: [github.com/qiuqiangkong/panns_inference](https://github.com/qiuqiangkong/panns_inference)

[3] TensorFlow. *YAMNet — a pretrained audio event classifier (MobileNet-v1, 521 AudioSet classes).* [github.com/tensorflow/models/tree/master/research/audioset/yamnet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) · [tensorflow.org/hub/tutorials/yamnet](https://www.tensorflow.org/hub/tutorials/yamnet)

[4] Gong Y, Chung Y-A, Glass J. *AST: Audio Spectrogram Transformer.* Interspeech 2021. [arxiv.org/abs/2104.01778](https://arxiv.org/abs/2104.01778) · Model: [hf.co/MIT/ast-finetuned-audioset-10-10-0.4593](https://hf.co/MIT/ast-finetuned-audioset-10-10-0.4593)

[5] Chen K, Du X, Zhu B, et al. *HTS-AT: A Hierarchical Token-Semantic Audio Transformer for Sound Classification and Detection.* ICASSP 2022. [arxiv.org/abs/2202.00874](https://arxiv.org/abs/2202.00874) · Code: [github.com/RetroCirce/HTS-Audio-Transformer](https://github.com/RetroCirce/HTS-Audio-Transformer)

[6] Koutini K, Schlüter J, Eghbal-zadeh H, Widmer G. *Efficient Training of Audio Transformers with Patchout (PaSST).* Interspeech 2022. [arxiv.org/abs/2110.05069](https://arxiv.org/abs/2110.05069) · Code: [github.com/kkoutini/PaSST](https://github.com/kkoutini/PaSST)

[7] Chen S, Wu Y, Wang C, et al. *BEATs: Audio Pre-Training with Acoustic Tokenizers.* ICML 2023. [arxiv.org/abs/2212.09058](https://arxiv.org/abs/2212.09058) · Code: [github.com/microsoft/unilm/tree/master/beats](https://github.com/microsoft/unilm/tree/master/beats)

[8] Microsoft Research. *BEATs: Audio Pre-Training with Acoustic Tokenizers* (publication page, SOTA mAP 50.6 % AudioSet). [microsoft.com/en-us/research/publication/beats-audio-pre-training-with-acoustic-tokenizers](https://www.microsoft.com/en-us/research/publication/beats-audio-pre-training-with-acoustic-tokenizers/)

[9] Elizalde B, Deshmukh S, Al Ismail M, Wang H. *CLAP: Learning Audio Concepts from Natural Language Supervision.* ICASSP 2023. [arxiv.org/abs/2206.04769](https://arxiv.org/abs/2206.04769)

[10] Wu Y, Chen K, Zhang T, et al. *Large-Scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation (LAION-CLAP).* ICASSP 2023. [arxiv.org/abs/2211.06687](https://arxiv.org/abs/2211.06687) · Code: [github.com/LAION-AI/CLAP](https://github.com/LAION-AI/CLAP) · Models: [hf.co/laion/larger_clap_general](https://hf.co/laion/larger_clap_general), [hf.co/laion/clap-htsat-unfused](https://hf.co/laion/clap-htsat-unfused)

[11] Elizalde B, Deshmukh S, Wang H. *Natural Language Supervision for General-Purpose Audio Representations (Microsoft CLAP 2023).* [arxiv.org/abs/2309.05767](https://arxiv.org/abs/2309.05767) · Code: [github.com/microsoft/CLAP](https://github.com/microsoft/CLAP) · Model: [hf.co/microsoft/msclap](https://hf.co/microsoft/msclap)

[12] Deshmukh S, Elizalde B, Singh R, Wang H. *Pengi: An Audio Language Model for Audio Tasks.* NeurIPS 2023. [arxiv.org/abs/2305.11834](https://arxiv.org/abs/2305.11834) · Code: [github.com/microsoft/Pengi](https://github.com/microsoft/Pengi)

[13] Kim J, Jung J, Lee J, Woo SH. *EnCLAP: Combining Neural Audio Codec and Audio-Text Joint Embedding for Automated Audio Captioning.* ICASSP 2024. [arxiv.org/abs/2401.17690](https://arxiv.org/abs/2401.17690) · Code: [github.com/jaeyeonkim99/EnCLAP](https://github.com/jaeyeonkim99/EnCLAP)

[14] Kong Z, Goel A, Badlani R, et al. *Audio Flamingo: A Novel Audio Language Model with Few-Shot Learning and Dialogue Abilities.* ICML 2024. [arxiv.org/abs/2402.01831](https://arxiv.org/abs/2402.01831) · Model: [hf.co/nvidia/audio-flamingo](https://hf.co/nvidia/audio-flamingo)

[15] Mei X, Meng C, Liu H, et al. *WavCaps: A ChatGPT-Assisted Weakly-Labelled Audio Captioning Dataset for Audio-Language Multimodal Research.* IEEE/ACM TASLP 2024. [arxiv.org/abs/2303.17395](https://arxiv.org/abs/2303.17395) · Code: [github.com/XinhaoMei/WavCaps](https://github.com/XinhaoMei/WavCaps)

[16] Chu Y, Xu J, Yang Q, et al. *Qwen2-Audio Technical Report.* 2024. [arxiv.org/abs/2407.10759](https://arxiv.org/abs/2407.10759) · Model: [hf.co/Qwen/Qwen2-Audio-7B-Instruct](https://hf.co/Qwen/Qwen2-Audio-7B-Instruct)

[17] Tang C, Yu W, Sun G, et al. *SALMONN: Towards Generic Hearing Abilities for Large Language Models.* ICLR 2024. [arxiv.org/abs/2310.13289](https://arxiv.org/abs/2310.13289) · Code: [github.com/bytedance/SALMONN](https://github.com/bytedance/SALMONN)

[18] Goel A, Kong Z, Valle R, et al. *Audio Flamingo 3: Advancing Audio Intelligence with Fully Open Large Audio Language Models.* 2025. [arxiv.org/abs/2507.08128](https://arxiv.org/abs/2507.08128) · Model: [hf.co/nvidia/audio-flamingo-3-hf](https://hf.co/nvidia/audio-flamingo-3-hf)

[19] Kim CD, Kim B, Lee H, Kim G. *AudioCaps: Generating Captions for Audios in The Wild.* NAACL 2019. [aclanthology.org/N19-1011](https://aclanthology.org/N19-1011/) · [audiocaps.github.io](https://audiocaps.github.io/)

[20] Drossos K, Lipping S, Virtanen T. *Clotho: An Audio Captioning Dataset.* ICASSP 2020. [arxiv.org/abs/1910.09387](https://arxiv.org/abs/1910.09387)

[21] Liu S, Zhu Z, Ye N, et al. *SPIDEr: Improved Image Captioning via Policy Gradient Optimization of SPIDEr.* ICCV 2017 (metric adopted by DCASE AAC). [arxiv.org/abs/1612.00370](https://arxiv.org/abs/1612.00370) · DCASE AAC task: [dcase.community/challenge2024/task-automated-audio-captioning](https://dcase.community/challenge2024/task-automated-audio-captioning)

[22] Bilen Ç, Ferroni G, Tuveri F, et al. *A Framework for the Robust Evaluation of Sound Event Detection (PSDS).* ICASSP 2020. [arxiv.org/abs/1910.08440](https://arxiv.org/abs/1910.08440)

[23] Cornell S, Ebbers J, Douwes C, et al. *DCASE 2024 Task 4: Sound Event Detection with Heterogeneous Data and Missing Labels.* DCASE 2024 Workshop. [dcase.community/challenge2024/task-sound-event-detection-with-heterogeneous-training-datasets-and-potentially-missing-labels](https://dcase.community/challenge2024/task-sound-event-detection-with-heterogeneous-training-datasets-and-potentially-missing-labels) · [merl.com/publications/docs/TR2024-146.pdf](https://www.merl.com/publications/docs/TR2024-146.pdf)

[24] Turpault N, Serizel R, Salamon J, Shah AP. *Sound Event Detection in Domestic Environments with Weakly Labeled Data and Soundscape Synthesis (DESED).* DCASE 2019. [hal.science/hal-02160855](https://hal.science/hal-02160855) · [project.inria.fr/desed](https://project.inria.fr/desed/)

[25] Wisdom S, Tzinis E, Erdogan H, et al. *Free Universal Sound Separation (FUSS / TDCN++).* 2020. [arxiv.org/abs/2011.00803](https://arxiv.org/abs/2011.00803) · [opensource.googleblog.com/2020/04/free-universal-sound-separation.html](https://opensource.googleblog.com/2020/04/free-universal-sound-separation.html)

[26] Liu H, Wang X, et al. *OmniSep: Unified Omni-Modality Sound Separation with Query-Mixup.* 2024. [arxiv.org/abs/2410.21269](https://arxiv.org/abs/2410.21269)

[27] Nguyen T, et al. *OpenSep: Leveraging Large Language Models with Textual Inversion for Open-World Audio Separation.* 2024. [arxiv.org/abs/2409.19270](https://arxiv.org/abs/2409.19270)
