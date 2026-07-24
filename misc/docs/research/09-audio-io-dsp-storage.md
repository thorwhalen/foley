# Audio I/O, Formats, DSP Fundamentals & Storage — the Foundation Layer

*Research brief for **foley** — the retrieval-first SFX facade. Focus: the
load-bearing foundation under SOURCE → INDEX → SELECT → WEAVE. What audio
**format** the library works in, which Python libraries **decode/encode/transform**
it, the DSP primitives every other layer calls, and how to hold audio **bytes**
behind a `dol` `Mapping` so a local folder swaps to S3/blob with no business-logic
change.*

*Compiled 2026-07. Versions and dates are noted inline; re-check library
changelogs before pinning — this landscape (soundfile MP3 support, torchaudio's
TorchCodec migration, `audioop` removal in Python 3.13) has moved fast.*

---

## Abstract

Every foley layer stands on this one: CLAP embedding wants **48 kHz mono float**
[report 04]; tagging/segmentation want decoded arrays; generation and weaving want
loud-normalized, trimmed, correctly-sampled clips; and the library must *store*
thousands of these cheaply and *swap local→cloud* with no code change. This brief
recommends a two-representation model that mirrors the FLAC-vs-WAV split every
studio already uses [1]: **archive at rest as FLAC** (lossless, 40–60 % smaller
than WAV [1], rich metadata, one canonical container) and **work in memory as a
`float32` NumPy array at 48 kHz** (the lingua franca of every Python audio library
and the exact input CLAP expects). Delivery/preview is a *third*, derived
representation — **Opus** (royalty-free, transparent near 128 kbps, 64 kbps Opus ≈
128 kbps MP3 [2]) for streamed previews, MP3 only for legacy reach (patent-free
since 2017 [3]).

For I/O the recommendation is **`soundfile`** (libsndfile) as the default
read/write engine for WAV/FLAC/OGG — fast, C-backed, streams via `blocks()`,
writes to `BytesIO` [4] — with **`librosa`** for high-level DSP, **`soxr`** for
resampling (librosa's own default backend [5][6]), **`pyloudnorm`** for
BS.1770-4/EBU-R128 loudness [7], and **`ffmpeg`** treated as an *optional external
tool* (not a bundled dependency) for MP3/AAC/Opus transcode — because FFmpeg's
licensing (LGPL/GPL + patent-encumbered codecs) [8] must never be inherited by a
`pip install foley`. `pydub` and `torchaudio` are explicitly **not** load-bearing:
`pydub` depends on the stdlib `audioop` module removed in Python 3.13 [9][10], and
`torchaudio` entered maintenance/deprecation in 2.8→2.9, folding decode/encode into
TorchCodec [11].

Storage follows the `dol` doctrine already set in report 04: audio **bytes live
behind a `Mapping[key → bytes]`** that is `dol.Files` locally and an S3 store in
the cloud, **content-addressed** by a hash key for automatic de-duplication and
immutability, and **kept separate from the lightweight metadata/index** so heavy
blobs and small records scale independently. Whether a sound is stored
**by-value** (bytes cached) or **by-reference** (URI + provenance only) is a
**per-source license decision**: CC0 audio may be cached freely, but Freesound's
API terms forbid "full copies of the database" and require intermediate copies be
"deleted when they are no longer required" [12] — so the `LicenseRecord` gates the
blob store.

---

## 1. Formats & Codecs — storage vs delivery vs working

### 1.1 The three roles a format plays

A sound-effects library needs a format for **three distinct jobs**, and the mistake
is using one format for all three:

| Role | What it must optimize | Recommended |
|---|---|---|
| **Working** (in RAM, between DSP ops) | zero loss, direct math, library-universal | `float32` NumPy array @ 48 kHz (not a file format at all) |
| **Archive / storage** (bytes at rest) | lossless, small, metadata-rich, one container | **FLAC** |
| **Delivery / preview** (streamed to a client) | small at transparent quality, royalty-free | **Opus** (fallback MP3) |

### 1.2 Uncompressed & lossless — WAV, FLAC

- **WAV** — uncompressed PCM. Universal, zero encode/decode overhead, the studio
  working-file standard [1]; but **large** (a 3-min CD-quality track ≈ 30 MB [1])
  and **near-zero metadata** (RIFF `INFO`/BWF chunks are minimal and poorly
  supported [1]). Good as an *interchange* format, poor as a *library archive*.
- **FLAC** — Free Lossless Audio Codec. **Bit-identical** to WAV on decode [1] but
  **40–60 % smaller** [1]; supports Vorbis-comment tags, embedded art, ReplayGain
  [1]; open, royalty-free (Xiph) [13]. This is the right **archive/storage**
  format: it halves the library's footprint with no quality loss and carries its
  own metadata. Recording engineers "keep working files as WAV during production,
  then archive finished projects as FLAC for long-term storage" [1] — foley
  ingests *finished* sounds, so it archives directly in FLAC.

### 1.3 Lossy — MP3, AAC, Ogg Vorbis, Opus (delivery only)

Lossy codecs are for **delivery/preview**, never for the canonical archive (they
discard data and re-encoding compounds loss). Ranked by quality-per-bit and
license cleanliness:

- **Opus** (IETF RFC 6716, Xiph) — the modern winner. Royalty-free; **64 kbps
  Opus sounds like 128 kbps MP3**, transparent for most listeners at ~128 kbps,
  intelligible speech down to 16 kbps, low-latency [2][14]. Container: `.opus`
  (Ogg) or WebM. **This is foley's default delivery codec.**
- **AAC** — better than MP3 per kilobit, the broadcast/streaming de-facto standard
  [2] — but **still patent-encumbered** with per-unit "end-user codec" licensing
  [3]. Avoid as a *default* in an open library; support only when a downstream
  target demands it.
- **MP3** — lossy, universal legacy playback. Core patents **expired April 2017**
  (US 6,009,399; Fraunhofer/Technicolor ended licensing 23 Apr 2017) [3], so
  baseline encode+decode is now royalty-free. Keep it as the **maximum-compatibility
  fallback**, not the default.
- **Ogg Vorbis** — open, strong sub-100 kbps, but **superseded by Opus** on every
  axis [2][14]. No reason to choose it for new work.

### 1.4 Sample rate, bit depth, channels

- **Sample rate: 48 kHz is foley's canonical rate.** 44.1 kHz is the CD/music
  legacy; **48 kHz is the professional audio/video/broadcast standard** — evenly
  divisible by common frame rates (24 fps) and required by many streaming/broadcast
  pipelines [15]. Nyquist at 48 kHz reaches 24 kHz, past human hearing [15].
  Decisively for foley: **CLAP expects 48 kHz mono** [report 04], and the weave
  layer targets video (48 kHz). Native SFX libraries are often 96/192 kHz for
  slow-motion headroom [15]; foley **preserves the source rate in the FLAC
  archive** and **resamples to 48 kHz only for the working array / embedding**.
- **Bit depth: archive at the source depth (commonly 24-bit), work in `float32`.**
  16-bit gives 96 dB SNR (distribution-grade); 24-bit gives 144 dB (recording
  headroom) [16]. Internal DSP should be **32-bit float** to avoid clipping across
  chained operations, quantizing back only on final encode.
- **Channels: preserve stereo in the archive, down-mix to mono for the embedding.**
  CLAP and most taggers are mono; store the real (often stereo) file, derive mono
  transiently.

---

## 2. Python Audio I/O — the library matrix

| Library | Backs onto | Best at | Load-bearing gotchas |
|---|---|---|---|
| **`soundfile`** | libsndfile (C) | fast WAV/FLAC/OGG read+write, streaming, in-memory | MP3 **read+write only since v0.11.0** (Jun 2022, libsndfile 1.1.0) [4]; no AAC |
| **`librosa`** | soundfile + soxr + numba | high-level DSP (trim, stretch, resample, features) | heavy (numba/scipy); audioread fallback **deprecated (0.10), removed in 1.0** [5][17] |
| **`soxr`** | libsoxr (C) | best-quality/fast resampling, streaming | mono-1D or 2D `(frames, ch)`; float32/64/int16/32 [6] |
| **`pyloudnorm`** | numpy/scipy | BS.1770-4 / EBU-R128 loudness (LUFS) | needs ≥ ~0.4 s of audio; gate floor -70 LUFS [7] |
| **`ffmpeg` (CLI)** | its own codecs | MP3/AAC/Opus transcode, exotic containers | **licensing** (§2.3) — external tool, don't bundle |
| **`pydub`** | ffmpeg + stdlib `audioop` | terse editing API (fades, gain, slice) | **broken on Python 3.13** — `audioop` removed (PEP 594) [9][10]; loosely maintained |
| **`torchaudio`** | SoX/soundfile/ffmpeg | tensor pipelines, GPU transforms | **maintenance phase 2.8→2.9**; load/save deprecated → **TorchCodec** [11] |
| **`audioread`** | GStreamer/CoreAudio/MAD/ffmpeg | last-resort decode of odd codecs | deprecated by librosa [17]; raw 16-bit PCM only |

### 2.1 `soundfile` — the default engine

`soundfile` (a CFFI wrapper over **libsndfile** + NumPy) is the right default: it
reads/writes WAV, FLAC, OGG/Vorbis, and (since libsndfile 1.1.0 / soundfile 0.11.0,
June 2022) MP3 [4]; v0.13.0 (2 Jan 2025) added `compression_level` and
`bitrate_mode` controls for compressed output [4]. It exposes subtypes
(`PCM_16`, `PCM_24`, `FLOAT`), streams large files without full load via
`blocks()`, and reads/writes **file-like objects** (`io.BytesIO`) — the property
that lets foley move bytes in and out of a `dol` store without touching disk [4].

```python
import io, soundfile as sf, numpy as np

# read (returns float64 by default; ask for float32 for the working array)
wav, sr = sf.read(
    "door_creak.flac", dtype="float32"
)  # wav: (frames,) or (frames, channels)

# stream a huge file in blocks (constant memory)
for block in sf.blocks("long_ambience.flac", blocksize=48000, dtype="float32"):
    process(block)

# encode to FLAC entirely in memory -> bytes for a dol store
buf = io.BytesIO()
sf.write(buf, wav, sr, format="FLAC", subtype="PCM_24")
flac_bytes = buf.getvalue()
```

> libsndfile does **not** do AAC and its MP3/Opus support is newer/narrower than
> FFmpeg's. For those, shell out to `ffmpeg` (§2.3) — but only as an optional path.

### 2.2 `librosa` for DSP, `soxr` under it

`librosa` is the high-level DSP toolbox (trim, split, time-stretch, pitch-shift,
feature extraction). Since v0.7 it **loads via `soundfile` by default**, falling
back to the now-deprecated `audioread` only for codecs libsndfile can't handle
[17]. Its `resample()` default is **`soxr_hq`** [5] — i.e. librosa already
delegates resampling to **`soxr`** (libsoxr), which foley can also call directly
for tight control (QQ/LQ/MQ/HQ/VHQ presets, `ResampleStream` for long/real-time
signals) [6]. Prefer `soxr`/librosa over naive polyphase resampling: quality of
sample-rate conversion materially affects downstream embedding fidelity.

### 2.3 FFmpeg — powerful, but a licensing liability to *inherit*

FFmpeg decodes/encodes essentially everything (MP3, AAC, Opus, exotic containers),
and `ffmpeg-python` / `pydub` are thin wrappers over the CLI. But its licensing must
**not** be inherited by a broadly-installed `pip` library:

- FFmpeg is **LGPL-2.1+ by default**, with optional **GPL** parts that, if enabled,
  relicense the whole binary as GPL; it is **not** available under proprietary
  terms [8].
- Patent-encumbered codecs (**AAC**, H.264/265) may require **separate patent
  licenses** for commercial use regardless of the FFmpeg license [8].

**Design rule for foley:** never bundle or hard-depend on FFmpeg. Treat it as an
**optional external tool** discovered at runtime (per the house `check_requirements`
convention — point users at an install command, don't ship the binary). Keep the
zero-dep core and the FLAC/WAV/Opus path on royalty-free codecs; use FFmpeg only when
a user explicitly needs MP3/AAC transcode, and keep that behind an extra
(`foley[ffmpeg]`).

### 2.4 What to avoid as load-bearing

- **`pydub`** — its editing API is pleasant, but it imports the stdlib **`audioop`**
  module that PEP 594 **removed in Python 3.13** [9][10]; it works only if the user
  installs the `audioop-lts` shim, and the project is loosely maintained. Do not put
  it on the critical path; reimplement the handful of ops foley needs on NumPy.
- **`torchaudio`** — from **2.8 it is in maintenance**, load/save are deprecated and
  removed in 2.9, with decode/encode moving to **TorchCodec** [11]. Only reach for it
  (or TorchCodec) inside a torch-based tagging/embedding pipeline that already has the
  dependency — never as the general I/O layer.

---

## 3. Core DSP Operations — recommended library per op

All ops assume the working representation: a `float32` NumPy array at 48 kHz, shape
`(frames,)` mono or `(frames, channels)`.

### 3.1 Trim silence — `librosa.effects.trim` / `split`

Silence = segments ≥ `top_db` below the reference (peak RMS) level [18]. `trim`
strips leading/trailing silence; `split` returns non-silent intervals (for
segmenting a long recording).

```python
import librosa

trimmed, idx = librosa.effects.trim(y, top_db=30)  # strip head/tail silence
intervals = librosa.effects.split(y, top_db=30)  # (m, 2) sample ranges of sound
```

Gotcha: on **all-silent** input `trim` can misbehave / return an empty span — guard
for it (relevant to near-silent SFX) [18].

### 3.2 Fades — NumPy ramps (equal-power for crossfades)

No library needed; a fade is a gain envelope. Use **equal-power** (√) curves for
crossfades to avoid a mid-fade dip.

```python
import numpy as np


def fade(y, sr, fade_s=0.02, kind="linear"):
    n = int(fade_s * sr)
    ramp = np.linspace(0, 1, n, dtype=y.dtype)
    if kind == "equal_power":
        ramp = np.sqrt(ramp)
    env = np.ones(len(y), dtype=y.dtype)
    env[:n], env[-n:] = ramp, ramp[::-1]
    return y * env[:, None] if y.ndim == 2 else y * env
```

A short (10–20 ms) fade on every trimmed clip prevents click artifacts at edit
points — cheap insurance the ingest pipeline should apply by default.

### 3.3 Resample — `soxr` (highest quality/speed)

```python
import soxr

y48 = soxr.resample(y, in_rate=sr, out_rate=48000, quality="HQ")  # or "VHQ"
```

`soxr` is libsoxr, fast and high-quality, with `ResampleStream` for very long
signals [6]; it is exactly what `librosa.resample(..., res_type="soxr_hq")` uses
[5]. Resample **only to derive the 48 kHz working/embedding array** — keep the
archive at its native rate.

### 3.4 Channel up/down-mix — NumPy

```python
mono = y.mean(axis=1) if y.ndim == 2 else y  # down-mix for CLAP
stereo = np.column_stack([mono, mono]) if mono.ndim == 1 else y  # up-mix by duplication
```

Down-mix to mono for embedding/tagging; **preserve the original channel layout in
the archive** (stereo carries spatial info the weave layer uses).

### 3.5 Time-stretch & pitch-shift — `pyrubberband` (quality) vs `librosa` (built-in)

Two tiers:

- **`librosa.effects.time_stretch` / `pitch_shift`** — phase-vocoder, pure-Python
  deps, no external binary [19]. Fine for modest ratios; audible smearing on
  transient-heavy SFX at larger factors.
- **`pyrubberband`** — wraps the **Rubber Band** library; markedly higher quality
  on percussive/transient material [19]. **Caveat:** it needs the external
  `rubberband` CLI, and Rubber Band is **GPL / commercial-licensed** — the same
  "external optional tool, don't inherit the license" rule as FFmpeg applies.

```python
import librosa

y_fast = librosa.effects.time_stretch(y, rate=1.2)  # 20% faster, same pitch
y_higher = librosa.effects.pitch_shift(y, sr=48000, n_steps=3)  # +3 semitones
# high quality (optional dep, GPL external binary):
# import pyrubberband as pyrb; y_hq = pyrb.time_stretch(y, 48000, 1.2)
```

Default to librosa's built-ins; expose `pyrubberband` behind `foley[hifi-dsp]`.

### 3.6 Loudness-normalize — `pyloudnorm` (BS.1770-4 / EBU-R128)

Peak normalization is not perceptual; **loudness** normalization is. `pyloudnorm`
implements **ITU-R BS.1770-4 / EBU R128** (MIT-licensed; v0.2.0, 4 Jan 2026, adds
LRA) [7]:

```python
import pyloudnorm as pyln

meter = pyln.Meter(48000)  # BS.1770-4 K-weighted meter
lufs = meter.integrated_loudness(y)  # measured LUFS
if lufs > -70:  # skip the gate floor (near-silent)
    y = pyln.normalize.loudness(
        y, lufs, -23.0
    )  # normalize to -23 LUFS (EBU R128 target)
```

Gotcha: very short or near-silent inputs report ≈ **-70 LUFS** (the gate floor) —
**flag, don't amplify**, or you just boost hiss [7][20]. Stamp the measured
`loudness_lufs` onto the `SoundRecord` at ingest (report 04 §6.4). FFmpeg's two-pass
`loudnorm` filter is the alternative when transcoding through FFmpeg anyway [20], but
`pyloudnorm` keeps the measurement in-process on the working array with no external
binary.

---

## 4. Storage — audio bytes behind a `dol` `Mapping`

### 4.1 The blob store is a `Mapping[key → bytes]`

foley's audio bytes live behind the same `dol` abstraction report 04 set for the
whole library: a `Mapping` whose local implementation is `dol.Files` and whose cloud
implementation is an S3/blob store — **swapped by config, not code** [21]. Nothing
in ingest/search/weave knows which backend is live.

```python
# local (default)                         # cloud (same interface, config flip)
from dol import Files  # from foley.stores import S3BytesStore

sounds = Files(
    "~/.local/share/foley/audio/"
)  # sounds = S3BytesStore("s3://foley/audio/")

sounds[key] = flac_bytes  # write blob
raw = sounds[key]  # read blob   -> bytes
```

Per the app-data-lifecycle convention, blobs go under `~/.local/share/foley/audio/`
(never inside the package dir), addressed through the store so they can grow up into
S3 without touching business logic.

### 4.2 Content-addressed keys → free de-duplication + immutability

Key each blob by a **hash of its content**, not by filename. Identical bytes → same
key → stored once (**automatic de-dup**); keys are **immutable** (content can't
silently change under a key), which makes caching and cloud sync safe.

```python
import hashlib


def content_key(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # stable, portable, git-like
```

- **`sha256`** (stdlib `hashlib`) is the recommended default: ubiquitous, portable,
  the de-facto content-addressing choice [22]. With SHA-NI it runs ~1.5–2.5 GB/s
  [23].
- **`blake3`** (optional dep) is ~2–4× faster (4–7 GB/s) [23] — worth it only for
  very large ingest batches where hashing is the bottleneck. Keep it behind an extra
  and **store the algorithm alongside the key** so libraries stay mixed-hash-coherent
  (same discipline as `embedding_model` in report 04).

A `dol` **key-transforming wrapper** makes this transparent: business code does
`store[record] = bytes`; the wrapper computes the content key and dedupes.

### 4.3 Separate heavy bytes from lightweight metadata/index

This is the core layout decision and it matches report 04's four-store facade:

```
SoundLibrary (facade)
├── sounds : Mapping[key → bytes]        # HEAVY audio blobs   (dol.Files → S3)      ← this report
├── meta   : Mapping[id → SoundRecord]   # LIGHT canonical SSOT (JSON/SQLite → S3/PG)
├── vindex : VectorIndex                 # CLAP 512-d          (LanceDB → s3://)
└── kindex : KeywordIndex (BM25)         # tags + caption      (LanceDB FTS)
```

`SoundRecord.uri` (report 04's schema) is a **reference into `sounds`** (the content
key), not the bytes themselves. Consequences: (1) listing/searching/faceting touch
only the small `meta`/index stores — fast and cheap; (2) the multi-GB blob store
scales independently (and can live on cold/object storage); (3) a record can point at
bytes that are cached-by-value *or* remote-by-reference (§4.4) with no schema change.

### 4.4 Store-by-value vs store-by-reference — a per-source **license** gate

Whether foley caches the actual bytes (**by value**) or only a URI + provenance
(**by reference**) is **not** a storage-engineering choice — it's a **licensing**
one, resolved per source via the `LicenseRecord` (report 01/design):

- **By value (cache the bytes)** — allowed when the license permits redistribution/
  copying: **CC0** and CC-BY audio, user's own files, accepted generations. The
  blob lands in `sounds`; the record's `uri` is the content key.
- **By reference (URI + metadata only)** — required when caching is restricted.
  **Freesound's API terms** are the canonical example: applications may "make
  limited intermediate copies … deleted when they are no longer required" and
  **"Do not make full copies of the database."** [12] So even though a *CC0*
  Freesound sound is legally copyable, the **API-TOS layer** constrains bulk
  caching — foley stores the reference and provenance, fetching bytes on demand and
  treating any local copy as a deletable cache, not the library of record.

The blob store therefore has **two entry modes** behind one interface: a
`by_value` put (bytes → content key) and a `by_reference` put (URI + fetch policy).
`decide()`/ingest consult `commercial_ok`/`redistribute_ok` before choosing — the
license record is the single source of truth for caching policy.

---

## 5. Performance — lazy decode, caching, batch

- **Store compressed, decode lazily.** Keep FLAC bytes in `sounds`; decode to a
  NumPy array **only when needed** (embedding, tagging, weaving). A `dol` value-decode
  wrapper turns `sounds[key]` → bytes into `decoded[key]` → array transparently, so
  callers never manage decode state.
- **Stream, don't slurp, large files.** `soundfile.blocks()` / `soxr.ResampleStream`
  process arbitrarily long ambiences in constant memory [4][6] — essential when a
  single field-recording is hundreds of MB.
- **Cache the expensive artifacts, not the cheap ones.** The costly thing is the
  **CLAP embedding** (a model forward pass), not the decode. Persist embeddings in
  `vindex` (report 04) and memoize hot decoded arrays with `functools.lru_cache` /
  `dol.cache_this`. Content-addressed keys make these caches trivially correct
  (same key ⇒ same bytes ⇒ same embedding).
- **Batch ingest as a stream.** Decode once, then run **tag + embed + loudness**
  together on that single decoded array (avoid re-decoding per model). Process the
  corpus as a generator pipeline (`probe → decode → {tag, embed, lufs} → record`),
  and parallelize with a process pool — `soundfile`/`soxr`/numba release the GIL, so
  CPU-bound decode+resample scales across cores. Write blobs and records in the same
  pass so a crash leaves the two stores consistent (write blob first, then the record
  that references it).

---

## 6. Recommendations for foley

### 6.1 Canonical audio representations (three, one per role)

| Role | Representation | Why |
|---|---|---|
| **Working** (in RAM) | **`float32` NumPy array, 48 kHz**; mono for embed/tag, native channels for weave | lingua franca of soundfile/librosa/soxr/CLAP; float avoids clip across chained DSP; 48 kHz = CLAP + video standard [15][report 04] |
| **Archive** (bytes at rest, `sounds` store) | **FLAC**, source sample-rate & bit-depth preserved, native channels | lossless, 40–60 % smaller than WAV [1], self-describing tags, royalty-free [13] |
| **Delivery / preview** (derived) | **Opus** (`.opus`/WebM) default; **MP3** legacy fallback; AAC only on demand | royalty-free, transparent ≪ WAV size [2][14]; MP3 patent-free since 2017 [3]; AAC still encumbered [3] |

Rule: **archive lossless (FLAC), compute on `float32`@48 kHz, deliver lossy (Opus).**
Never let a lossy format be the library of record.

### 6.2 `dol`-based store layout (bytes ⟂ metadata ⟂ index)

```python
class SoundLibrary:
    def __init__(self, *, sounds=None, meta=None, vindex=None, kindex=None):
        # HEAVY bytes — content-addressed, dedup, license-gated by/ref-or-value
        self.sounds = sounds or ContentAddressed(Files("~/.local/share/foley/audio/"))
        # LIGHT canonical SoundRecord SSOT (report 04 schema)
        self.meta = meta or JsonFiles("~/.local/share/foley/meta/")
        # search indexes (report 04) — one LanceDB table, local dir or s3://
        self.vindex = vindex or LanceVectorIndex(...)  # CLAP 512-d
        self.kindex = kindex or LanceKeywordIndex(...)  # BM25 tags+caption

    def audio(self, sid):
        return self.sounds[self.meta[sid].uri]  # bytes (or fetch-by-ref)

    def array(self, sid, sr=48000, mono=True):  # lazy decode → working array
        y, r = sf.read(io.BytesIO(self.audio(sid)), dtype="float32")
        if mono and y.ndim == 2:
            y = y.mean(1)
        return soxr.resample(y, r, sr) if r != sr else y
```

- **Tier 0 (default, local):** `sounds` = `dol.Files` under `~/.local/share/foley/`;
  `meta` = JSON files; `vindex`+`kindex` = one LanceDB table. Zero servers.
- **Tier 1 (cloud):** flip `sounds` → S3 bytes store, `meta` → S3/Postgres, LanceDB →
  `s3://` — **same facade, no business-logic change** [21][report 04]. Content keys
  make the local↔cloud copy idempotent and dedup-safe.
- **Caching policy** rides on the `LicenseRecord`: CC0/CC-BY/own/generated →
  by-value in `sounds`; Freesound/TOS-restricted → by-reference (URI + provenance),
  local bytes treated as a deletable cache [12].

### 6.3 Recommended library per operation

| Operation | Library | Note |
|---|---|---|
| Read/write WAV, FLAC, OGG; stream; in-memory bytes | **`soundfile`** (libsndfile) | default engine; MP3 r/w since 0.11.0 [4] |
| MP3 / AAC / Opus transcode, odd containers | **`ffmpeg`** (external, optional) | licensing — don't bundle; `foley[ffmpeg]` [8] |
| Resample | **`soxr`** (HQ/VHQ) | librosa's own default backend [5][6] |
| Trim silence / segment | **`librosa`** `.effects.trim`/`.split` | guard all-silent input [18] |
| Fades / crossfades | **NumPy** ramps | equal-power for crossfades |
| Channel up/down-mix | **NumPy** (`mean` / `column_stack`) | mono for embed, keep stereo archive |
| Time-stretch / pitch-shift | **`librosa`** (default) → **`pyrubberband`** (hi-fi, optional GPL) | transient quality tier [19] |
| Loudness normalize (LUFS) | **`pyloudnorm`** (BS.1770-4/EBU-R128) | flag the -70 LUFS gate floor [7][20] |
| Content hash / dedup | **`hashlib.sha256`** → **`blake3`** (optional, fast) | store algo with key [22][23] |
| Storage `Mapping` | **`dol`** (`Files` → S3) | local→cloud, one interface [21] |

**Do not** put `pydub` (Python-3.13 `audioop` removal [9][10]) or `torchaudio`
(maintenance/TorchCodec migration [11]) on the load-bearing path.

---

## REFERENCES

1. Cloudinary. *FLAC vs. WAV: 4 Key Differences and How to Choose*; and everpresent, *FLAC vs. WAV* (lossless equivalence, 40–60 % size reduction, WAV as working / FLAC as archive, metadata support). [cloudinary.com/guides/front-end-development/flac-vs-wav-4-key-differences-and-how-to-choose](https://cloudinary.com/guides/front-end-development/flac-vs-wav-4-key-differences-and-how-to-choose) · [everpresent.com/flac-vs-wav](https://everpresent.com/flac-vs-wav/)
2. Xiph.Org. *Opus Codec — Comparison* (Opus > other codecs at 64 kb/s; 64 kb/s Opus ≈ 128 kb/s MP3; transparency; cascading-encode resilience). [opus-codec.org/comparison](https://opus-codec.org/comparison/) · Valin J-M et al., *High-Quality, Low-Delay Music Coding in the Opus Codec*, arXiv:1602.04845. [arxiv.org/pdf/1602.04845](https://arxiv.org/pdf/1602.04845)
3. Fraunhofer IIS. *Alive and Kicking — mp3 Software, Patents and Licenses* (MP3 licensing ended 23 Apr 2017; baseline royalty-free); AppleInsider, *Patent licensing on MP3 format expires; AAC a de-facto standard* (AAC remains encumbered). [audioblog.iis.fraunhofer.com/mp3-software-patents-licenses](https://www.audioblog.iis.fraunhofer.com/mp3-software-patents-licenses) · [appleinsider.com/articles/17/05/15/...](https://appleinsider.com/articles/17/05/15/patent-licensing-on-mp3-format-expires-apple-preferred-aac-now-a-de-facto-standard)
4. python-soundfile (bastibe). *Documentation & changelog* — formats (WAV/FLAC/OGG/MP3), MP3 read+write since v0.11.0 (2 Jun 2022, libsndfile 1.1.0), `compression_level`/`bitrate_mode` in v0.13.0 (2 Jan 2025), `blocks()` streaming, `BytesIO`/file-like I/O, subtypes. [python-soundfile.readthedocs.io/en/0.13.1](https://python-soundfile.readthedocs.io/en/0.13.1/) · [github.com/bastibe/python-soundfile](https://github.com/bastibe/python-soundfile)
5. librosa. *`librosa.resample` documentation* (default `res_type='soxr_hq'`; soxr VHQ/HQ/MQ/LQ; resampy/samplerate optional). [librosa.org/doc/latest/generated/librosa.resample.html](https://librosa.org/doc/latest/generated/librosa.resample.html)
6. python-soxr (dofuuz) — wrapper of libsoxr; `soxr.resample`, QQ/LQ/MQ/HQ/VHQ presets, `ResampleStream`, dtypes float32/64/int16/32. [github.com/dofuuz/python-soxr](https://github.com/dofuuz/python-soxr) · libsoxr (chirlu): [github.com/chirlu/soxr](https://github.com/chirlu/soxr)
7. pyloudnorm (csteinmetz1) — ITU-R BS.1770-4 / EBU R128 integrated loudness; `Meter.integrated_loudness`, `normalize.loudness`, `normalize.peak`; MIT; v0.2.0 (4 Jan 2026, LRA). [github.com/csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm)
8. FFmpeg. *License and Legal Considerations* (LGPL-2.1+ default, optional GPL parts relicense the whole, no proprietary terms, patent-encumbered codecs e.g. AAC/H.264 need separate licenses). [ffmpeg.org/legal.html](https://www.ffmpeg.org/legal.html)
9. jiaaro/pydub. *Issue #863 — `pyaudioop` / `audioop` removed on Python 3.13*; *#867 — Adapt pydub to Python 3.13*. [github.com/jiaaro/pydub/issues/863](https://github.com/jiaaro/pydub/issues/863)
10. Python. *PEP 594 — Removing dead batteries from the standard library* (`audioop` removed in 3.13); `audioop-lts` drop-in shim. [peps.python.org/pep-0594](https://peps.python.org/pep-0594/) · [pypi.org/project/audioop-lts](https://pypi.org/project/audioop-lts/)
11. pytorch/audio. *Update on TorchAudio's future* (Issue #3902) & docs — maintenance phase from 2.8, load/save deprecated (removed 2.9), decode/encode consolidated into **TorchCodec** (`AudioDecoder`/`AudioEncoder`), `load_with_torchcodec` shim. [github.com/pytorch/audio/issues/3902](https://github.com/pytorch/audio/issues/3902) · [docs.pytorch.org/audio/2.8/torchaudio.html](https://docs.pytorch.org/audio/main/torchaudio.html)
12. Freesound. *Terms of Use of the Freesound API* ("make limited intermediate copies … deleted when no longer required"; "Do not make full copies of the database"; no redistribution outside your application). [freesound.org/help/tos_api](https://freesound.org/help/tos_api/) · overview: [freesound.org/docs/api/terms_of_use.html](https://freesound.org/docs/api/terms_of_use.html)
13. Xiph.Org. *FLAC — Free Lossless Audio Codec* (open, royalty-free, lossless, Vorbis-comment metadata). [xiph.org/flac](https://xiph.org/flac/)
14. Cloudinary. *AAC vs Opus* and AudioUtils, *Opus vs MP3 / Opus vs AAC* (bitrate-quality curves, container support, delivery guidance). [cloudinary.com/guides/video-formats/aac-vs-opus](https://cloudinary.com/guides/video-formats/aac-vs-opus) · [audioutils.com/blog/opus-vs-mp3](https://audioutils.com/blog/opus-vs-mp3)
15. Soundstripe, *48 kHz vs 44.1 kHz*; Wikipedia, *48,000 Hz* (48 kHz professional/video standard, divisible by 24 fps, broadcast requirement; SFX libraries at 96/192 kHz). [soundstripe.com/blogs/48khz-vs-44.1khz-best-audio-sample-rate-for-video](https://www.soundstripe.com/blogs/48khz-vs-44.1khz-best-audio-sample-rate-for-video) · [en.wikipedia.org/wiki/48,000_Hz](https://en.wikipedia.org/wiki/48,000_Hz)
16. SoundGuys. *Audio Bit Depth Explained* (16-bit ≈ 96 dB, 24-bit ≈ 144 dB SNR; 24-bit recording headroom, 16-bit distribution; 32-bit float for processing). [soundguys.com/audio-bit-depth-explained-23706](https://www.soundguys.com/audio-bit-depth-explained-23706/)
17. librosa. *Advanced I/O Use Cases* & Issue #1456 (soundfile default backend since v0.7; audioread deprecated in 0.10, removed in 1.0; MP3 pre-libsndfile-1.1 fell back to audioread). [librosa.org/doc/0.11.0/ioformats.html](https://librosa.org/doc/0.11.0/ioformats.html) · [github.com/librosa/librosa/issues/1456](https://github.com/librosa/librosa/issues/1456)
18. librosa. *`librosa.effects.trim` / `split`* (top_db vs reference RMS; interval output; all-silence edge cases, Issues #1802/#1809). [librosa.org/doc/main/generated/librosa.effects.trim.html](https://librosa.org/doc/main/generated/librosa.effects.trim.html)
19. librosa. *`effects.time_stretch` / `pitch_shift`* (phase vocoder) and pyrubberband (`pyrb.time_stretch`/`pitch_shift`, Rubber Band, higher quality). [librosa.org/doc/0.11.0/generated/librosa.effects.pitch_shift.html](https://librosa.org/doc/0.11.0/generated/librosa.effects.pitch_shift.html) · [github.com/bmcfee/pyrubberband](https://github.com/bmcfee/pyrubberband) · Rubber Band: [breakfastquay.com/rubberband](https://breakfastquay.com/rubberband/)
20. slhck. *ffmpeg-normalize* & *Two-pass loudness normalization with FFmpeg loudnorm* (EBU R128 two-pass measure→apply; -70 LUFS gate floor caution for short/near-silent inputs). [github.com/slhck/ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) · [dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3)
21. dol (i2mint) — Python data-object-layer: storage as a `Mapping`, local→cloud behind one interface; key/value-transforming wrappers, `Files`, caching. [github.com/i2mint/dol](https://github.com/i2mint/dol)
22. Transloadit. *Efficient file deduplication with SHA-256* (content-based dedup: identical content → identical hash → single stored path). [transloadit.com/devtips/efficient-file-deduplication-with-sha-256-and-node-js](https://transloadit.com/devtips/efficient-file-deduplication-with-sha-256-and-node-js/)
23. SSOJet. *BLAKE3 vs SHA-256* (BLAKE3 ~4–7 GB/s vs SHA-256 ~1.5–2.5 GB/s with SHA-NI; BLAKE3 Python bindings). [ssojet.com/compare-hashing-algorithms/blake3-vs-osdb-hash](https://ssojet.com/compare-hashing-algorithms/blake3-vs-osdb-hash) · BLAKE3: [github.com/BLAKE3-team/BLAKE3](https://github.com/BLAKE3-team/BLAKE3)
