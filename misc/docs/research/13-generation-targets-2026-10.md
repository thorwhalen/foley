# 13 — SFX generation targets: the delta since July 2026, an inventory, and what foley misses

*Research for the SFX facade (2026-10-03). Scope: sound-effect **generation** only (text-to-SFX, video-to-audio, local models, procedural synthesis). Retrieval/libraries are out of scope. This is a **delta** on foley's July 2026 research: foley report 02 (generation) [1], report 07 (licensing) [2] and report 10 (architecture) [3]. What those reports establish is cited, not re-derived. Prices were read on 2026-10-03 unless marked otherwise; "unverified" means a single secondary source or an inference.*

## Summary

1. **The biggest change is Stable Audio 3 (May 2026)** [11][14]: an open-weights family with a **Small-SFX** model (433M params, 120 s, 44.1 kHz stereo) that runs **on CPU** (30 s of audio in ~1.7 s on a Mac CPU), under the same Stability Community License as Stable Audio Open (commercial use free under US $1M revenue) [10][11]. It should replace Stable Audio Open 1.0 as foley's local default.
2. **Two commercially permissive open SFX models appeared**: **MOSS-SoundEffect v2.0** (Apache-2.0, 1.3B, 48 kHz, 30 s) [43] and **Dasheng-AudioGen** (Apache-2.0, 16 kHz, speech+music+SFX in one scene) [45]. **EzAudio** (MIT weights) [47] and **Make-An-Audio 2** (MIT, not "verify") [49] join Make-An-Audio 1 as permissive options. TangoFlux is confirmed **non-commercial** [50].
3. **Video-to-audio (V2A) is now a mature, cheap, hosted mode**: fal alone hosts 10+ V2A endpoints (MMAudio v2, ThinkSound, HunyuanVideo-Foley, Mirelo SFX 1.5/1.6, Kling, ControlFoley, Sonilo, PixVerse, CassetteAI) at $0.001–$0.01 per output second [16][17]. foley has no video-conditioned mode at all.
4. **New dedicated SFX vendors**: **Mirelo** (Berlin, $41M raised Dec 2025; own REST API + MIT Python/JS SDKs; SFX 1.6 does text-to-SFX, seamless ambience loops, extend, inpaint, V2A up to 60 s) [23][28][30][31] and **Sonilo** (Shutterstock-licensed training data; text-to-SFX up to 180 s; V2A with per-segment prompts; inaudible provenance watermark reported in the response) [26][27].
5. **ElevenLabs is unchanged at the API level**: still only `eleven_text_to_sound_v2`, same params, $0.12/min, terms last updated 2026-02-12 [4][5][6][7]. One foley bug follows: foley maps `output_format='wav'` to MP3 because "no lossless container", but the enum has `pcm_44100`/`pcm_48000` [5]. Lossless is available.
6. **Stability's hosted API moved to Stable Audio 3** (`/v2beta/audio/stable-audio/text-to-audio`, 380 s, flat 26 credits) and **has no `negative_prompt`** (report 02's adapter table says it does) [8].
7. **Distilled models break foley's guidance mapping**: SA 2.5/3 default to `cfg_scale=1`, 8 steps [8][12]. foley's linear `prompt_influence→guidance_scale` map with default 0.3 would push them off their tuned operating point. The knob must default to "backend native" (`None`).
8. **Licence traps found**: fal labels MMAudio v2 (video) as `commercial` while its weights are CC-BY-NC [20][52]. HunyuanVideo-Foley's licence **does not apply in the EU, UK or South Korea**, and forbids using outputs to improve other models [54]. ThinkSound's weights are tagged Apache-2.0 but its README says research-only [55][56]. Mirelo, Sonilo and ElevenLabs free tiers are **non-commercial** [7][27][28].
9. **Not SFX targets**: Google (Lyria = music, Veo = audio only inside video) [40], OpenAI (Sora 2 video+audio only; API sunset reported) [41], Adobe Firefly (SFX in the app, no public API) [38][39], Meta (AudioGen unchanged since 2024, CC-BY-NC) [42].
10. **Procedural synthesis is a missing backend kind**: sfxr-family generators (pyfxr BSD-3, jsfxr Unlicense, ZzFX MIT, jfxr BSD-3, rFXGen zlib with a CLI) are free, offline, deterministic and their outputs are unencumbered [60]–[66]. They are the right default for UI blips, game-style cues and placeholders.

## 0. What the July reports already establish (not repeated here)

- The two-mode split (hosted vs local), the July comparison table, and the per-model notes for AudioGen, Stable Audio Open 1.0 / Small, AudioLDM(2), Tango(2), Auffusion, GenAU and MMAudio: foley report 02 [1].
- The output-licence matrix (commercial, standalone redistribution, attribution, AI training), the ElevenLabs sublicensing opt-out, AudioSeal and C2PA, and the EU AI Act Art. 50 disclosure duty: foley report 07 [2].
- The `SOURCE_CONFIG` plugin shape, the `GENERATION_AFFORDANCES` vocabulary (`prompt`, `duration`, `prompt_influence`, `negative_prompt`, `steps`, `seed`, `loop`, `output_format`), `commercial_ok`, and the generation flywheel: foley report 10 [3].

foley today ships two generate sources: `stable_audio` (local diffusers `StableAudioPipeline`, SAO 1.0) and `elevenlabs` (hosted v2). `foley.generate(prompt, *, backend=..., **affordances)` returns one stored `Candidate`. It records no cost and takes no video input.

## 1. What changed since July 2026 (the delta)

| # | Change | Date | Consequence for foley |
|---|---|---|---|
| D1 | **Stable Audio 3** open family: Small-SFX, Small-Music, Medium (open), Large (API only), plus base checkpoints, LoRA fine-tuning, inpainting, audio-to-audio [11][12][14] | May 2026 (HF repos 2026-05-19) | New local default (CPU-capable SFX model, 120 s). New ops: inpaint, audio-to-audio. |
| D2 | Stability API: SA3 endpoint `/v2beta/audio/stable-audio/*`, 380 s, 26 credits flat; SA 2/2.5 endpoint still live [8] | 2026 | Hosted adapter target; no `negative_prompt`; async results endpoint exists. |
| D3 | fal hosts SA3 Small-SFX at **$0.0206/clip** and SA3 Medium at **$0.0376/clip** [16][19] | 2026-05-22/25 | The cheapest high-quality hosted SFX path, roughly 10x cheaper than Stability direct. |
| D4 | **Mirelo SFX 1.6** (text-to-SFX, `ambience` loop tiles, extend, inpaint, V2A to 60 s) [23] | 2026-05-15/18 | New vendor and a second provider with a loop concept, which promotes `loop` (§3). |
| D5 | **Sonilo v1.1** text-to-SFX (to 180 s) and V2A with `segments`; fal exclusive launch partner [26] | 2026-07-20 | New vendor; licensed training data (Shutterstock) [27]; watermark field in output. |
| D6 | **ControlFoley** on fal (V2A, $0.002/s) [25] | 2026-05-05 | New V2A option; schema not published (unverified params). |
| D7 | **MOSS-SoundEffect v2.0** (Apache-2.0) [43]; **Dasheng-AudioGen** (Apache-2.0) [45][46] | 2026-05/06 | First strong permissively licensed open SFX models. |
| D8 | **LTX-2.3 Foley LoRA** (V2A for the LTX video model; LTX Community License, free under $10M ARR) [57][58]; fal `ltx-2.3-quality/text-to-audio` [72] | 2026-06/09 | Another V2A route, tied to an open video model. |
| D9 | ElevenLabs: no new SFX model; v2 page now advertises "WAV (48kHz)" output [6]; terms unchanged since 2026-02-12 [7] | — | Fix foley's `wav` mapping (use `pcm_48000`). |
| D10 | Beatoven SFX (`fal-ai/beatoven/sound-effect-generation`, which falaw's corpus references) no longer appears in fal's model search [16] | seen 2026-10-03 | Treat as delisted (unverified). |
| D11 | OpenAI Sora app closed 2026-04-26 and the API reportedly stopped accepting requests 2026-09-24 [41] | 2026 | No OpenAI SFX path (secondary source, unverified). |
| D12 | Google Lyria 3 (Mar 2026) and Lyria 3.5 (Sep 2026) in the Gemini API: music only [40] | 2026 | Out of scope (arioso's territory). |

## 2. Inventory cards

Card fields follow the facade-design target template: kind; access and package licences; entry operation and native params verbatim; output; pricing (source, date); output licence and terms; provenance/watermark; maturity. Long tails are tables.

### 2A. Hosted text-to-SFX (first-party APIs)

#### elevenlabs-sfx — ElevenLabs Sound Effects v2 (in foley)
- **Kind:** hosted-generate. **Access:** REST; Python SDK `elevenlabs` 2.70.0 (MIT) [75]; JS SDK `@elevenlabs/elevenlabs-js` 2.70.0 (MIT); auth header `xi-api-key`, env `ELEVENLABS_API_KEY`.
- **Entry:** `POST /v1/sound-generation` (SDK `client.text_to_sound_effects.convert`). Body: `text` (str, required), `duration_seconds` (number|null, 0.5–30, null = auto), `prompt_influence` (number|null, 0–1, default 0.3), `loop` (bool, default false), `model_id` (enum, only `eleven_text_to_sound_v2`). Query: `output_format` [4][5].
- **Output:** `output_format` enum: `mp3_22050_32`, `mp3_24000_48`, `mp3_44100_{32,64,96,128,192}`, `pcm_{8000,16000,22050,24000,32000,44100,48000}`, `ulaw_8000`, `alaw_8000`, `opus_48000_{32,64,96,128,192}` [5]. Sync, returns bytes. One variation per call. Max 30 s. Loopable: yes.
- **Pricing:** $0.12 per minute of audio via API [6] (seen 2026-10-03; same as July [1]). Same price on fal ($0.002/s) [16][73].
- **Output licence/ToS:** unchanged since report 07 [2]: paid plans give commercial rights, free plan is non-commercial with attribution, standalone redistribution of raw SFX prohibited, outputs sublicensed to other users unless "Disable" is set. SFX Terms last updated 2026-02-12 [7].
- **Watermark/C2PA:** none documented for SFX (unverified).
- **Maturity:** stable; SDK released 2026-09-28. **Delta:** none at the API level; the lossless PCM outputs were already in the enum and foley does not use them.

#### stability-api — Stability AI Stable Audio (2 / 2.5 / 3 Large) hosted API
- **Kind:** hosted-generate (also audio-to-audio and inpaint). **Access:** REST, `Authorization: Bearer`, multipart form. No official Python SDK for audio.
- **Entry (SA3):** `POST /v2beta/audio/stable-audio/text-to-audio` with `prompt` (required), `model` (enum `stable-audio-3`), `duration` (1–380, default 190), `seed`, `steps` (4–8, default 8), `cfg_scale` (1–25, default 1), `output_format` (`mp3`|`wav`) [8]. Siblings: `/audio-to-audio` (+`audio`, `strength` 0–1), `/inpaint` (+`audio`, `mask_start`, `mask_end`), and `GET /v2beta/audio/results/{id}` for async results.
- **Entry (SA 2/2.5):** `POST /v2beta/audio/stable-audio-2/text-to-audio` with `prompt`, `duration` (1–190), `seed`, `steps`, `cfg_scale` (1–25), `model` (`stable-audio-2.5`|`stable-audio-2`), `output_format` [8].
- **No `negative_prompt`** on any audio endpoint [8]. Report 02's adapter table [1] is wrong on this point.
- **Output:** mp3 or wav, 44.1 kHz stereo; one clip per call.
- **Pricing:** SA3 flat 26 credits per success; SA 2.5 flat 20 credits; SA 2 `credits = 17 + 0.06*steps` [8]. At $0.01/credit (report 02 [1]) that is $0.26 and $0.20 per clip.
- **Output licence/ToS:** the platform API has its own terms separate from the Community License [9]. Report 07 records commercial use plus Enterprise indemnification [2]. SA3 training data is licensed (AudioSparx) plus CC Freesound [13].
- **Maturity:** active. SA3 Large is API-only [11].

#### mirelo — Mirelo SFX (direct API) (new)
- **Kind:** hosted-generate + video-to-audio. **Access:** REST (base `https://api.mirelo.ai/v2/`, Bearer) [31]; Python `mirelo-sdk` 1.0.0 (MIT) [30]; JS `@mirelo/sdk` 1.0.4 (MIT); also an MCP server, plus Premiere, Resolve, Reaper and Roblox plugins [29].
- **Entry and params:** the direct API schema could not be fetched (docs site unreachable; unverified). Native names as exposed on fal [23]: `text_prompt`, `duration` (0.1–60; ≥1 when `ambience`), `num_samples` (1–4, default 2), `seed`, `ambience` (bool: "a seamlessly loopable ambience tile"), `double_output` (loop concatenated to 2x), `upload_audio_format` (`wav`|`mp3`|`aac`|`flac`). V2A: `video_url`, `text_prompt`, `duration` (1–60), `num_samples`, `seed`, and on v1.5 `start_offset` [80]. Also `extend-audio` and `inpaint-audio` ops.
- **Output:** up to 4 variations per call; wav/mp3/aac/flac.
- **Pricing (direct):** Free €0 (5,000 credits/mo ≈ 8 min of SFX 1.6, watermark on exports, projects deleted after 1 week); Creator €20/mo (24,000 credits ≈ 40 min; extra €0.90/1,000 credits); Studio €99/mo (≈ 200 min); Scale, Business and Enterprise above that [29] (seen 2026-10-03). On fal: $0.01 per output second [16]. Whether `num_samples` multiplies the fal charge is unverified.
- **Output licence/ToS:** Free plan non-commercial only (§2.1); paid plans commercial (§2.2); IP in output "vest[s] exclusively in you" (§7.3); Mirelo gets a **training licence on your input and output**, which paid users can opt out of and free users cannot (§7.4); free output may carry a watermark (§7.5) [28].
- **Maturity:** SFX 1.6 released May 2026; funded [31].

#### sonilo — Sonilo Sound Effects v1.1 (new)
- **Kind:** hosted-generate + video-to-audio. **Access:** own platform API (`platform.sonilo.com`; unverified) and fal (exclusive launch partner) [26]. SDKs: unverified.
- **Entry (fal):** text: `prompt` (required), `duration` (0.5–180, default 8), `audio_format` (`aac`|`mp3`|`wav`|`flac`, default aac). V2A: `video_url`, `prompt` (optional; auto-captions if empty), `segments` (time ranges, each with its own description), `audio_format`, `keep_speech_vocal` (separates and keeps the source speech) [16][17].
- **Returns:** `audio`, `audios` (all samples, "one per sample"), `watermark` ("present when the audio carries the inaudible provenance watermark") [17]. This is the only target that **reports its own watermark in the response**.
- **Pricing (fal):** text $0.0018/s; V2A $0.009/s [16].
- **Output licence/ToS:** "fully licensed via Shutterstock" (the vendor's own claim; its comparison blog [77] is marketing); commercial rights for Pro, Premium, Enterprise and eligible API users; **Free and Creator plans are personal and non-commercial** [27]. Terms for fal-routed calls are unverified (fal labels the endpoints `commercial`).

#### Resellers and wrappers of the above (no new model)
| Id | What | Native params | Note |
|---|---|---|---|
| `fal-ai/elevenlabs/sound-effects/v2` | ElevenLabs v2 on fal | `text`, `duration_seconds`, `prompt_influence`, `loop`, `output_format` (no `ulaw`/`alaw`/`mp3_24000_48`/`pcm_32000`) | $0.002/s [16][73]; billed through fal |
| Magnific (formerly Freepik) API | ElevenLabs SFX behind a task API | `text` (≤2500 chars), `duration_seconds` (**0.5–22**, required), `loop`, `prompt_influence`, `webhook_url`; `POST/GET /v1/ai/sound-effects[/{task-id}]` | async + webhook; 22 s cap suggests the v1 limit [37] (pricing unverified) |
| Replicate `stability-ai/stable-audio-2.5` | SA 2.5 | — | exists; price not shown without login [35] |
| ComfyUI partner nodes, Segmind, Runware | ElevenLabs / Mirelo resellers | — | not carded (no added capability) |

#### Checked and dropped as SFX targets
| Target | Finding |
|---|---|
| **Adobe Firefly** "Generate Sound Effects" | In the Firefly web/mobile app (beta; text or voice-imitation prompt; "commercially safe") [38]. The Firefly API lists image endpoints only; **no public SFX API** (as of 2026-10-03) [39]. |
| **Google** | Lyria 3 / 3.5 in the Gemini API are music [40]; Veo 3.x emits audio only inside video. No audio-only SFX endpoint found (absence, partially verified). |
| **OpenAI** | Sora 2 generates synchronized SFX inside video; no text-to-SFX endpoint. The Sora API is reported to have stopped 2026-09-24 (secondary source, unverified) [41]. |
| **Meta** | AudioCraft code MIT, last push 2026-03; AudioGen weights still CC-BY-NC; no new SFX model [42]. (Meta SAM Audio on fal is **separation**, not generation [16].) |
| **ByteDance Seed Audio 1.0** (`bytedance/seed-audio-1.0` on fal) | Voice/speech-oriented (`voice`, `pitch`, `speed`); not an SFX generator [17]. |

### 2B. fal-hosted generation endpoints (aggregator)

Access for all: `fal-client` 1.0.3 (Python; repo Apache-2.0) [76] and `@fal-ai/client` 1.10.1 (JS, MIT); env `FAL_KEY`; queue (async) or `subscribe`. **falaw already reaches fal**, so these are reachable through it rather than a new transport. Endpoint ids come from fal's model gallery and search API [15] and pricing from fal's pricing API, both read 2026-10-03 [16]. Params come from each endpoint's OpenAPI [17]. The fal `license_type` field is fal's own label; see the conflict notes.

**Text-to-SFX on fal**

| Endpoint id | Native params (verbatim; * = required) | Limits / output | Price (fal, 2026-10-03) | Licence notes |
|---|---|---|---|---|
| `fal-ai/stable-audio-3/small/sfx/text-to-audio` (+ `/base/` variant) | `prompt`*, `duration` (1–120, def 30), `num_inference_steps` (1–100, def 8), `guidance_scale` (0–25, def 1), `negative_prompt`, `seed`, `output_format` (`mp3`/`wav`/`flac`/`ogg`/`opus`/`m4a`/`aac`), `bitrate` (def `192k`), `enable_prompt_expansion`, `enable_safety_checker`, `sync_mode` | 120 s; returns `audio`, `seed`, `prompt` | **$0.0206 / audio** | SA Community via fal; fal label commercial [19] |
| `fal-ai/stable-audio-3/medium/text-to-audio` (+ `/base/`) | same as above; `duration` 1–380 | 380 s | $0.0376 / audio | as above |
| `fal-ai/stable-audio-3/small/sfx/{audio-to-audio,audio-inpainting,audio-outpainting}` | (edit ops; not carded) | — | — | new op family |
| `fal-ai/stable-audio-25/text-to-audio` | `prompt`*, `seconds_total` (1–190, def 190), `num_inference_steps` (4–8, def 8), `guidance_scale` (1–25, def 1), `seed`, `sync_mode` | 190 s | $0.20 / audio | [79] |
| `fal-ai/stable-audio` (SAO 1.0) | `prompt`*, `seconds_total` (0–47, def 30), `seconds_start`, `steps` (2–1000, def 100) | 47 s; returns `audio_file` | $0.00125 / compute-second | in report 02 [1][78] |
| `fal-ai/elevenlabs/sound-effects/v2` | see §2A | 30 s | $0.002 / s | ElevenLabs terms |
| `mirelo-ai/sfx1.6/text-to-audio` | `text_prompt`*, `duration` (0.1–60), `num_samples` (1–4, def 2), `seed`, `ambience`, `double_output`, `upload_audio_format` | 60 s; 1–4 variations | $0.01 / s | Mirelo terms [28] |
| `sonilo/v1.1/text-to-sound-effects` | `prompt`*, `duration` (0.5–180, def 8), `audio_format` | 180 s; `watermark` field | $0.0018 / s | Sonilo terms [27] |
| `fal-ai/mmaudio-v2/text-to-audio` | `prompt`*, `negative_prompt`, `duration` (1–30, def 8), `num_steps` (4–50, def 25), `cfg_strength` (0–20, def 4.5), `mask_away_clip`, `seed` | 30 s | $0.001 / s | **fal label `None`**; weights CC-BY-NC [52] |
| `cassetteai/sound-effects-generator` | `prompt`*, `duration`* (int 1–30) | 30 s; returns `audio_file` | $0.01 / generation | vendor terms unverified [71] |
| `fal-ai/ltx-2.3-quality/text-to-audio` (+ `/lora`) | `prompt`*, `negative_prompt` (def "pc game, console game, …"), `num_frames` (9–481), `frames_per_second` (1–60), `num_inference_steps` (8–30, def 15), `guidance_scale` (1–20, def 1), `seed`, `enable_prompt_expansion`, `enable_safety_checker` | duration = `num_frames/frames_per_second` (~20 s max at 24 fps) | $0.0024075 / "megapixel" (odd unit for audio; unverified) | LTX Community License (free under $10M ARR) [58][72] |

**Video-to-audio on fal**

| Endpoint id | Native params (verbatim) | Limits / output | Price | Licence notes |
|---|---|---|---|---|
| `fal-ai/mmaudio-v2` | `video_url`*, `prompt`*, `negative_prompt`, `duration` (1–30, def 8), `num_steps`, `cfg_strength`, `mask_away_clip`, `seed` | returns `video` | $0.001 / s | **fal says `commercial`; weights CC-BY-NC-4.0** [20][52] (conflict) |
| `fal-ai/thinksound` (+ `/audio`) | `video_url`*, `prompt` (auto-extracted if empty), `num_inference_steps` (2–100, def 24), `cfg_scale` (1–20, def 5), `seed` | returns `video`, `prompt` | $0.001 / s | weights tagged Apache-2.0 but README says research-only [21][55][56] (conflict) |
| `fal-ai/hunyuan-video-foley` | `video_url`*, `text_prompt`*, `negative_prompt` (def "noisy, harsh"), `guidance_scale` (1–10, def 4.5), `num_inference_steps` (10–100, def 50), `seed` | returns `video` | $0.10 per 10 s | Tencent Hunyuan Community licence: **not valid in EU/UK/South Korea** [22][54] |
| `mirelo-ai/sfx1.6/video-to-video`, `mirelo-ai/sfx-v1.5/video-to-audio` (+ v1) | `video_url`*, `text_prompt`, `duration` (1–60), `num_samples` (1–4), `seed`, `start_offset` (v1.5) | up to 60 s; 1–4 variations | $0.01 / s | Mirelo terms [28][80] |
| `fal-ai/kling-video/video-to-audio` | `video_url`* (mp4/mov, ≤100 MB, **3–20 s**), `sound_effect_prompt` (≤200 chars), `background_music_prompt` (≤200 chars), `asmr_mode` | returns `audio` (MP3) and `video` | $0.035 / video | Kling terms unverified [24] |
| `sonilo/v1.1/video-to-sound-effects` (+ `video-to-video-sound-effects`) | `video_url`*, `prompt`, `segments`, `audio_format`, `keep_speech_vocal` | audio length = video length; `watermark` | $0.009 / s | Sonilo terms [27] |
| `fal-ai/controlfoley` | schema not published (only `prompt` visible) — **unverified** | — | $0.002 / s | fal label commercial [25] |
| `fal-ai/pixverse/sound-effects` | `video_url`*, `prompt`, `original_sound_switch` | returns `video` | $0.10 per 5 s | PixVerse terms unverified [70] |
| `cassetteai/video-sound-effects-generator` | (not fetched) | — | — | — |

**Fal-specific conflicts to encode, not paper over:** (a) fal's `license_type: commercial` is a platform label, not the model licence. MMAudio-v2 (video) carries it while its weights are CC-BY-NC. fal's ToS says the customer owns its Output Content [18], but whether fal holds a commercial licence from the MMAudio authors is undocumented (unverified). (b) For partner models (Mirelo, Sonilo, ElevenLabs, Kling), the vendor's plan-tier rules may or may not apply to fal-routed calls; unverified. Record `licence_basis="aggregator-label"` with low confidence until confirmed.

### 2C. Replicate-hosted (aggregator)

`replicate` (Python 1.0.7, Apache-2.0; JS 1.4.0, Apache-2.0); env `REPLICATE_API_TOKEN`; billed by GPU time. Existence verified 2026-10-03 by page fetch. Prices are from search snippets (unverified).

| Model id | Kind | Note |
|---|---|---|
| `tencent/hunyuanvideo-foley` | V2A | ~$0.011/run, ~12 s [32] (unverified); same EU/UK/KR licence limit [54] |
| `zsxkib/mmaudio` | V2A + T2A | ~$0.0064/run [33] (unverified); CC-BY-NC weights |
| `zsxkib/thinksound` | V2A | research-only per README [34][55] |
| `declare-lab/tangoflux` | T2A | non-commercial [36][50] |
| `stability-ai/stable-audio-2.5` | T2A | [35] |
| `stackadoc/stable-audio-open-1.0`, `sepal/audiogen` | T2A | in report 02 [1] |

### 2D. Local / open models

**Weights licence ≠ code licence ≠ output terms.** Dates are last repo/model update.

#### sa3-small-sfx — Stable Audio 3 Small-SFX (new; recommended local default)
- **Kind:** local-model. **Access:** repo `Stability-AI/stable-audio-3` (code MIT; README points to the Community License for models) [11]; Python package `stable_audio_3` installed with `uv sync` from the repo (**not on PyPI**); weights gated on HF [13]; also ONNX, GGUF, MLX and CoreML community ports.
- **Entry:** `StableAudioModel.from_pretrained("small-sfx").generate(prompt=..., negative_prompt=..., duration=..., steps=8, cfg_scale=1, seed=-1, batch_size=1)`; audio-to-audio via `init_audio`, `init_noise_level`; inpainting via `inpaint_audio`, `inpaint_mask_start_seconds`, `inpaint_mask_end_seconds` (scalars or lists, so several holes in one pass) [12].
- **Output:** 44.1 kHz stereo (SAME-Small autoencoder), variable length up to **120 s**; `batch_size` gives variations.
- **Hardware:** **CPU only is fine**: 30 s of audio in 1.72 s on a Mac CPU and 0.63 s with CoreML; peak ~1.9 GB [11]. Medium (1.4B, 380 s) needs CUDA + Flash Attention 2, ~5–6.5 GB VRAM [11].
- **Weights licence:** Stability AI Community License: free (including commercial) under US $1M annual revenue, registration required for commercial use, user owns outputs, may not use outputs to build competing foundation models [9][10]. Training data: 806k AudioSparx (licensed) + 473k Freesound CC0/CC-BY/CC-Sampling+ clips [13].
- **Maturity:** paper arXiv 2605.17991 [14]; repo pushed 2026-09-29.

#### Other local models (delta vs report 02 in bold)

| Model | Kind | Weights licence (commercial?) | Size / HW | Max len, SR | Run with (package) | Native params | Status |
|---|---|---|---|---|---|---|---|
| **MOSS-SoundEffect v2.0** [43][44] | T2A (SFX) | **Apache-2.0 (yes)** | 1.3B DiT, CUDA (torch.compile) | 30 s, **48 kHz** | git `OpenMOSS/MOSS-TTS/moss_soundeffect_v2` (`MossSoundEffectPipeline`) | `prompt`, `seconds`, `num_inference_steps` (100), `cfg_scale` (4.0), `sigma_shift` (5.0) | new 2026-05; training data not stated (unverified) |
| **Dasheng-AudioGen** [45][46] | T2A (scene: speech+music+SFX) | **Apache-2.0 (yes)** | transformers `trust_remote_code`, CUDA | 16 kHz | `transformers<5` `AutoModel` | `compose_prompt(caption=, sfx=, env=, music=, speech=, asr=)` then `generate(prompts, num_steps=25, guidance_scale=5.0, sway_sampling_coef=-1.0)` | new 2026-06 (Xiaomi); tagged prompt format |
| **EzAudio** [47][48] | T2A | **MIT (yes)** (HF tag) | DiT, GPU | ~10 s (unverified) | git `haidog-yaqub/EzAudio` | (not carded) | not in report 02; trained on AudioCaps/WavCaps, whose data terms are academic (caveat, unverified) |
| **Make-An-Audio 2** [49] | T2A | **MIT (yes)**; resolves report 02's "verify" | ~8–12 GB | ~10 s | git `bytedance/Make-An-Audio-2` | (not carded) | stale (2024) |
| Stable Audio Open 1.0 / Small | T2A | SA Community (< $1M) | per [1] | 47 s / 11 s | diffusers 0.40 `StableAudioPipeline`; `stable-audio-tools` 0.0.20 [74] | per [1] | **superseded by SA3 Small-SFX** |
| **TangoFlux** [50] | T2A | **non-commercial, research-only** (SA Community + WavCaps academic-only) | 8–12 GB | 30 s | PyPI `tangoflux` 0.1.0 | — | resolves report 02's "verify": **NC** |
| AudioX / AudioX-MAF [51] | any-to-audio | CC-BY-NC-4.0 (no) | — | — | git `ZeyueT/AudioX` | — | 2026-02/03 |
| AudioGen | T2A | CC-BY-NC (no) | ≥16 GB | 10 s, 16 kHz | `audiocraft` 1.3.0 (2024) [42] | per [1] | unchanged; MLX port exists |
| AudioLDM2, Tango 2, Auffusion, GenAU | T2A | NC (per [1]) | — | — | — | — | unchanged |

**Local video-to-audio**

| Model | Weights licence | HW | Notes |
|---|---|---|---|
| **MMAudio** (`large_44k_v2` etc.) [52][53] | **CC-BY-NC-4.0** (code MIT) | ~6 GB fp16 | unchanged since [1]; repo pushed 2026-02; fal and Replicate host it |
| **HunyuanVideo-Foley** [54] | Tencent Hunyuan Community: **territory excludes EU, UK, South Korea** (outputs included, §5c); outputs may not improve other models (§5b); >100M MAU needs a licence | large (XL variants; unverified) | best sync per secondary sources; legally unusable for an EU-based user |
| **ThinkSound** [55][56] | HF tag Apache-2.0, but README: "for research and educational purposes only … for commercial licensing, please contact the authors"; bundles an SAO VAE under SA Community | GPU | treat as **non-commercial**; PyPI `thinksound` 0.0.19 exists (unverified as official) |
| **LTX-2.3 Foley LoRA** [57][58] | LTX Community License (free under $10M ARR) | 22B LTX base (large GPU) | gated; V2A as a LoRA on an open video model |
| **Kling-Foley** [59] | repo has no licence file | — | repo dormant since 2025-06; weights unclear (drop) |

### 2E. Procedural / parametric synthesis (a new backend kind)

Deterministic given parameters (some generators randomise unless seeded), free, offline, milliseconds, no model. Licence-clean: the code licence covers the tool, and these tools put no restriction on the sounds they produce. Best fit: UI blips, pickups, lasers, jumps, hits, alarms, retro cues, placeholders. Poor fit: realistic foley (doors, rain, footsteps).

| Id | Language / package | Licence (code) | Entry and native params (verbatim) | Output | Status |
|---|---|---|---|---|---|
| **pyfxr** [60][61] | Python, PyPI `pyfxr` 0.3.0 (Cython wheels for Mac/Win/Linux) | BSD-3-Clause | presets `pickup()`, `laser()`, `explosion()`, `powerup()`, `hurt()`, `jump()`, `select()` return `SFX`; `SFX(base_freq, freq_limit, freq_ramp, freq_dramp, duty, duty_ramp, vib_strength, vib_speed, vib_delay, env_attack, env_sustain, env_decay, env_punch, lpf_resonance, lpf_freq, lpf_ramp, hpf_freq, hpf_ramp, pha_offset, pha_ramp, repeat_speed, arp_speed, arp_mod, wave_type)`; `.as_dict()` round-trips; also `tone()`, `pluck(duration=, pitch=)`, `chord()` | mono 44.1 kHz `SoundBuffer` (buffer protocol), save to WAV | last push 2025-07; small but working |
| **jsfxr** [62] | JS, npm `jsfxr` 1.4.1 (Node + browser) | Unlicense | `sfxr.generate(preset)` with presets `pickupCoin`, `laserShoot`, `explosion`, `powerUp`, `hitHurt`, `jump`, `blipSelect`, `synth`, `tone`, `click`, `random`; `sfxr.toWave(sound)`, `toBuffer`, `toAudio`; sounds serialise as JSON or base58 (`b58encode`/`b58decode`) | WAV | active (2026-05) |
| **ZzFX** [63] | JS, npm `zzfx` 1.4.0 | MIT | `zzfx(...params)` / `ZZFX.buildSamples(volume, randomness, frequency, attack, sustain, release, shape, shapeCurve, slide, deltaSlide, pitchJump, pitchJumpTime, repeatTime, noise, modulation, bitCrush, delay, sustainVolume, decay, tremolo, filter)`; `sampleRate: 44100` | Float samples (WAV export in the designer app) | very active (2026-10-01); a whole sound is one short array, so it is cheap to store as provenance |
| **jfxr** [64] | JS, npm `jfxr` 0.13.0 (2022) | BSD-3; README: "sound effects you make are entirely yours" | browser app plus library (API not carded) | WAV | app active (2026-07), npm stale |
| **bfxr2** [65] | JS web app | MIT | new footstep generator (port of Obiwannabe's Pure Data model), Transfxr (morphs between states), Chattr (creature babble) | WAV | very active (pushed 2026-10-03); app, not a library (unverified) |
| **rFXGen** [66] | C (raylib) desktop + **CLI** | zlib | `rfxgen --input <file.rfx|preset> --output <file.wav>` batch conversion and presets | WAV | active (2026-08); wrappable from Python via subprocess |
| ChipTone [69] | web app (SFB Games) | proprietary app; outputs reported free for commercial use (unverified) | — | WAV | not wrappable (no API) |
| Tone.js [67] | JS, npm `tone` 15.1.22 | MIT | general Web Audio synthesis framework (`Synth`, `NoiseSynth`, `MetalSynth`, envelopes, `Offline` rendering) | buffer | very active; a building block, not an SFX generator |
| sfxr (original) [68] | C++ desktop | MIT (per author page; unverified) | — | WAV | reference design for the whole family |

**Shared vocabulary of the sfxr family:** base frequency and slide, ADSR envelope (attack/sustain/decay/punch), wave type (square/saw/sine/noise), vibrato, arpeggio, duty cycle, low-/high-pass filter, phaser, repeat, plus a small fixed set of **category presets** (pickup/coin, laser, explosion, powerup, hit/hurt, jump, blip/select). The presets are the facade-level concept. The 20–25 synthesis params stay native.

## 3. Jargon table (generation)

Columns: EL = ElevenLabs; SA-API = Stability hosted; SA3 = Stable Audio 3 local; fal-SA3 = SA3 on fal; MMA = MMAudio (fal); Mir = Mirelo SFX 1.6 (fal); Son = Sonilo (fal); HVF = HunyuanVideo-Foley (fal); TS = ThinkSound (fal); MOSS; dif = diffusers SAO/AudioLDM2; AG = AudioGen; pfx = pyfxr/jsfxr/ZzFX. "—" means the concept is absent. Canonical = the proposed foley name; ✓ means ≥2 providers share the concept (promotion rule); ✗ means it stays native and goes through the escape hatch.

| Concept | EL | SA-API | SA3 | fal-SA3 | MMA | Mir | Son | HVF / TS | MOSS | dif | AG | pfx | Canonical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| text description | `text` | `prompt` | `prompt` | `prompt` | `prompt` | `text_prompt` | `prompt` | `text_prompt` / `prompt` | `prompt` | `prompt` | `descriptions` (list arg) | — (preset) | `prompt` ✓ (have) |
| length | `duration_seconds` (0.5–30, null=auto) | `duration` (1–380) | `duration` | `duration` (1–120/380) | `duration` (1–30) | `duration` (0.1–60) | `duration` (0.5–180) | — (= video) | `seconds` | `audio_end_in_s` / `audio_length_in_s` | `set_generation_params(duration=)` | envelope-derived | `duration_s` ✓ (rename from `duration`; `None` = backend auto) |
| prompt adherence | `prompt_influence` (0–1, def 0.3) | `cfg_scale` (1–25, **def 1**) | `cfg_scale` (def 1) | `guidance_scale` (0–25, def 1) | `cfg_strength` (0–20, def 4.5) | — | — | `guidance_scale` (1–10, def 4.5) / `cfg_scale` (1–20, def 5) | `cfg_scale` (4.0) | `guidance_scale` (def 7) | `cfg_coef` | — | `prompt_influence` ✓ (0–1, **default `None` = native default**; per-backend `coerce`) |
| exclude content | — | **—** | `negative_prompt` | `negative_prompt` | `negative_prompt` | — | — | `negative_prompt` / — | — | `negative_prompt` | — | — | `negative_prompt` ✓ (have) |
| sampler steps | — | `steps` (4–8) | `steps` (def 8) | `num_inference_steps` | `num_steps` | — | — | `num_inference_steps` | `num_inference_steps` | `num_inference_steps` | — | — | `steps` ✓ (have) |
| randomness seed | — | `seed` | `seed` (-1 = random) | `seed` | `seed` | `seed` | — | `seed` | — (torch) | `generator` | — | random unless seeded (jsfxr/pyfxr presets) | `seed` ✓ (have; record the seed the backend **returns**, since fal SA3 and LTX echo it) |
| loopable output | `loop` | — | — | — | — | `ambience` (+`double_output`) | — | — | — | — | — | `repeat_speed` (different meaning) | `loop` ✓ (have; now 2 providers) |
| number of variations | — (1) | — (1) | `batch_size` | — | — | `num_samples` (1–4) | (`audios` list returned, no knob) | — | — | `num_waveforms_per_prompt` | batch via list of prompts | — | `n` ✓ (new; returns a list) |
| model / version | `model_id` | `model` | `from_pretrained("small-sfx")` | endpoint id | endpoint id | endpoint id | endpoint id | endpoint id | repo id | repo id | `get_pretrained` | — | `model` ✓ (new; today it is buried in `native_defaults`) |
| container / codec | `output_format` (`codec_sr_bitrate` enum) | `output_format` (`mp3`/`wav`) | — (tensor) | `output_format` + `bitrate` | — | `upload_audio_format` | `audio_format` | — | — | — | — | WAV | `output_format` ✓ (have) |
| sample rate | inside `output_format` | — | fixed 44.1k | — | fixed 44.1k | — | — | — | fixed 48k | fixed | fixed 16k | 44.1k | `sample_rate` ✓ (EL encodes it, and Seed Audio exposes `sample_rate`) as a **requested** value, with the actual rate reported back |
| video conditioning | — | — | — | — | `video_url` | `video_url` | `video_url` | `video_url` | — | — | — | — | `video` ✓ (new: path/URL/bytes) |
| keep source audio | — | — | — | — | `mask_away_clip` (different meaning) | — | `keep_speech_vocal` | — | — | — | — | — | `keep_source_audio` ✓ (also PixVerse `original_sound_switch`) |
| time-ranged prompts | — | — | — | — | — | `start_offset` (v1.5) | `segments` | — | — | — | — | — | native ✗ (Sonilo only) |
| separate SFX vs music prompt | — | — | — | — | — | — | — | — | — | — | — | — | native ✗ (Kling `sound_effect_prompt` / `background_music_prompt`) |
| init audio (audio-to-audio) | — | `audio` + `strength` | `init_audio` + `init_noise_level` | (separate endpoint) | — | — | — | — | — | — | (continuation) | — | `init_audio`, `strength` ✓ (new op) |
| inpaint window | — | `mask_start`, `mask_end` | `inpaint_mask_start_seconds`, `inpaint_mask_end_seconds` | (separate endpoint) | — | (`inpaint-audio` endpoint) | — | — | — | — | — | — | `inpaint_start_s`, `inpaint_end_s` ✓ (new op) |
| extend / continue | — | (inpaint past end) | (inpaint) | `audio-outpainting` | — | `extend-audio` | — | — | — | — | continuation | — | `extend` op ✓ (new) |
| prompt rewriting | — | — | — | `enable_prompt_expansion` | — | — | auto-caption when empty | TS: auto-extract | — | — | — | — | `expand_prompt` ✓ (fal SA3 and LTX share the param; report the prompt actually used) |
| provenance watermark | — | — | — | — | — | (free tier) | `watermark` (returned) | — | — | — | — | — | output field `watermark` ✓ (Mirelo and Sonilo both watermark; record whether the **vendor** watermarked, separately from foley's AudioSeal) |
| category preset | — | — | — | — | — | — | — | — | — | — | — | `pickupCoin`/`pickup()`, … | `preset` (procedural kind only) ✓ (jsfxr, pyfxr, rFXGen share it) |
| synthesis params | — | — | — | — | — | — | — | — | — | — | — | `base_freq`, `env_attack`, … / `frequency`, `attack`, … | native ✗ (different param sets per lib) |
| sigma shift, sway sampling, ASMR mode, safety checker, sync mode | — | — | — | `enable_safety_checker`, `sync_mode` | — | — | — | — | `sigma_shift` | — | `top_k`, `top_p`, `temperature` | — | native ✗ (escape hatch) |

**Notes on the coercions the table implies:**
- `prompt_influence` is the only portable adherence knob because the native scales differ: 0–1 (EL), 1–10 (HVF), 0–20 (MMA), 1–25 (SA). For **distilled** backends (SA 2.5 and SA3 post-trained models default to `cfg_scale=1` with 8 steps [8][12]), any value above 1 departs from the tuned regime. foley's current map `guidance_scale = 1 + prompt_influence*(cfg_max-1)` with default 0.3 would send `cfg=5.2` to an SA3 backend. Make the default `None` (native), and let each config declare its `coerce` and whether the backend is distilled.
- `duration` semantics differ: EL `null` = auto with a flat fee; V2A ignores it (length = video), except MMAudio and Mirelo, which take it; LTX derives it from frames. The canonical is "requested seconds or `None`"; the **actual** duration must be measured and stored.
- `seed` is honoured only where the backend exposes it. ElevenLabs, Sonilo and Kling are non-reproducible, and the provenance record should say so instead of storing a meaningless seed.

## 4. Output-licence vocabulary (generation targets → foley `LicenseFlags`)

foley's `LICENSE_FLAGS` already has `ElevenLabs-SFX` and `Stability-Community` [2]. Rows the new targets need (commercial / attribution / standalone redistribution / AI-training-ok / revenue cap / territory). Normalisation never widens rights.

| Proposed `license_id` | commercial | attribution | redistribute standalone | ai_training_ok | cap / territory | Source |
|---|---|---|---|---|---|---|
| `Mirelo-Paid` | yes | no | unverified (assume no) | no (and Mirelo trains on your output unless opted out) | — | [28] |
| `Mirelo-Free` | **no** | unverified | no | no | watermark | [28] |
| `Sonilo-Paid` (Pro/Premium/Enterprise/API) | yes | unverified | unverified (assume no) | unverified | — | [27] |
| `Sonilo-Free` (Free/Creator) | **no** | — | no | — | — | [27] |
| `Stability-Community` (now also SA3 weights) | yes | no (only when redistributing weights) | no | no (no competing foundation models) | $1M revenue | [9][10] |
| `Stability-API` | yes | no | no | unverified | — | [2][9] |
| `Apache-2.0` (MOSS, Dasheng outputs) | yes | no | yes | yes | training-data provenance unverified | [43][45] |
| `MIT` (Make-An-Audio 1/2, EzAudio, procedural tools) | yes | no | yes | yes | EzAudio's data caveat | [47][49] |
| `Tencent-Hunyuan-Community` | yes | no | no | **no** (may not improve other models) | **excludes EU, UK, KR**; 100M MAU | [54] |
| `LTX-Community` | yes | unverified | no | unverified | $10M ARR | [58] |
| `CC-BY-NC-4.0` (MMAudio, AudioGen, AudioX) | **no** | yes | no | — | — | [1][52] |
| `research-only` (ThinkSound, TangoFlux) | **no** | — | no | — | — | [50][55] |
| `procedural-free` (sfxr family output) | yes | no | yes | yes | — | [60]–[64] |

`LicenseFlags` has no **territory** field. HunyuanVideo-Foley is the first target whose rights depend on where the user is. That is a schema gap.

## 5. What foley's generation layer misses, with recommendations

foley's current state: two `kind="generate"` sources (`stable_audio` = SAO 1.0 via diffusers; `elevenlabs` = v2), `GENERATION_AFFORDANCES` with eight names, one `Candidate` per call, no cost, no video input.

1. **SA3 Small-SFX as local default.** CPU-capable, 120 s, the same Community License as today's default. *Rec:* add a `stable_audio_3` source (`stable_audio_3.StableAudioModel`, model id `small-sfx`; `medium` when CUDA is present) and make it the default `backend`. Keep `stable_audio` (SAO) as the diffusers fallback until `stable_audio_3` is on PyPI.
2. **No fal source.** The fleet already reaches fal through falaw (Plans as data, cost at plan time, content-addressed cache). *Rec:* one `fal` generate source that maps the canonical vocabulary onto a per-endpoint `param_map` table (`fal-ai/stable-audio-3/small/sfx/text-to-audio`, `mirelo-ai/sfx1.6/text-to-audio`, `sonilo/v1.1/text-to-sound-effects`, `fal-ai/elevenlabs/sound-effects/v2`, the V2A ids). Execute through `falaw`, not raw `fal_client`.
3. **No Stability-hosted adapter** (report 10 planned one). *Rec:* add `stability_api` targeting `/v2beta/audio/stable-audio/text-to-audio` (SA3 Large). Map `negative_prompt` to unsupported; handle the async `results/{id}` path.
4. **No direct Mirelo or Sonilo adapters.** *Rec:* reach both through `fal` first (one key, one bill); add direct adapters (`mirelo-sdk`) only if a plan-tier licence (paid, training opt-out) must be provable, since fal-routed terms are unverified.
5. **Video-to-audio is not a mode.** *Rec:* add a `video` affordance (path/URL) plus a `generate_for_video(video, prompt=None, ...)` facade entry, or `generate(..., video=...)` routed only to backends declaring `modes={"v2a"}`. Return the **audio track** even when the backend returns a muxed video (strip with `mixing`). This is what an/cutan films need: foley timed to picture.
6. **Edit operations are missing** (inpaint, extend, audio-to-audio), offered by SA-API, SA3, fal-SA3 and Mirelo. *Rec:* add `init_audio`/`strength` and `inpaint_start_s`/`inpaint_end_s` as canonical (≥2 providers) behind a separate `edit()` verb rather than overloading `generate()`.
7. **No variations (`n`).** Mirelo returns 1–4 per call, SA3 has `batch_size`, diffusers has `num_waveforms_per_prompt`. *Rec:* add `n` and return a list of `Candidate`s, which feeds `verify_match` ranking (report 10's selection depends on choosing among candidates).
8. **No `model` affordance.** *Rec:* promote `model` (EL `model_id`, SA-API `model`, SA3 id, fal endpoint id) so a caller can pin a version, and store it as `generator_version`.
9. **No cost reporting.** *Rec:* add per-source `pricing` (unit, unit_price, currency, `seen` date, source URL) to `SOURCE_CONFIG`, return `cost_estimate` before the call and `cost_actual` after it on the `Candidate`/provenance (unknown = `None`, never 0). Pull fal prices live from `GET /v1/models/pricing` [16], and gate spend cumulatively, following the group's rule.
10. **`prompt_influence` default breaks distilled models.** *Rec:* default `prompt_influence=None` (backend native); give each config a `coerce` and a `distilled: bool`. Today SAO's `cfg_max=15` linear map is fine, but the same map on SA3 is wrong.
11. **ElevenLabs `wav` → MP3 is unnecessary loss.** *Rec:* map `wav` to `pcm_48000` (or `pcm_44100`) and wrap a WAV header locally. Whether PCM-44.1/48k needs a higher plan tier for SFX is unverified, so fall back to MP3 on a 4xx.
12. **Procedural kind is missing.** *Rec:* add `kind="procedural"` sources: `pyfxr` (Python, BSD-3) first, then `zzfx`/`jsfxr` (via a tiny Node shim, or a Python port of ZzFX's ~100-line `buildSamples`), with `preset` canonical and the synthesis params native. Licence row `procedural-free`, `cost=0`, `offline=True`, deterministic with a seed. Use it as the default for UI or game-style cues, and to keep tests offline.
13. **Licence schema gaps.** *Rec:* add a `territory_excludes` field (for Hunyuan's EU/UK/KR exclusion) and a `vendor_trains_on_output` flag (Mirelo, and ElevenLabs sublicensing); add the rows in §4; record `licence_basis` (`model-licence` | `vendor-tos` | `aggregator-label`) with a confidence so fal's `commercial` label is never mistaken for the weights licence.
14. **Vendor watermarks are not captured.** Sonilo returns `watermark`; Mirelo free output is watermarked. *Rec:* store the vendor's watermark statement in provenance next to foley's own AudioSeal entry, and avoid double-watermarking or misreporting.
15. **Prompt actually used is not stored.** fal SA3, LTX and ThinkSound may rewrite or auto-extract the prompt and echo it back. *Rec:* store `prompt_sent` and `prompt_used` separately in provenance.
16. **Permissive open models are not offered.** *Rec:* add `moss_soundeffect` (Apache-2.0, 48 kHz) as the "no revenue cap" local option for users above $1M revenue, after a quality check against SA3 Small-SFX on foley's gold set. Keep Dasheng-AudioGen as a candidate for whole-scene beds (16 kHz is a limit).
17. **Non-commercial V2A must be fenced.** MMAudio, ThinkSound and HunyuanVideo-Foley (in the EU) are the strongest sync models and all are licence-encumbered. *Rec:* register them with `commercial_ok=False` (Hunyuan with `territory_excludes`) so `foley.keep()` refuses them for published work, and make Mirelo or Sonilo V2A the commercial default.

## REFERENCES

1. foley report 02 — *Generative-AI SFX Generation: Local Models and Hosted APIs* (2026-07), `foley/misc/docs/research/02-genai-sfx-generation.md`
2. foley report 07 — *Licensing & provenance* (2026-07), `foley/misc/docs/research/07-licensing-provenance.md`
3. foley report 10 — *Facade architecture* (2026-07), `foley/misc/docs/research/10-facade-architecture.md`
4. [ElevenLabs — Create sound effect (API reference)](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)
5. [ElevenLabs — OpenAPI spec (`/v1/sound-generation`)](https://api.elevenlabs.io/openapi.json)
6. [ElevenLabs — API pricing](https://elevenlabs.io/pricing/api)
7. [ElevenLabs — Sound Effects Terms (last updated 12 Feb 2026)](https://elevenlabs.io/sound-effects-terms)
8. [Stability AI — Platform OpenAPI (v2beta audio endpoints, credit formulas)](https://api.stability.ai/v2alpha/openapi)
9. [Stability AI — License tiers](https://stability.ai/license)
10. [Stability AI — Community License Agreement](https://stability.ai/community-license-agreement)
11. [GitHub — Stability-AI/stable-audio-3 (models, hardware, performance)](https://github.com/Stability-AI/stable-audio-3)
12. [GitHub — Stable Audio 3 inference methods (generate / init_audio / inpaint kwargs)](https://github.com/Stability-AI/stable-audio-3/blob/main/docs/workflows/inference.md)
13. [Hugging Face — stabilityai/stable-audio-3-small-sfx](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)
14. [Stable Audio 3 technical report (arXiv:2605.17991)](https://arxiv.org/abs/2605.17991)
15. [fal.ai — model gallery](https://fal.ai/models)
16. [fal Platform API — model search and pricing (`GET /v1/models`, `GET /v1/models/pricing`), queried 2026-10-03](https://api.fal.ai/v1/models)
17. [fal — per-endpoint OpenAPI schema (example: ElevenLabs SFX v2)](https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=fal-ai/elevenlabs/sound-effects/v2)
18. [fal — Terms of Service (last updated 8 Sep 2026)](https://fal.ai/legal/terms-of-service)
19. [fal — Stable Audio 3 Small SFX text-to-audio](https://fal.ai/models/fal-ai/stable-audio-3/small/sfx/text-to-audio)
20. [fal — MMAudio V2 (video-to-audio)](https://fal.ai/models/fal-ai/mmaudio-v2)
21. [fal — ThinkSound](https://fal.ai/models/fal-ai/thinksound)
22. [fal — Hunyuan Video Foley](https://fal.ai/models/fal-ai/hunyuan-video-foley)
23. [fal — Mirelo SFX 1.6 text-to-audio](https://fal.ai/models/mirelo-ai/sfx1.6/text-to-audio)
24. [fal — Kling video-to-audio](https://fal.ai/models/fal-ai/kling-video/video-to-audio)
25. [fal — ControlFoley](https://fal.ai/models/fal-ai/controlfoley)
26. [fal — Sonilo Sound Effects 1.0 launch page](https://fal.ai/sonilo-sound-effects-1.0)
27. [Sonilo — Licensing / commercial safety](https://sonilo.com/licensing)
28. [Mirelo — Terms of service (§2 plans, §7 output rights and training licence)](https://mirelo.ai/terms)
29. [Mirelo — Pricing](https://mirelo.ai/pricing)
30. [PyPI — mirelo-sdk (MIT)](https://pypi.org/project/mirelo-sdk/)
31. [TechCrunch — Mirelo raises $41M from Index and a16z (15 Dec 2025)](https://techcrunch.com/2025/12/15/mirelo-raises-41m-from-index-and-a16z-to-solve-ai-videos-silent-problem)
32. [Replicate — tencent/hunyuanvideo-foley](https://replicate.com/tencent/hunyuanvideo-foley)
33. [Replicate — zsxkib/mmaudio](https://replicate.com/zsxkib/mmaudio)
34. [Replicate — zsxkib/thinksound](https://replicate.com/zsxkib/thinksound)
35. [Replicate — stability-ai/stable-audio-2.5](https://replicate.com/stability-ai/stable-audio-2.5)
36. [Replicate — declare-lab/tangoflux](https://replicate.com/declare-lab/tangoflux)
37. [Magnific API — Sound effects (ElevenLabs-backed) overview](https://docs.magnific.com/api-reference/sound-effects/overview.md)
38. [Adobe — Generate sound effects using text prompts (Firefly app)](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-audio/text-to-sound-effects.html)
39. [Adobe — Firefly API documentation](https://developer.adobe.com/firefly-services/docs/firefly-api/)
40. [Google — Gemini API changelog (Lyria 3 / 3.5, Veo)](https://ai.google.dev/gemini-api/docs/changelog)
41. [Gate.ai — Sora 2 specs, pricing and API status (secondary source)](https://gate.ai/blog/sora-2-openai-specs-pricing-api-use-cases)
42. [GitHub — facebookresearch/audiocraft](https://github.com/facebookresearch/audiocraft)
43. [Hugging Face — OpenMOSS-Team/MOSS-SoundEffect-v2.0 (Apache-2.0)](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0)
44. [GitHub — OpenMOSS/MOSS-TTS, moss_soundeffect_v2](https://github.com/OpenMOSS/MOSS-TTS/tree/main/moss_soundeffect_v2)
45. [Hugging Face — mispeech/Dasheng-AudioGen (Apache-2.0)](https://huggingface.co/mispeech/Dasheng-AudioGen)
46. [Dasheng AudioGen paper (arXiv:2605.27838)](https://arxiv.org/abs/2605.27838)
47. [Hugging Face — OpenSound/EzAudio](https://huggingface.co/OpenSound/EzAudio)
48. [GitHub — haidog-yaqub/EzAudio](https://github.com/haidog-yaqub/EzAudio)
49. [GitHub — bytedance/Make-An-Audio-2 (MIT)](https://github.com/bytedance/Make-An-Audio-2)
50. [GitHub — declare-lab/TangoFlux (licence section: non-commercial, research only)](https://github.com/declare-lab/TangoFlux)
51. [Hugging Face — HKUSTAudio/AudioX-MAF (CC-BY-NC-4.0)](https://huggingface.co/HKUSTAudio/AudioX-MAF)
52. [Hugging Face — hkchengrex/MMAudio (checkpoints CC-BY-NC-4.0)](https://huggingface.co/hkchengrex/MMAudio)
53. [GitHub — hkchengrex/MMAudio](https://github.com/hkchengrex/MMAudio)
54. [GitHub — Tencent-Hunyuan/HunyuanVideo-Foley LICENSE (territory excludes EU, UK, South Korea)](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley/blob/main/LICENSE)
55. [GitHub — FunAudioLLM/ThinkSound (licence note: research and educational use only)](https://github.com/FunAudioLLM/ThinkSound)
56. [Hugging Face — FunAudioLLM/ThinkSound](https://huggingface.co/FunAudioLLM/ThinkSound)
57. [Hugging Face — Lightricks/LTX-2.3-22b-LoRA-Foley-V2A](https://huggingface.co/Lightricks/LTX-2.3-22b-LoRA-Foley-V2A)
58. [ComfyUI Wiki — LTX-2.3 Foley LoRA (24 Jun 2026; LTX Community License, $10M threshold)](https://comfyui-wiki.com/en/news/2026-06-24-ltx-2-3-foley-lora)
59. [GitHub — klingfoley/Kling-Foley](https://github.com/klingfoley/Kling-Foley)
60. [GitHub — lordmauve/pyfxr (BSD-3-Clause)](https://github.com/lordmauve/pyfxr)
61. [pyfxr docs — Generating sounds (SFX parameters, presets)](https://pyfxr.readthedocs.io/en/latest/generating.html)
62. [GitHub — chr15m/jsfxr (Unlicense)](https://github.com/chr15m/jsfxr)
63. [GitHub — KilledByAPixel/ZzFX (MIT)](https://github.com/KilledByAPixel/ZzFX)
64. [GitHub — ttencate/jfxr (BSD-3; outputs are yours)](https://github.com/ttencate/jfxr)
65. [GitHub — increpare/bfxr2 (MIT)](https://github.com/increpare/bfxr2)
66. [GitHub — raysan5/rfxgen (zlib; CLI)](https://github.com/raysan5/rfxgen)
67. [GitHub — Tonejs/Tone.js (MIT)](https://github.com/Tonejs/Tone.js)
68. [DrPetter — sfxr (original)](http://www.drpetter.se/project_sfxr.html)
69. [SFB Games — ChipTone](https://sfbgames.itch.io/chiptone)
70. [fal — PixVerse sound effects](https://fal.ai/models/fal-ai/pixverse/sound-effects)
71. [fal — CassetteAI sound effects generator](https://fal.ai/models/cassetteai/sound-effects-generator)
72. [fal — LTX 2.3 Quality text-to-audio](https://fal.ai/models/fal-ai/ltx-2.3-quality/text-to-audio)
73. [fal — ElevenLabs Sound Effects V2](https://fal.ai/models/fal-ai/elevenlabs/sound-effects/v2)
74. [PyPI — stable-audio-tools](https://pypi.org/project/stable-audio-tools/)
75. [PyPI — elevenlabs (MIT)](https://pypi.org/project/elevenlabs/)
76. [GitHub — fal-ai/fal (fal-client; Apache-2.0)](https://github.com/fal-ai/fal)
77. [Sonilo — Video-to-sound-effects API comparison 2026 (vendor blog; context only)](https://sonilo.com/blog/comparisons/video-to-sound-effects-api-comparison-2026)
78. [fal — Stable Audio Open](https://fal.ai/models/fal-ai/stable-audio)
79. [fal — Stable Audio 2.5 text-to-audio](https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio)
80. [fal — Mirelo SFX v1.5 video-to-audio](https://fal.ai/models/mirelo-ai/sfx-v1.5/video-to-audio)
