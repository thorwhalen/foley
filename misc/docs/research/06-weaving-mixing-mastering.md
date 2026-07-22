# 06 — Weaving SFX into Narration: Alignment, Timing, Mixing & Mastering

**Abstract.** This report covers foley's **WEAVE** stage — how a *chosen* sound effect is
placed under a voice so the result sounds professionally produced rather than concatenated.
It surveys forced alignment (WhisperX, Montreal Forced Aligner, `aeneas`, NeMo) to pin cues to
words and beats; the mixing craft of ducking/side-chain, gain staging, panning, distance and
reverb, crossfades and declicking; loudness mastering to EBU R128 / ITU-R BS.1770 LUFS targets
with true-peak limiting; the placement/looping differences between one-shots, ambience beds and
stingers; and a proposed **editable, re-renderable sound-design timeline** (an EDL for a
narration's SFX layer). It closes with a concrete default render/mix pipeline and a timeline
data model for foley, dovetailing with the "soundscape plan" that the SELECT-stage agent already
emits (`place_in_timeline` → `TimelineItem` of `onset · gain · layer · loop`; see report 05).

---

## 1. Where WEAVE sits in the pipeline

The SELECT stage (report 05) ends by emitting a **soundscape plan**: an ordered list of
`TimelineItem`s, each a chosen clip with an `onset`, a `gain`, a `layer`
(foreground vs ambience bed), and a `loop` flag [ref: report 05 §5.2]. WEAVE consumes that plan
plus the **narration audio** and produces a finished mix. It does four things concatenation does
not:

1. **Align** — convert the plan's abstract onsets ("at the word *door*", "when the storm scene
   begins") into exact sample positions, using forced alignment of the narration to its
   transcript.
2. **Mix** — set each sound's level *relative to the voice*, duck beds under speech, place sounds
   in the stereo field and at a plausible distance, and glue edits with fades so there are no
   clicks.
3. **Master** — normalise the whole program to a platform loudness target with true-peak-safe
   limiting.
4. **Persist** — keep the whole thing as an **editable timeline** so the SFX layer can be nudged,
   swapped and re-rendered — never baked into a single opaque file.

The design principle throughout: **the render is a pure function of (narration, timeline,
library, master profile)**. Nothing is destructive; every knob is data.

---

## 2. Timing & placement — forced alignment

### 2.1 Why forced alignment

An onset like "fire the door-creak *as the word 'door' is spoken*" is only meaningful if we know
*when* the word "door" occurs in the narration audio. **Forced alignment** takes an audio file and
its known transcript and returns start/end timestamps for every word (and often every phoneme).
This is a much easier and more accurate problem than open ASR because the words are given — the
aligner only has to place them in time [1,3].

Vanilla Whisper emits only utterance-level timestamps that can be off by seconds; word-level
alignment tightens this to tens of milliseconds [1].

### 2.2 The options

| Tool | Method | Granularity / accuracy | Deps & footprint | License | Best for |
|---|---|---|---|---|---|
| **WhisperX** [1,2] | faster-whisper ASR → **wav2vec2 CTC phoneme forced alignment** → (opt.) pyannote diarization | word-level, **≈±50 ms** vs Whisper's ±500 ms [1] | PyTorch + a CTC model per language; GPU-friendly, CPU-ok | BSD-4 (code); models vary | **foley default** — you get transcription *and* alignment in one pass |
| **Montreal Forced Aligner (MFA)** [3,4] | Kaldi HMM-GMM acoustic models + pronunciation dictionary | word **and phone** level; **most accurate** in 2026 benchmarks — HMM-GMM still beats neural aligners [3] | conda/Kaldi install; needs a dictionary + language model | MIT | highest-precision / phoneme work; batch offline |
| **`aeneas`** [5,6] | Synthesize the transcript with TTS, then **DTW-align MFCCs** (Sakoe-Chiba band) of real vs synth audio | fragment-level (sentence/line), not per-phoneme | Python/C + espeak TTS + ffmpeg; light | GNU AGPL/LGPL | audiobook/caption sync where you only need line-level anchors; no ML model download |
| **NeMo Forced Aligner (NFA)** [7] | NeMo CTC ASR model, Viterbi over emissions | token/word/segment level, multilingual | NVIDIA NeMo (heavy); GPU | Apache-2.0 | already-in-NeMo shops; multilingual at scale |
| whisper-timestamped / stable-ts | cross-attention or DTW on Whisper itself | word-level, no second model | just Whisper | MIT | lightest add-on when a wav2vec2 model per language is unwanted |

**Takeaway.** WhisperX is the pragmatic default: one dependency chain gives foley both the
transcript (if not supplied) *and* the word timestamps, at ≈±50 ms — well inside the perceptual
tolerance for SFX sync [1,2]. Offer MFA as an opt-in "high-precision" aligner and `aeneas` as a
zero-ML-download fallback for line-level anchoring [3,4,5].

### 2.3 Alignment code sketch (WhisperX)

```python
import whisperx

def word_timeline(audio_path, *, device="cpu", language="en"):
    """Return [{'word','start','end'}, ...] for a narration file."""
    model = whisperx.load_model("small", device, language=language)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16)
    align_model, meta = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(result["segments"], align_model, meta, audio, device)
    return [w for seg in aligned["segments"] for w in seg["words"]]  # word-level cues
```

### 2.4 Anchoring heuristics — from "which word" to "which sample"

Word timestamps are the raw material; foley needs rules that turn a decomposed sound event into a
concrete trigger time. Recommended anchors, cheapest first:

- **Word anchor (impact/one-shot).** A discrete diegetic event ("she *knocked*") fires on the
  onset of its trigger word. Match the event's `query`/keyword to the nearest transcript word
  (fuzzy/lemmatised match), take that word's `start`.
- **Pre-roll for anticipatory cues.** Some sounds must *precede* the word to feel causal (a
  whoosh landing on an impact, a door starting to creak before "door"). Subtract a lead time
  (typ. 100–400 ms) so the sound's *salient transient* — not its file start — lands on the word.
  This is a per-event `pre_roll`/`sync_point` offset.
- **Phrase / sentence span (beds & processes).** Continuous events (rain, room tone) anchor to a
  **span**: start at the first word of the sentence/scene, end at the last, from sentence
  boundaries in the aligned transcript (punctuation + inter-word gaps > ~350 ms as a segmenter).
- **Scene / paragraph boundary (ambience swaps, stingers).** A change of location or chapter is a
  paragraph break in the source text; map it to the timestamp of the paragraph's first spoken
  word. Ambience beds crossfade across this boundary; a stinger can punctuate it.
- **Silence/pause snapping.** Snap onsets to the nearest inter-word pause when a sound would
  otherwise collide with a stressed syllable; this keeps speech intelligible and avoids masking.

These heuristics are pure functions from `(SoundEvent, WordTimeline) → onset_seconds`, so they
live in a small `weave/anchor.py` and are independently testable.

---

## 3. Mixing — making the sound sit under the voice

Mixing is where "a sound plays at time *t*" becomes "a sound belongs in this scene". Six concerns.

### 3.1 Gain staging & dialogue-relative levels

The voice is the **anchor**; everything else is set *relative to it*. Practically: normalise the
narration bus to a working level, then place SFX beneath it. Common starting points (to be exposed
as defaults, not magic constants):

- Foreground one-shots: **−6 to −12 dB** below the voice's short-term level.
- Ambience beds: **−18 to −24 dB** below the voice (present but subliminal) [22, ref: report 05].
- Non-diegetic mood/music beds: duck hard under speech (see §3.2).

Gain staging = keeping every stage in its optimal range to avoid noise/distortion [19]; foley
should track per-item gain in dB and apply it *before* the master limiter, leaving headroom.

### 3.2 Ducking / side-chain compression

**Ducking** attenuates a background element whenever the voice is active, so speech stays
intelligible [8, 20]. Two implementation routes:

**(a) FFmpeg `sidechaincompress`** — a compressor whose *detector* is a second stream (the
voice), applied to the bed [8]:

```bash
ffmpeg -i narration.wav -i bed.wav -filter_complex "\
  [0:a]asplit=2[voice][key];\
  [1:a][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[ducked];\
  [voice][ducked]amix=inputs=2:duration=longest:normalize=0" out.wav
```

Here the voice keys the compressor: while the narrator speaks, the bed drops (attack 20 ms,
release 300 ms) then recovers in the gaps. Typical ducking depth is **~8–12 dB** [20]. Duck E/M
(effects/music) beds; leave foreground diegetic hits mostly un-ducked so they retain impact — but
still keep them below the voice.

**(b) Envelope-follower ducking in Python** (no per-clip DAW), which foley can do directly on the
narration's word timeline: build a gain automation curve that dips the bed during speech spans and
lifts it in pauses, then apply it sample-wise. This is deterministic, testable, and needs no
external key routing:

```python
import numpy as np

def speech_duck_gain(n_samples, sr, speech_spans, *, duck_db=-10.0,
                     attack=0.02, release=0.3):
    """Gain envelope (linear) that dips to duck_db during speech spans."""
    g = np.ones(n_samples, dtype=np.float32)
    duck = 10 ** (duck_db / 20)
    for start, end in speech_spans:            # from the word timeline
        a, b = int(start * sr), int(end * sr)
        g[a:b] = duck
    # one-pole smoothing to make attack/release clickless
    ca, cr = np.exp(-1/(attack*sr)), np.exp(-1/(release*sr))
    out = np.empty_like(g); acc = 1.0
    for i, target in enumerate(g):
        coef = ca if target < acc else cr
        acc = target + coef * (acc - target); out[i] = acc
    return out
```

### 3.3 Stereo panning (constant-power)

To place a sound left/right, use a **constant-power (equal-power) pan** so perceived loudness
stays flat across the field: `L = cos(θ)`, `R = sin(θ)` with `θ = (pan+1)·π/4`, `pan ∈ [−1, 1]`.
Linear panning dips ~3 dB in the centre; constant-power keeps `L² + R²` constant [15]. Keep the
narration centred; pan SFX modestly (diegetic position, e.g. a door to the left) but avoid hard
pans that pull attention off the voice.

### 3.4 Distance cues

Distance is not just "quieter" — it is a *combination* of cues the ear reads together:

- **Attenuation** (roughly inverse-distance; ~−6 dB per doubling of distance).
- **Low-pass filtering** (air absorbs highs → distant sounds are duller).
- **More reverb, less direct** (the *wet/dry ratio* rises with distance).

foley can expose a single `distance` (or `proximity` ∈ near/mid/far) that maps to a gain +
LPF-cutoff + reverb-send triple, so the agent's high-level intent ("distant thunder") becomes a
concrete DSP recipe.

### 3.5 Reverb / room — placing a sound in a scene

To make a dry library clip sound like it belongs in the narrated space, convolve it with a **room
impulse response (RIR)**. **`pyroomacoustics`** (LCAV) generates RIRs from a shoebox/polyhedral
room via the image-source model and convolves sources with them [18]:

```python
import pyroomacoustics as pra, numpy as np
room = pra.ShoeBox([6, 5, 3], fs=sr, materials=pra.Material(0.4), max_order=12)
room.add_source([1.5, 4.0, 1.2], signal=clip)     # place the SFX in the room
room.add_microphone([3.0, 1.0, 1.6])              # listener position
room.simulate()
wet = room.mic_array.signals[0]                    # clip, now "in the room"
```

Alternatively, convolve against a **recorded IR** (church, hall, forest) with
`scipy.signal.fftconvolve`. A single shared reverb *send* per scene (rather than per clip) both
saves compute and glues the scene together. Keep a **dry/wet** control per item.

### 3.6 Crossfades, fades & declicking

Cutting or looping audio at a non-zero sample produces a step discontinuity the speaker
reproduces as a **click** [16]. Two defences, both cheap and mandatory:

- **Zero-crossing / short fades.** Snap edit points to zero crossings, or apply a very short
  fade-in/out (a few ms) at every clip boundary — enough to remove the click, too short to hear
  [16, 17].
- **Equal-power crossfades** where two sounds overlap (e.g. looping a bed, swapping ambiences).
  A linear ("equal-gain") crossfade dips ~3 dB at the midpoint; an **equal-power** crossfade
  (`gain_out = cos(t·π/2)`, `gain_in = sin(t·π/2)`) holds perceived loudness constant [15].

Every clip placed on the timeline should therefore carry a `fade_in`/`fade_out` (default ~5–10 ms)
and every loop/overlap should use an equal-power crossfade of a few tens of ms.

---

## 4. Sound types — one-shots vs beds vs stingers

The plan's `layer`/`loop` fields already distinguish these; WEAVE treats them differently:

| Type | Role | Placement | Duration/looping | Level | Fades |
|---|---|---|---|---|---|
| **One-shot** (impact/hit) | discrete diegetic event: knock, door creak, glass smash | **word-anchored** on its trigger (with `pre_roll` for anticipatory transients) | single play; no loop | −6…−12 dB under voice | short in/out to declick |
| **Ambience bed** | continuous scene texture: rain, forest, room tone | **span-anchored** across a sentence/scene; **ducked** under speech | **seamless loop** if shorter than the span | −18…−24 dB under voice | long equal-power crossfade at loop point and at scene boundaries |
| **Stinger / transition** | non-diegetic punctuation: chapter sting, whoosh between scenes | **boundary-anchored** on a paragraph/scene change or reveal | single play; may tail into the next bed | prominent but < voice; often ducks the bed | fade to taste; can crossfade into next scene |

**Seamless looping** (beds): choose loop points at matching zero crossings on low-feature
material, apply tiny edge fades, and crossfade the seam; the loop must "give a sense of place
without features that reveal it is repeating" [17]. foley should either (a) require pre-looped bed
assets or (b) auto-generate a seamless loop by crossfading the tail back over the head.

---

## 5. Mastering / loudness

### 5.1 LUFS, R128 and BS.1770 in one paragraph

Perceived loudness is measured in **LUFS** (Loudness Units Full Scale) per **ITU-R BS.1770**,
which K-weights the signal and gates out silence: an **absolute gate** at −70 LUFS and a
**relative gate** 10 LU below the ungated mean, so quiet passages don't drag the number down
[10, 11]. **EBU R128** wraps BS.1770 into a delivery spec: target **−23 LUFS** (±0.5 LU),
max true peak **−1 dBTP**, with **LRA** (loudness range) and momentary/short-term meters
[11]. **EBU R128 s2** (Nov 2023) adapts this for streaming/on-demand [11]. **`Integrated
loudness`** is the single whole-program number foley normalises to.

### 5.2 Platform targets (2024–2026)

| Destination | Integrated target | True peak | Source |
|---|---|---|---|
| **Podcast / spoken web (foley default)** | **−16 LUFS** (±1) | **−1 dBTP** | Apple Podcasts; AES web-content rec [12,13,14] |
| Spotify / YouTube / most streaming | **−14 LUFS** | −1 dBTP | platform normalisation [13,14] |
| AES streaming recommendation (TD1008) | **−16 to −20 LUFS** window | −1 dBTP | AES TD1008 [12] |
| EBU broadcast (R128) | **−23 LUFS** (±0.5) | **−1 dBTP** | EBU R128 [11] |
| ATSC A/85 (US broadcast) | **−24 LKFS** | −2 dBTP | ATSC / [10] |

**Recommendation for foley:** default to **−16 LUFS, −1 dBTP** (the single master that is not
penalised anywhere and is the dominant spoken-word norm), and expose a `master_profile` enum
(`podcast=-16`, `streaming=-14`, `broadcast_ebu=-23`, `broadcast_atsc=-24`) so the target is data,
not code [12,13,14].

### 5.3 True-peak limiting

Sample-peak meters miss **inter-sample peaks**: reconstructed analog/lossy waveforms can exceed
the highest sample by up to ~3 dB, causing clipping after D/A or MP3/AAC encode [22, 23]. A
**true-peak limiter** oversamples (≥4×) to detect these and holds the ceiling at, e.g., −1 dBTP
[22]. `ffmpeg loudnorm` performs true-peak-aware normalisation to its `TP` target; a dedicated
brickwall (`ffmpeg alimiter`, or a mastering limiter) can be chained if more control is wanted.

### 5.4 Tooling

- **`pyloudnorm`** (Steinmetz & Reiss, AES 2021) — pure-Python **ITU-R BS.1770-4** meter; measure
  integrated loudness and normalise. Ideal for foley's in-process path (no shell-out) [9]:

  ```python
  import pyloudnorm as pyln, soundfile as sf
  data, rate = sf.read("mix.wav")
  meter = pyln.Meter(rate)                          # BS.1770-4
  loudness = meter.integrated_loudness(data)        # e.g. -21.3 LUFS
  norm = pyln.normalize.loudness(data, loudness, -16.0)   # → -16 LUFS
  ```

  (Note: pyloudnorm measures loudness and normalises by a single gain; it does **not** itself do
  true-peak limiting — pair it with a limiter or clamp/`ffmpeg loudnorm` for the ceiling [9].)

- **`ffmpeg loudnorm`** — EBU R128 normaliser with defaults **I=−24, TP=−2, LRA=7** (I range
  −70…−5) [ffmpeg loudnorm doc]. Use **two-pass** for accuracy: pass 1 measures
  `input_i/input_tp/input_lra/input_thresh`; pass 2 feeds them back as `measured_*` so it can
  normalise linearly instead of dynamically compressing [ref: two-pass loudnorm]:

  ```bash
  # pass 1: measure
  ffmpeg -i mix.wav -af loudnorm=I=-16:TP=-1:LRA=11:print_format=json -f null -
  # pass 2: apply with measured values
  ffmpeg -i mix.wav -af loudnorm=I=-16:TP=-1:LRA=11:\
  measured_I=-21.3:measured_TP=-6.4:measured_LRA=9.1:measured_thresh=-31.6:\
  linear=true:print_format=summary out.wav
  ```

- **`pydub`** — high-level clip ops (`overlay(seg, position=ms)`, `apply_gain(db)`, `fade_in`,
  `fade_out`, loop) — convenient for assembling the SFX bus, though `overlay` is pure-Python and
  slow at scale [20].
- **`sox` / `ffmpeg adelay` / `amix`** — placement (`adelay` shifts a clip to its onset), summing
  (`amix` with per-input `weights`), and batch DSP; good for the final render graph.

---

## 6. The render model — an editable sound-design timeline (EDL)

### 6.1 Requirements

The design target (design.md §4) is **not a one-shot bake** but an **editable, re-renderable**
representation — conceptually like cosmograph "snapshots/stories" applied to a narration's SFX
layer. Requirements:

1. **Non-destructive** — store *decisions* (which clip, when, how loud, how processed) as data
   and reference source media by id; never mutate source audio [21, OTIO model].
2. **Re-renderable** — `render(timeline) → audio` is a pure, deterministic function; re-running
   after an edit reproduces the change and nothing else.
3. **Serialisable & diffable** — JSON (Zod/pydantic-validated), so a timeline can be saved,
   versioned, hand-edited, LLM-edited, and round-tripped through the MCP tools.
4. **Layered / multi-track** — separate tracks for voice, foreground SFX, ambience beds,
   stingers, and (later) music, each with its own bus processing.
5. **Anchor-preserving** — items store their *symbolic* anchor (word/sentence/scene) **and** the
   resolved time, so re-aligning a re-recorded narration re-flows the SFX automatically.

### 6.2 Prior art

- **OpenTimelineIO (OTIO)** — the Academy Software Foundation's editorial interchange: a modern
  EDL that stores order/length of clips and *references* to external media (non-destructive), with
  adapters to CMX3600 EDL, AAF, FCPXML, etc. [21]. foley's model is a small, audio-only,
  SFX-flavoured cousin of OTIO; exporting to OTIO/EDL is a natural future adapter.
- **CMX3600 EDL / AAF** — legacy but ubiquitous; limited track counts [21].
- **DAW session files** (Reaper `.rpp`, Ableton) — full-fidelity but tool-specific.

foley should define its **own compact JSON schema** (below) as the SSOT and treat OTIO/EDL/DAW
formats as *export adapters*, exactly as the source/index layers treat backends as adapters.

### 6.3 Proposed `SoundDesignTimeline` schema

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

Anchor = Literal["absolute", "word", "sentence", "scene", "paragraph"]
Layer  = Literal["voice", "sfx_fg", "ambience", "stinger", "music"]

@dataclass
class Placement:
    """WHERE/WHEN a clip sits — symbolic anchor + resolved time."""
    anchor: Anchor = "absolute"
    ref: Optional[str] = None      # e.g. transcript word / sentence id / scene id
    onset: float = 0.0             # resolved start (s); filled by the aligner
    pre_roll: float = 0.0          # shift so the clip's transient lands on the anchor
    duration: Optional[float] = None   # None = full clip length
    loop: bool = False             # seamless-loop to fill `duration` (beds)

@dataclass
class Processing:
    """HOW a clip sounds — all optional, sensible defaults."""
    gain_db: float = 0.0           # relative to the voice bus
    pan: float = 0.0               # -1 (L) .. +1 (R), constant-power
    distance: float = 0.0          # 0 near .. 1 far → gain+LPF+reverb recipe
    reverb_send: float = 0.0       # 0 dry .. 1 wet (scene bus)
    fade_in: float = 0.008         # s, declick
    fade_out: float = 0.012        # s, declick
    duck_bed: bool = False         # does this item duck the ambience bus?

@dataclass
class TimelineItem:
    id: str
    clip_ref: str                  # SoundRecord id in the dol library (by reference!)
    layer: Layer = "sfx_fg"
    placement: Placement = field(default_factory=Placement)
    processing: Processing = field(default_factory=Processing)
    event: Optional[dict] = None   # provenance: the SoundEvent from decompose_context
    enabled: bool = True           # non-destructive mute

@dataclass
class MasterProfile:
    target_lufs: float = -16.0     # podcast default
    true_peak_db: float = -1.0
    lra: float = 11.0

@dataclass
class SoundDesignTimeline:
    narration_ref: str             # the voice audio (dol ref)
    transcript: Optional[str] = None
    word_timeline: list = field(default_factory=list)   # from forced alignment
    items: list = field(default_factory=list)           # list[TimelineItem]
    master: MasterProfile = field(default_factory=MasterProfile)
    schema_version: int = 1
```

This is a superset of the SELECT stage's `TimelineItem` (`onset · gain · layer · loop`): the
agent emits the sparse plan; WEAVE *resolves* anchors to times, fills processing defaults, and the
render function reads the whole thing. Because items reference clips **by id** into the `dol`
library, the timeline stays tiny and diffable.

### 6.4 Render function (sketch)

```python
def render(tl: SoundDesignTimeline, library, *, sr=48_000):
    voice = load(library[tl.narration_ref], sr)
    if not tl.word_timeline:
        tl.word_timeline = word_timeline_from(voice, tl.transcript)   # §2
    buses = {layer: silence(len(voice), sr) for layer in LAYERS}
    for item in tl.items:
        if not item.enabled:
            continue
        onset = resolve_anchor(item.placement, tl.word_timeline)      # §2.4
        clip  = load(library[item.clip_ref], sr)
        clip  = fit_duration(clip, item.placement, sr)                # loop/trim + xfade
        clip  = apply_processing(clip, item.processing, sr)           # gain/pan/dist/reverb/fades
        buses[item.layer] = overlay(buses[item.layer], clip, onset)
    buses["ambience"] = duck(buses["ambience"], voice, tl.word_timeline)  # §3.2
    mix = sum_buses(voice_bus(voice), buses)                          # gain-staged sum
    return master(mix, tl.master, sr)                                 # §5: LUFS + true-peak
```

Every stage is a pure function of data + library; editing any field and re-calling `render`
reproduces exactly that change.

---

## 7. Recommendations for `foley`

### 7.1 Default render/mix pipeline (ordered)

1. **Align.** `whisperx` → word timeline (≈±50 ms) [1,2]; cache it on the timeline so re-renders
   skip re-alignment. `aeneas` fallback for no-ML-download / line-level; MFA opt-in for
   high-precision [3,4,5].
2. **Resolve anchors.** Turn each item's symbolic anchor (word/sentence/scene) + `pre_roll` into a
   sample onset (§2.4) — pure functions, unit-tested.
3. **Fit duration.** One-shots play once; beds seamless-loop to fill their span with equal-power
   crossfades at the seam; snap edits to zero crossings + short declick fades [16,17].
4. **Per-item processing.** Constant-power pan [15]; distance → gain+LPF+reverb-send; optional
   `pyroomacoustics`/IR convolution per scene bus [18]; apply `gain_db` relative to voice.
5. **Bus sum + ducking.** Sum voice + sfx_fg + ambience + stinger buses with gain staging [19];
   **duck the ambience/music bus under speech** via envelope-follower (§3.2) [19] or `ffmpeg
   sidechaincompress` (~8–12 dB, attack ~20 ms, release ~300 ms) [8,20].
6. **Master.** Normalise integrated loudness to the `MasterProfile` target with true-peak-safe
   limiting: **`pyloudnorm` measure + normalise in-process** [9], then a true-peak limiter / or a
   final **two-pass `ffmpeg loudnorm`** to guarantee I and TP (default **−16 LUFS / −1 dBTP** for
   podcast) [9,12,13,22].
7. **Persist, don't bake.** Save the `SoundDesignTimeline` JSON alongside the rendered audio so
   the SFX layer is re-editable; expose `render`, `place`, `nudge`, `swap_clip`, `set_master`,
   `re_align` as MCP tools (same façade-to-MCP path as SELECT).

### 7.2 Module layout (fits design.md `weave/`)

```
foley/weave/
    align.py      # forced alignment adapters (whisperx default; aeneas/mfa/nemo opt-in)
    anchor.py     # symbolic-anchor → onset heuristics (pure fns)
    mix.py        # gain, constant-power pan, distance, reverb send, ducking, crossfade/declick
    master.py     # LUFS normalise (pyloudnorm) + true-peak limit; MasterProfile targets
    timeline.py   # SoundDesignTimeline / TimelineItem schemas (Zod/pydantic-validated)
    render.py     # render(timeline, library) -> audio ; export adapters (OTIO/EDL)
```

### 7.3 Optional-extras plan (mirrors design.md)

`foley[align]` (whisperx / torch), `foley[align-mfa]`, `foley[align-aeneas]`,
`foley[mix]` (numpy/scipy/pyroomacoustics), `foley[master]` (pyloudnorm; ffmpeg is a *system* dep
surfaced via `check_requirements`). The zero-dep core keeps only the timeline schema + a pure
`render` skeleton that no-ops gracefully when DSP extras are absent (progressive disclosure).

### 7.4 Open questions (for design.md)

- **DSP in-process vs shell-out.** `pyloudnorm`/`numpy` keep everything in Python (testable,
  portable); `ffmpeg loudnorm`/`sidechaincompress` are battle-tested but add a system dep. Propose
  **in-process for mix + measure, ffmpeg two-pass as the optional "guarantee the numbers" master
  path** — pick per `check_requirements`.
- **Anchor robustness.** Fuzzy word-matching when the SFX keyword isn't a transcript word (map
  event `query` → nearest concept in the sentence); needs a small evaluation set (Prompt 11).
- **Timeline ↔ OTIO.** Ship foley JSON as SSOT now; add an OTIO/EDL export adapter later for DAW
  round-tripping [21].
- **Re-render triggers.** Cache alignment + measured loudness; invalidate only the buses touched
  by an edit (incremental render) for interactive authoring (Prompt 12).

---

## REFERENCES

1. Bain M, Huh J, Han T, Zisserman A. *WhisperX: Time-Accurate Speech Transcription of Long-Form
   Audio* (Interspeech 2023). [ora.ox.ac.uk](https://ora.ox.ac.uk/objects/uuid:fece4192-95b7-4db8-a018-3cf728040194/files/swm117q47j)
2. m-bain/whisperX — *Automatic Speech Recognition with Word-level Timestamps & Diarization*
   (GitHub, accessed 2026-07). [github.com/m-bain/whisperX](https://github.com/m-bain/whisperX)
3. *Montreal Forced Aligner and the state of speech-to-text alignment in 2026* (arXiv 2606.18466).
   [arxiv.org](https://arxiv.org/html/2606.18466v1)
4. *Montreal Forced Aligner — User Guide* (v3.x documentation, accessed 2026-07).
   [montreal-forced-aligner.readthedocs.io](https://montreal-forced-aligner.readthedocs.io/en/latest/user_guide/index.html)
5. *aeneas — automagically synchronize audio and text* (ReadBeyond, v1.7.3).
   [readbeyond.it/aeneas](https://www.readbeyond.it/aeneas/)
6. *aeneas — HOW IT WORKS* (DTW over MFCCs of real vs TTS-synthesized audio).
   [github.com/readbeyond/aeneas](https://github.com/readbeyond/aeneas/blob/master/wiki/HOWITWORKS.md)
7. NVIDIA NeMo — *Forced Alignment (NFA)* (discussion / docs, accessed 2026-07).
   [github.com/NVIDIA-NeMo/NeMo](https://github.com/NVIDIA-NeMo/NeMo/discussions/2657)
8. *sidechaincompress — FFmpeg Filters* (Audio) documentation (FFmpeg 8.0).
   [ayosec.github.io/ffmpeg-filters-docs](https://ayosec.github.io/ffmpeg-filters-docs/8.0/Filters/Audio/sidechaincompress.html)
9. Steinmetz C, Reiss J. *pyloudnorm: A simple yet flexible loudness meter in Python* (AES 2021);
   implements ITU-R BS.1770-4. [github.com/csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) ·
   [preprint](https://csteinmetz1.github.io/pyloudnorm-eval/paper/pyloudnorm_preprint.pdf)
10. *Loudness normalization: EBU R128, ITU-R BS.1770, ATSC A/85* (Forasoft, accessed 2026-07).
    [forasoft.com](https://www.forasoft.com/learn/audio-for-video/articles-audio/loudness-normalization-ebu-r128-bs1770-atsc-a85)
11. EBU Technology & Innovation — *Loudness (R128, R128 s2 streaming, Nov 2023)*.
    [tech.ebu.ch/loudness](https://tech.ebu.ch/loudness)
12. AES — *Technical Document AESTD1008 (v3.13): Recommendations for Loudness of Internet Audio
    Streaming and On-Demand Distribution* (2021/2024). [aes2.org PDF](https://aes2.org/wp-content/uploads/2024/01/20210924_TD1008_v3.13.pdf)
13. *LUFS Standards for Podcast, Video & Broadcast* (Josh Vamos, accessed 2026-07); Apple Podcasts
    −16 LUFS/−1 dBTP, Spotify/YouTube −14 LUFS. [joshvamos.com](https://www.joshvamos.com/lufs-standards/)
14. *Loudness (LUFS) — Podcasting Articles* (Audio Audit, accessed 2026-07).
    [audioaudit.io](https://audioaudit.io/articles/podcast/loudness-lufs)
15. *Implementing a Constant Power Crossfade* (Teed, 2019); Audacity Manual — *Fade and Crossfade*.
    [teedteed.wordpress.com](https://teedteed.wordpress.com/2019/05/06/implementing-a-constant-power-crossfade/) ·
    [manual.audacityteam.org](https://manual.audacityteam.org/man/fade_and_crossfade.html)
16. Audacity Manual / Cockos forum — *zero-crossing edits and clicks*.
    [manual.audacityteam.org](https://manual.audacityteam.org/man/fade_and_crossfade.html)
17. *Looping Audio Seamlessly* (Creator Sounds Pro) · *How to Seamlessly Loop Any Ambience*
    (Frontier SoundFX) · ZapSplat looping guide (accessed 2026-07).
    [creatorsoundspro.com](https://creatorsoundspro.com/looping-audio-seamlessly-a-practical-guide-for-game-developers-video-editors/) ·
    [frontiersoundfx.com](https://www.frontiersoundfx.com/how-to-seamlessly-loop-any-ambience-audio-file/)
18. Scheibler R, Bezzam E, Dokmanić I. *Pyroomacoustics: A Python Package for Audio Room Simulation
    and Array Processing* (2018); image-source RIR + convolution.
    [pypi.org/project/pyroomacoustics](https://pypi.org/project/pyroomacoustics/) ·
    [readthedocs](https://pyroomacoustics.readthedocs.io/en/pypi-release/pyroomacoustics.room.html)
19. *Dialogue Mixing and Processing for Clarity* (Fiveable — Sound Design notes, accessed 2026-07).
    [fiveable.me](https://fiveable.me/sound-design/unit-8/dialogue-mixing-processing-clarity/study-guide/nSoJGnAWJBITslMR)
20. jiaaro/pydub — *API* (`overlay(position=)`, `apply_gain`, `fade_in/out`, loop); ducking
    reference values ~10 dB. [github.com/jiaaro/pydub](https://github.com/jiaaro/pydub/blob/master/API.markdown)
21. AcademySoftwareFoundation/OpenTimelineIO — *editorial interchange / modern EDL*
    (v0.18, docs accessed 2026-07). [opentimelineio.readthedocs.io](https://opentimelineio.readthedocs.io/en/stable/) ·
    [PyPI](https://pypi.org/project/OpenTimelineIO/)
22. iZotope — *What Is a True Peak Limiter?* · FabFilter Pro-L 2 — *True peak limiting*
    (oversampling, inter-sample peaks, dBTP). [izotope.com](https://www.izotope.com/en/learn/true-peak-limiter) ·
    [fabfilter.com](https://www.fabfilter.com/help/pro-l/using/truepeaklimiting)
23. *Two-pass loudness normalization with FFmpeg loudnorm (the right way)* (DEV, accessed 2026-07);
    `loudnorm` two-pass `measured_*` workflow; FFmpeg `loudnorm` filter docs (defaults I=−24, TP=−2,
    LRA=7). [dev.to](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3) ·
    [ffmpeg loudnorm doc](https://ayosec.github.io/ffmpeg-filters-docs/8.0/Filters/Audio/loudnorm.html)
24. *How to Incorporate Sound Effects into Audiobooks* (Spines) · *Sound effects in audiobooks*
    (NarratorsRoadmap) — placement sparingly at scene/chapter boundaries, below voice
    (accessed 2026-07). [spines.com](https://spines.com/how-to-incorporate-sound-effects-into-audiobooks/) ·
    [narratorsroadmap.com](https://www.narratorsroadmap.com/sound-effects-in-audiobooks/)
</content>
</invoke>
