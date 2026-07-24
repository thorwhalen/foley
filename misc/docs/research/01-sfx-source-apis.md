# SFX Source APIs & Sound Libraries — A Survey for foley

This report surveys the services and corpora **foley** can pull existing sound effects (SFX) from — programmable APIs, subscription libraries, non-commercial archives, and free bulk datasets — with each service's API surface, library size, license terms, pricing, rate limits, download formats, and returned metadata. The central finding: **Freesound (APIv2, filtered to CC0) is the only mature, self-serve, programmable API that also permits redistribution**, making it foley's anchor source; the professional libraries (Epidemic Sound, Storyblocks, Pond5, Pro Sound Effects) expose real APIs but gate them behind partner/enterprise agreements, while most "free" web libraries (Zapsplat, Soundly, Mixkit, Uppbeat, Pixabay audio) have **no content API** and forbid redistribution. The report closes by recommending the **Universal Category System (UCS)** as foley's canonical category vocabulary and sketching a config-driven `source adapter` plugin pattern mirroring arioso's platform config.

> **Access date:** 2026-07-22. Sound-library terms and pricing change frequently; verify license/pricing pages before relying on any figure. Facts are drawn from primary sources (official API docs, license pages) wherever possible; a handful of figures (noted inline) come from indexed reads of pages that block automated fetching, or are marked *uncertain* where sources conflict.

---

## Comparison table

Legend for **Redistribute?** — whether the raw sound files may be redistributed *on a standalone basis* (i.e., as a corpus/dataset or re-downloadable library), as opposed to embedded inside a finished derivative work (which nearly all licenses permit).

| Service | Programmable API? | Auth | Library size | Commercial use | Redistribute (standalone)? | Attribution | Formats | Best role for foley |
|---|---|---|---|---|---|---|---|---|
| **Freesound** | **Yes — APIv2 (documented, self-serve)** | Token (search) / OAuth2 (download) | 600k+ sounds | Depends on per-sound CC license | **Yes for CC0**; CC-BY yes w/ credit; CC-BY-NC no | Per-sound (CC0/BY/BY-NC) | Original: wav/aif/flac/ogg/mp3; previews mp3/ogg | **Primary programmatic source** |
| **Openverse** | Yes — REST (open) | Anonymous / OAuth2 client-creds | 1M+ audio (aggregates Freesound, Jamendo, Wikimedia) | Per-source CC | Per-source (CC0 yes) | Per-source | Points back to source files | Secondary CC aggregator / discovery |
| **Internet Archive** | Yes — Metadata + Search API (open) | None | Huge, heterogeneous | Per-item | Per-item (much PD/CC) | Per-item | FLAC/MP3/WAV | Public-domain long-tail |
| **BBC Sound Effects** | No (web only) | — | 33,000+ (16,000 as WAV) | **No — non-commercial only (RemArc)** | No | N/A (non-commercial) | WAV 44.1 kHz/16-bit | Non-commercial/demo only; commercial via PSE |
| **Epidemic Sound** | Yes — **Partner Content API** (partner-only) | API key / ES Connect OAuth | 250,000+ SFX | Yes, tied to active subscription | No (no local caching allowed) | Rights-cleared | MP3 only (128/320 kbps) via API | Deferred partner integration |
| **Storyblocks** | Yes — **Stock Media API** (enterprise) | HMAC-SHA256 | ~42,800 SFX | Yes ($20k indemnification) | No (must be in finished project) | Not required | WAV 24-bit/44.1 kHz + MP3 320 | Deferred partner integration |
| **Pond5** | Yes — **Partner/reseller API** | Partner key | Tens of millions (mixed media) | Yes, per-item royalty-free | No | Per-item | WAV/MP3 | Deferred partner integration |
| **Pro Sound Effects** | **Enterprise data-license API/bulk** only | Contact-sales | 1.27M–3.5M pro files, 660+ categories | Yes; **AI/ML only via separate license** | Only via negotiated data license | No (buyout) | Broadcast WAV (typ. 24-bit/96 kHz) | Enterprise/AI-dataset partner |
| **Zapsplat** | **No (automation prohibited)** | — | 150,000+ SFX | Yes | No | Yes (free); none (Gold) | MP3 (free), WAV (Gold) | Link-out only |
| **Soundly** | No (desktop app + DAW plugins) | — | 3,000 free / ~100k Pro | Yes | No (no reselling as-is/modified) | No | Broadcast WAV (in-app) | Link-out only; UCS reference |
| **Pixabay (audio)** | **No — API is images/video only** | API key (non-audio) | Large on-site audio | Yes (Content License) | No (no standalone redistribution) | No | MP3 (site) | Scrape/link-out only |
| **Mixkit** | No | — | Free SFX (Envato) | Yes | No (no standalone resale) | No | WAV/MP3 (site) | Link-out only |
| **Uppbeat** | **No (automation prohibited)** | — | Free + Premium SFX | Yes | No (dataset/AI training barred) | Free tier: yes; Premium: no | MP3/WAV (site) | Link-out only |
| **Boom Library** | No (curated packs) | — | Themed packs | Yes | No | No | WAV 24-bit/96 kHz | Purchased local packs |
| **Sonniss GameAudioGDC** | No (bulk download) | — | ~160–200 GB cumulative | Yes (royalty-free) | No (raw resale barred); **AI training barred** | No | Hi-res WAV (specs vary) | **Bulk starter corpus (local)** |
| **FSD50K** | No (dataset download) | — | 51,197 clips / 108.3 h | ~85% (CC0/BY); filter out CC-BY-NC | Yes w/ per-clip license | Per-clip | 16-bit/44.1 kHz mono WAV | **Labeled starter corpus (local)** |
| **AudioSet** | No (labels + YouTube IDs) | — | 2.08M clips (labels only) | Labels only; audio = uploaders' copyright | Labels yes; audio no | Labels: CC-BY | No audio shipped | **Ontology + weak labels** |

---

## Programmable, self-serve APIs (the ones foley can actually call today)

### Freesound — the primary programmable CC library

Freesound (Music Technology Group, Universitat Pompeu Fabra) is the anchor: a documented, self-serve REST API over 600,000+ Creative-Commons sounds, with per-sound licensing that *includes CC0* — the only combination in this whole survey that is both programmable **and** legally redistributable. [1][3][4]

- **Base URL:** `https://freesound.org/apiv2/`. Register for an API key at `https://freesound.org/apiv2/apply`. [1]
- **Auth:** *Token auth* (pass `token=<API_KEY>` as a query param) is sufficient for search, metadata, analysis, and **preview** downloads. **OAuth2 is required to download the original (full-quality) file**, and also to upload/describe/rate/comment/bookmark. Downloading also requires a registered Freesound account. [1][4]
- **Key endpoints** [2]:
  - `GET /apiv2/search/` — text/metadata search. *(Note: this replaced the older `/apiv2/search/text/`, deprecated November 2025.)*
  - `GET /apiv2/sounds/<id>/` — full sound instance metadata.
  - `GET /apiv2/sounds/<id>/analysis/` — content-based descriptors + similarity vectors.
  - `GET /apiv2/sounds/<id>/similar/` — acoustically similar sounds.
  - `GET /apiv2/sounds/<id>/download/` — original file (**OAuth2 required**).
- **Search parameters** [2]: `query` (supports `+`mandatory / `-`prohibited terms), `filter` (Apache Solr syntax, e.g. `filter=tag:guitar duration:[0.0 TO 15.0] license:"Creative Commons 0"`), `sort` (`score`, `duration_asc/desc`, `created_asc/desc`, `downloads_asc/desc`, `rating_asc/desc`), `fields` (comma-separated field selection), `group_by_pack`, `page`, `page_size` (default 15, **max 150**). Content/similarity search via `similar_to` and `similarity_space` — either `laion_clap` (512-dim CLAP embedding) or `freesound_classic` (100-dim). The CLAP space makes **text→audio semantic retrieval** possible, which is directly useful for "find the right sound for this narrative beat."
- **Returnable fields** [2]: default `id, name, tags, username, license`; also `url, description, duration, channels, filesize, samplerate, bitdepth, type, num_downloads, avg_rating, geotag, created`, `previews`, `analysis`/`ac_analysis`, and (see below) `bst_category`. Over 70 audio descriptors are available (`mfcc`, `hpcp`, `pitch`, `bpm`, `spectral_centroid`, `loudness`, `onset_times`, `beat_times`, …).
- **Previews vs. originals** [2]: the `previews` object gives `preview-hq-mp3` (~128 kbps), `preview-lq-mp3` (~64 kbps), `preview-hq-ogg` (~192 kbps), `preview-lq-ogg` (~80 kbps). Previews need only token auth; originals need OAuth2 and come back in the uploaded format (`.wav/.aif/.flac/.ogg/.mp3`).
- **Licenses** [4]: per-sound **CC0 1.0**, **CC-BY 4.0** (Attribution), **CC-BY-NC 4.0** (Attribution-NonCommercial), plus a legacy **CC Sampling+** on older uploads. Because the license is per-sound, foley must **capture and store the license with every retrieved sound** and filter by it (e.g., `license:"Creative Commons 0"` for a redistributable/commercial-safe subset).
- **Category taxonomy** [5]: Since April 2025 Freesound assigns every sound a **Broad Sound Taxonomy (BST)** category (5 top-level, 23 second-level categories), exposed as the `bst_category` search facet/field. This is *not* UCS, but it is a clean coarse axis foley can map onto UCS CatIDs.
- **Rate limits** [1]: **60 requests/min and 2,000/day** for standard resources; 30/min and 500/day for restricted write operations. Throttled requests return **HTTP 429**. Higher limits available on request (email the MTG admins).
- **Official client:** `freesound-python` (MTG) maps function args to HTTP params and augments `Sound`/`User`/`Pack` objects with API calls; it supports token auth for search/previews and accepts an OAuth2 access token for original downloads (you implement the OAuth flow). [6] foley can wrap or reimplement this thin layer.

### Openverse — CC audio aggregator

Openverse (a WordPress Foundation project) is an open, free REST API indexing 1M+ CC/PD audio records aggregated from **Freesound, Jamendo, and Wikimedia Commons** — so most SFX coverage flows through Freesound, but with a single normalized schema and license-filter interface. [7][10]

- **Base URL:** `https://api.openverse.org/v1/`; the audio endpoint is `GET /v1/audio/`. Anonymous access works; register (`POST /v1/auth_tokens/register/`) and obtain an OAuth2 client-credentials token (`POST /v1/auth_tokens/token/`) for higher throttling tiers. [7][9]
- **License filtering** [7]: `license=cc0,by,by-nc,...` and `license_type=commercial|modification` — first-class support for exactly the constraint foley needs.
- **Audio metadata** [8]: `duration`, `sample_rate`, `bit_rate`, `filesize`, `filetype`, `alt_files`, `category` (values include `sound_effect`, `music`, `podcast`), `genres`, `tags`, `audio_set`, `thumbnail`, plus `license`, `creator`, `source`, `provider`. Download URLs point back to the source; you must honor each source's CC terms.
- **Rate limits** [9]: tiered (anonymous / authenticated "standard" / selectively granted "enhanced"); exact per-hour/day numbers were not reproducible from the docs pages reachable on the access date — verify in the API reference. *(Uncertain.)*
- **Role for foley:** a convenient normalized fallback/aggregator, but since it largely re-indexes Freesound, direct Freesound access remains richer (analysis descriptors, similarity spaces).

### Internet Archive — public-domain long tail

The Internet Archive exposes an open **Metadata Read API** (`https://archive.org/metadata/<id>`, JSON) and an **Advanced Search API** for discovery; audio items carry FLAC/MP3/WAV. [11] Licenses vary **per item** (much is public-domain or CC, but not uniformly), so each item must be license-checked. Not a curated SFX library — useful for public-domain and archival material, weaker for precise foley cueing.

### SoundBible — small CC/PD library, no API

SoundBible has **no developer API** (web download only). Files are WAV or MP3; the catalog mixes **CC-BY** and **Public Domain** sounds (commercial use permitted with attribution where the CC-BY items require it). [12] Only usable programmatically by scraping; low priority.

---

## Partner / enterprise APIs (real APIs, gated behind agreements)

### Epidemic Sound — Partner Content API ("Epidemic Sound Connect")

A genuine, well-documented REST API — but **partner-only**; production/commercial use needs a partnership agreement, with a free tier for prototyping. [13][14]

- **Base URL:** `https://partner-content-api.epidemicsound.com`; OpenAPI spec at `.../docs/spec.json`. [15]
- **Auth (three schemes)** [14][15]: `ApiKeyAuth` (server-side, recommended), `EpidemicSoundConnectAuth` (OAuth-style tokens tying an end-user's Epidemic subscription to your app), and `UserAuth`.
- **SFX endpoints** [15]: `GET /v0/sound-effects/search` (`term` required, `limit` ≤60, `offset`, `sort` = best-match|newest|popular|length|title, `order`, `includeExplicit`); `.../collections`, `.../categories`, `.../categories/{id}/tracks`, and `GET /v0/sound-effects/{trackId}/download`. Music endpoints add AI tooling (video→music "Soundmatch," semantic search, similar-section, beat detection).
- **Catalog** [13][15]: 55,000+ music tracks and **250,000+ sound effects across ~300 categories**.
- **License** [14]: rights-cleared, but entitlement is **tied to an active subscription** surfaced via ES Connect (free tier = personal license; paid connected users = commercial license). **Partners may not cache metadata/tracks locally** — a hard blocker for a persisted foley corpus.
- **Formats** [15]: **MP3 only via the API** (128 kbps "normal" / 320 kbps "high"); download URLs are short-lived (≈24 h / 1 h). Metadata: `id` (UUID), `title`, `added`, `length` (s), multi-size `images`, category hierarchy with counts.
- **Pricing** [16]: API Free tier = up to 50 downloads, non-commercial, "prototyping only"; Scale and Enterprise tiers are custom/contact-sales.

### Storyblocks — Stock Media API

A production REST API (used by Descript, Magix, Clipchamp) covering video, images, and audio (music + SFX). Free self-serve **test keys**; production access is enterprise. [17][18]

- **Base URL:** `https://api.storyblocks.com` (one domain for all media). **Auth: HMAC-SHA256** — each request carries `APIKEY` (public key), `EXPIRES` (Unix epoch, ≤36 h ahead), and `HMAC` (SHA-256 over the resource path, keyed by `secretKey + expiration`). [18]
- **Catalog** [20]: ~45,125 music tracks + **~42,790 sound effects** (as of access date), categorized by mood/style.
- **License** [17][19]: 100% royalty-free, commercial use, **$20,000 indemnification, no attribution required**, license survives cancellation — **but no standalone redistribution** ("cannot distribute, resell, or otherwise provide the source files on a stand-alone basis; must be incorporated into a finished project"). API partners may pass content to end-customers subject to compliance review.
- **Formats** [19]: **WAV 24-bit/44.1 kHz and MP3 320 kbps** — the best format quality among the partner APIs. Test keys allow ~5 downloads per content type, unlimited search.

### Pond5 — partner/reseller API

Pond5's API gives partners/resellers/affiliates programmatic search+retrieval across "the world's largest catalogue" of royalty-free video, music, images, **sound effects**, motion graphics, and 3D models; it powers third-party sites' search. [21] It is a **partner integration**, not open self-serve (apply via the API portal). Licensing is per-item royalty-free (individual purchase); standalone redistribution of raw files is not part of the model. Endpoint/param specifics live behind the developer portal (not publicly documented at the access date). *(Details uncertain.)*

### Pro Sound Effects — enterprise data license (incl. AI/ML)

A professional/enterprise vendor whose **standard** store EULA forbids automated retrieval and AI training, but which separately offers a **rights-cleared data license delivered by "API, bulk download, or custom delivery"** for ML/AI teams. [22][23]

- **Dataset** [22]: **1.27M rights-cleared sounds** core, up to **~3.5M total files** (SFX + music + speech), 5,000+ hours, ~5.8 TB, **660+ categories**, professionally recorded, human-tagged, **UCS metadata**, Soundminer workflow.
- **Standard license** [23]: perpetual buyout (single-user) or subscription; commercial use yes; **redistribution and AI/ML training prohibited** (subscriber cap 10,000 downloads/month). Corpus/AI use requires the separate ML data license. Pricing is contact-sales. Also the **commercial licensor for BBC Sound Effects** (see below).

---

## Non-commercial archive

### BBC Sound Effects (RemArc license)

The BBC Sound Effects archive (`sound-effects.bbcrewind.co.uk`) offers **33,000+** effects for streaming and **16,000 as downloadable WAV (44.1 kHz / 16-bit)** under the **RemArc license**. [37][38]

- **RemArc terms** [37][38]: use permitted only for **personal, educational, or research** purposes; **commercial use is excluded** (e.g., cannot be sampled into music that is sold); also prohibits political/social-campaigning and fundraising use. No API or bulk-download mechanism — web download only.
- **Commercial path:** the BBC delegates **commercial licensing to Pro Sound Effects** (per-sound "Buy sound"). [37][22]
- **Role for foley:** excellent for demos/prototypes and non-commercial narration, but it must be **flagged non-commercial** in foley's license model and never leak into a commercial pipeline. Files are *not* UCS-named.

---

## Web libraries with no content API (link-out / scrape only)

These are popular but **cannot be adapters in the programmatic sense** — no API, and their licenses forbid standalone redistribution (several forbid automation outright). foley should treat them as *pointer* sources (surface a search URL / attribution guidance) rather than fetch-and-store backends.

- **Zapsplat** — **No API; automated/scripted access explicitly prohibited.** 150,000+ SFX. Standard (free) license permits commercial use **with attribution** ("ZapSplat" + link) and caps free downloads at ~4/hour (MP3); **Gold** (~£4/mo or ~£30/yr) removes attribution and adds WAV. **No redistribution / no soundboard-style apps.** A subset is also offered under CC-BY 4.0. [24][25] *(Pricing/format specifics from indexed reads; site blocks automated fetch.)*
- **Soundly** — Desktop app + DAW/NLE plugins, **no public REST API**. Free library 3,000 SFX; Pro cloud library (marketed ~100k; exact count uncertain), $14.99/mo (or $12.49/mo annual). Sounds are cleared for commercial use and stay cleared after cancellation, **but "must be used as part of a project with other media" and cannot be resold as-is or modified**. Notably a reference **UCS adopter** (in-app UCS support). [26][27]
- **Pixabay (audio)** — **The Pixabay API serves images and video only; there is no audio endpoint.** [28] (The image/video API uses an API-key query param and is rate-limited to 100 requests/60 s. [29]) The **Pixabay Content License** is royalty-free, no attribution, commercial OK, but **no standalone redistribution**. [30] So Pixabay SFX can be used via manual/site download but not fetched via API nor redistributed as a corpus.
- **Mixkit** (Envato) — **No API.** Free license: commercial + personal, **no attribution, unlimited free downloads, no sign-up**, but **no standalone resale / no competing stock service / no third-party redistribution**. [31][32]
- **Uppbeat** — **No API; running scripts/automation to download is explicitly forbidden** (auto-pauses above ~500 items/mo). Free tier requires an "Uppbeat credit"; Premium (Essentials/Creator/Pro) removes credit and adds Content-ID safelisting. **Dataset compilation and AI-model training explicitly restricted.** [33][34]
- **Boom Library** — **No API**; sells curated themed packs (typ. WAV 24-bit/96 kHz). Single-user media license by default, multi-user (MULA) on request, as buyout or time-limited subscription; commercial use yes; **no redistribution of raw source files.** [35][36] A **UCS metadata** adopter in recent releases.

---

## Free bulk corpora (foley's local starter library)

These are the best way to seed foley with real, on-disk audio without any API — download once, index locally.

### Sonniss #GameAudioGDC bundles — bulk production SFX

Annual free royalty-free SFX bundles Sonniss releases around GDC, contributed by independent vendors. The cumulative multi-year archive is **~160–200 GB** of high-resolution WAV (per-year drops are smaller, e.g. GDC 2015 ≈10.3 GB/646 files; a recent-year bundle ≈7–12 GB). Ten annual bundles are listed on the archive hub, each with HTTP downloads, a mirror, and an official BitTorrent file. [39][41]

- **Download:** archive hub `https://sonniss.com/gameaudiogdc/` (all past years); current year `https://gdc.sonniss.com/`; Internet Archive mirrors exist. [39][41]
- **License** [40]: royalty-free, **commercial use OK, no attribution, unlimited projects for life** — but **raw files may not be sold "as they come"** (only embedded in a finished project), and, critically, **using the sounds to train AI is expressly prohibited.** This AI-training ban is the single most important caveat: Sonniss can seed a **human-facing retrieval/playback** library but must never be fed into model training, and never re-exposed as standalone downloads.
- **Format/naming:** hi-res WAV (specs vary by vendor; read from headers). Organized in **per-vendor folders, not UCS-named** — foley must tag/map onto UCS itself.

### FSD50K — labeled, redistributable seed corpus

The Freesound Dataset 50K (MTG/UPF) is the best *labeled and redistributable* seed: **51,197 clips / 108.3 hours**, drawn from Freesound and labeled with **200 classes from the AudioSet Ontology** (144 leaf + 56 intermediate). [42][43]

- **Download:** Zenodo record `https://zenodo.org/records/4060432` (DOI `10.5281/zenodo.4060432`); also mirrored on Hugging Face. No login. **Format:** 16-bit / 44.1 kHz **mono WAV**.
- **License** [42][43]: dataset overall **CC-BY 4.0**; **per-clip** licenses vary (CC0 / CC-BY / CC-BY-NC / Sampling+), with **≈85% CC0 or CC-BY** (safe for commercial after filtering out the ~12% CC-BY-NC). Per-clip license ships in the metadata, so filtering is trivial.
- **Metadata:** ground-truth `dev.csv`/`eval.csv` (multi-label, with AudioSet MIDs), `vocabulary.csv` (the 200 classes), rich per-clip info (Freesound ID, tags, title, license, uploader). Unlike raw Sonniss, FSD50K is explicitly a research dataset and is fine for building/evaluating retrieval models.

### AudioSet — ontology + weak labels (not an audio source)

Google's AudioSet is **2,084,320 10-second clips (~5,900 h)** — but **it ships labels + YouTube video IDs + timestamps only, no audio.** [44] To get audio you must scrape each YouTube video yourself (link-rot removes a large fraction; the underlying videos carry their own copyrights; ToS gray area). Its real value to foley is the **AudioSet Ontology**: a hierarchical graph of **632 audio-event classes** (527 used in the released labels), published as `ontology.json` with `id` (MID), `name`, `description`, `child_ids`, and example segments. [45][46]

- **License** [44][45]: ontology **CC-BY-SA 4.0**; labels/segment CSVs **CC-BY 4.0**; the **audio is not covered** (belongs to uploaders).
- **Role for foley:** use the ontology as a **weak-label / cross-walk reference** (map AudioSet classes ↔ UCS CatIDs), not as a file source.

---

## The Universal Category System (UCS) — foley's canonical category vocabulary

**UCS is the industry-standard, open, public-domain taxonomy and filename convention for sound effects** — a controlled vocabulary that standardizes how SFX are categorized and named so libraries interoperate across tools and vendors. [47][49] It was initiated by **Tim Nielsen**, **Justin Drury** (Soundminer), **Kai Paquin**, and others, and is **free for anyone to adopt** (owned by no vendor). [47][48]

- **Current version:** **v8.2.1 (January 2024)** — a minor fix on v8.2 (Feb 2023), which the authors billed as the "final planned" major version. [47][48]
- **Structure:** three levels — **Category → SubCategory → CatID**. The **CatID** is a short abbreviation uniquely encoding a Category/SubCategory pair (Category in ALL CAPS, SubCategory in Title Case), e.g. `GUNMech`, `ELECBuzz`, `WOODHndl`. UCS 8.2 has **82 top-level categories and ~753 subcategories** (thus ~700+ CatIDs); each entry ships with explanations and **synonyms**. [50][51] *(82/753 are widely cited but not read off the official spreadsheet directly — treat as ±a few.)*
- **Filename schema** [50][51]: underscore-delimited, CatID first —
  ```
  CatID_FXName_CreatorID_SourceID.wav
  ```
  where **FXName** is a brief free-text description (~25 chars), **CreatorID** is the designer/recordist/vendor short code, and **SourceID** is the library/project. Optional trailing fields (UserCategory, VendorCategory, UserData: mic, date, sample rate, channels) may be appended. Real example: `GUNMech_Ak47-Layer 4_aXL_MtSw.wav`.
- **Where to get it:** `https://universalcategorysystem.com/` — free master spreadsheet + **~20 translations** (Dropbox/Drive repository linked from the site). [47]
- **Adoption:** Soundminer (deepest integration), **Soundly**, **BaseHead**, Steinberg MediaBay (Cubase/Nuendo), **Pro Sound Effects** (formally adopted), **BOOM Library**, and many independent vendors + the A Sound Effect marketplace. [49][52] There is even a recent arXiv paper on unifying SFX datasets onto UCS (arXiv:2606.05571) — worth mining for mapping methodology. [53] *(Existence confirmed; not read in full.)*

**Why foley should adopt UCS as its canonical category axis:**

1. **Lingua franca / interoperability.** UCS is the de-facto professional standard. If foley normalizes every sound onto a UCS CatID, its output files and metadata drop straight into Soundminer/Soundly/BaseHead workflows, and any UCS-named library (PSE, BOOM, many vendors) merges cleanly.
2. **A single mapping target for heterogeneous tags.** foley's sources speak different vocabularies — Freesound uses the **Broad Sound Taxonomy** (`bst_category`) + free tags, FSD50K uses the **200-class AudioSet subset**, AudioSet uses its **632-class ontology**, Sonniss uses **per-vendor folder names**, and web libraries use ad-hoc categories. UCS gives one controlled vocabulary onto which all of these can be mapped (AudioSet class → CatID, vendor folder → CatID, free tag → CatID via UCS's **synonym lists**, which directly aid fuzzy matching).
3. **Filename-as-metadata robustness.** The `CatID_…` scheme survives format conversion, storage moves, and tools that strip embedded metadata — important for a `dol`-based pipeline that shuffles files across storage backends.
4. **Free, stable, permanent.** Public-domain, declared "final," actively used — negligible adoption risk.

---

## Recommendations for foley

### 1. Which sources to build adapters for first

Prioritize by *(programmable now) × (redistribution/commercial clarity) × (retrieval quality)*:

- **Tier 1 — build first (the retrieval core):**
  - **Freesound APIv2** — the anchor. Documented, self-serve, rich metadata + audio descriptors, CLAP semantic search (`similarity_space=laion_clap`), and — filtered to **CC0** — the one source that is both programmatic and freely redistributable. Implement token-auth search/preview first; add OAuth2 original-download as a second step.
  - **FSD50K** (local corpus) — labeled, redistributable, model-trainable; ideal for building/evaluating foley's own retrieval and for an offline default library. Filter out CC-BY-NC for commercial use.
  - **Sonniss GameAudioGDC** (local corpus) — high production quality for a human-facing library. **Hard-flag it `ai_training=forbidden` and `redistribute=forbidden`** so it can never leak into training or standalone re-download.
  - **BBC Sound Effects** (local, non-commercial) — great breadth for demos; **hard-flag `commercial=forbidden` (RemArc)**.
- **Tier 2 — CC aggregators / long tail:** **Openverse** (normalized CC audio index; license-filterable) and **Internet Archive** (public-domain long tail). Both are open APIs; low effort, good coverage extension.
- **Tier 3 — partner/enterprise (defer behind agreements, stub the adapter now):** **Epidemic Sound** (Partner Content API — note *no local caching* and MP3-only), **Storyblocks** (HMAC API, best WAV quality), **Pond5** (reseller API), **Pro Sound Effects** (enterprise data license, incl. the only clearly AI/ML-cleared corpus). Design the adapter interface so these slot in when a partnership exists.
- **Tier 4 — link-out only (no adapter):** **Zapsplat, Soundly, Pixabay-audio, Mixkit, Uppbeat, Boom.** No API and/or redistribution/automation forbidden. Surface these as *pointers* (a search URL + attribution/credit guidance) but never fetch-and-store.

> The AI-generation source that arioso represents becomes just *one more Tier-1/2 source* in foley — retrieval is primary, generation is a fallback when no retrieved sound fits.

### 2. Track license per-sound (this is non-negotiable, not an afterthought)

Because licensing is **per-sound and heterogeneous** (Freesound and FSD50K mix CC0/BY/BY-NC/Sampling+ within a single query; Sonniss forbids AI training; BBC forbids commercial use), every retrieved item must carry a normalized license record, stored as a **sidecar next to the audio** in a `dol` store (e.g., a JSON manifest keyed by the same key as the audio blob). A minimal, filterable schema:

```python
# one record per sound, stored alongside the audio blob in a dol store
LicenseRecord = {
    "source": "freesound",  # which adapter produced it
    "source_id": "12345",  # id within that source
    "source_url": "https://freesound.org/s/12345/",
    "license_id": "CC0-1.0",  # SPDX-style where possible;
    # else "RemArc", "Sonniss-GDC", "Proprietary"
    "attribution": "user 'foo' — freesound.org/s/12345",  # ready-to-print credit line
    "commercial_ok": True,  # derived flags for cheap query-time filtering
    "redistribute_ok": True,  # standalone redistribution allowed?
    "ai_training_ok": True,  # may this feed a training pipeline?
    "requires_attribution": False,
    "retrieved_at": "2026-07-22T...",
}
```

Design consequences:
- **Filter at query time on the derived boolean flags**, so a caller can request, e.g., "commercial-safe, redistributable, no-attribution" and foley composes the right per-source query (Freesound `license:"Creative Commons 0"`, FSD50K `license in {CC0, CC-BY}`, exclude BBC/Sonniss for AI, etc.).
- **Normalize to a small controlled license vocabulary** (SPDX ids for CC; named ids for the bespoke ones: `RemArc`, `Sonniss-GDC`, `Pixabay-Content`, `Proprietary-<vendor>`). Keep a table mapping each license id → the flag set, so adding a source is "declare its default license id(s)," not "rewrite filtering logic."
- **Never discard provenance.** Store `source`, `source_id`, `source_url`, and the ready-to-use attribution string so foley (or a downstream narration renderer) can emit a correct credits list automatically.

### 3. Shape of a `source adapter` plugin (mirroring arioso's platform config)

arioso auto-discovers each backend as a package under `arioso/platforms/<name>/` containing a `config.py` with a `PLATFORM_CONFIG` dict (name, auth, `param_map` translating a unified vocabulary → native params, `supported_affordances`, `output`, `api`) plus an `adapter.py`; a registry scans the package, lazily loads adapters, and offers `register_platform()` for third-party plugins. foley should mirror this exactly, swapping the *generation* vocabulary for a *retrieval* one and adding a first-class **license** block.

Proposed layout: `foley/sources/<name>/{config.py, adapter.py, __init__.py}`, auto-discovered by a `foley/sources/registry.py` (config.py must define `SOURCE_CONFIG`), lazily loaded, with `register_source()` for out-of-tree adapters. A source config:

```python
# foley/sources/freesound/config.py
SOURCE_CONFIG = {
    "name": "freesound",
    "display_name": "Freesound",
    "website": "https://freesound.org",
    "access_type": "rest_api",  # rest_api | partner_api | bulk_corpus | scrape | no_api
    "auth": {
        "type": "api_key",  # api_key | oauth2 | hmac | none
        "env_var": "FREESOUND_API_KEY",
        "query_param": "token",
        "download_requires": "oauth2",  # original-file download needs OAuth2
    },
    "dependencies": ["requests"],
    "optional_dependencies": ["freesound"],  # official MTG client
    "capabilities": [
        "search",
        "text_similarity",
        "similarity",
        "preview",
        "download",
        "analysis",
    ],
    # unified retrieval vocabulary -> this source's native search params
    "query_map": {
        "text": {"native_name": "query"},
        "max_results": {"native_name": "page_size", "native_default": 15},  # max 150
        "duration_range": {
            "native_name": "filter",
            "to_native": lambda lo, hi: f"duration:[{lo} TO {hi}]",
        },
        "license": {
            "native_name": "filter",
            "to_native": lambda lic: f'license:"{LICENSE_TO_FREESOUND[lic]}"',
        },
        "sort": {"native_name": "sort", "native_default": "score"},
        "semantic_text": {
            "native_name": "similarity_space",
            "native_default": "laion_clap",
        },
    },
    # how to resolve the license of each returned item (per-sound here)
    "license": {
        "per_item": True,  # license varies by sound; read from the 'license' field
        "field": "license",
        "default_id": None,  # no single default; resolved per item
    },
    "output": {
        "formats": ["wav", "aiff", "flac", "ogg", "mp3"],
        "preview_formats": ["mp3", "ogg"],
    },
    "api": {
        "base_url": "https://freesound.org/apiv2",
        "search_endpoint": {"method": "get", "path": "/search/"},
        "instance_endpoint": {"method": "get", "path": "/sounds/{id}/"},
        "download_endpoint": {"method": "get", "path": "/sounds/{id}/download/"},
    },
    "rate_limits": {"per_minute": 60, "per_day": 2000},
}
```

The `adapter.py` implements a small `SourceAdapter` protocol — `search(query) -> list[SoundResult]`, `get(id) -> SoundMetadata`, `download(id) -> bytes|path`, and optionally `similar(id)` / `preview(id)` — with a `BaseRestAdapter` (à la arioso) providing the shared session/auth/pagination plumbing. Every `SoundResult` carries the normalized **`LicenseRecord`** (§2) and a **canonical UCS CatID** (§UCS), computed by mapping the source's native category/tags via a shared `tags→CatID` resolver that leans on UCS synonyms. Bulk-corpus "sources" (FSD50K, Sonniss, BBC) implement the *same* protocol over a local `dol` store instead of HTTP, so the caller sees one uniform `search/get/download` interface whether the audio is remote, cached, or purely local.

This yields arioso's progressive-disclosure UX for retrieval: a one-call `foley.find_sound("distant thunder rumble", commercial_ok=True)` that fans out across enabled sources, filters by license flags, ranks by relevance (text + CLAP similarity), and returns license-clean, UCS-categorized results — with each new source added by dropping in a `config.py` + thin `adapter.py`, no changes to the core.

---

## REFERENCES

1. [Freesound APIv2 — Overview (base URL, auth, rate limits, apply for key)](https://freesound.org/docs/api/overview.html)
2. [Freesound APIv2 — Resources (endpoints, search params, fields, descriptors)](https://freesound.org/docs/api/resources_apiv2.html)
3. [Freesound API documentation — index](https://freesound.org/docs/api/)
4. [Freesound — Frequently Asked Questions (licenses, downloads)](https://freesound.org/help/faq/)
5. [Introducing the Broad Sound Taxonomy — The Freesound Blog](https://blog.freesound.org/?p=2206)
6. [freesound-python — official MTG client (GitHub)](https://github.com/MTG/freesound-python)
7. [Openverse API — Reference (base URL, audio endpoint, license filters)](https://api.openverse.org/v1/)
8. [Openverse — API Media Properties (audio fields)](https://docs.openverse.org/meta/media_properties/api.html)
9. [Openverse — Authentication and Throttling](https://docs.openverse.org/api/reference/authentication_and_throttling.html)
10. [Openverse Now Includes Over 1 Million Audio Records (sources)](https://make.wordpress.org/openverse/2022/11/16/openverse-now-includes-over-1-million-audio-records/)
11. [Internet Archive — Item Metadata API (developer portal)](https://archive.org/developers/metadata.html)
12. [SoundBible — About (WAV/MP3, CC + Public Domain)](https://soundbible.com/about.php)
13. [Epidemic Sound — Developers portal](https://developers.epidemicsound.com/)
14. [Epidemic Sound Connect — Partner API documentation (auth, caching policy)](https://developers.epidemicsite.com/docs/)
15. [Epidemic Sound — Partner Content API OpenAPI spec (endpoints, params, formats)](https://partner-content-api.epidemicsound.com/docs/spec.json)
16. [Epidemic Sound — Try the API Free tier (blog)](https://www.epidemicsound.com/blog/free-api/)
17. [Storyblocks — Stock Media API (business solutions)](https://www.storyblocks.com/resources/business-solutions/api)
18. [Storyblocks — API Reference documentation (HMAC auth, base URL)](https://documentation.storyblocks.com/)
19. [Storyblocks — Audio file specifications (WAV 24-bit/44.1 kHz, MP3 320 kbps)](https://help.storyblocks.com/en/articles/3622329-what-are-the-specifications-of-your-audio-files)
20. [Storyblocks — Audio library (SFX/music counts)](https://www.storyblocks.com/audio)
21. [Pond5 — API (partner/reseller integration)](https://www.pond5.com/api)
22. [Pro Sound Effects — Audio Dataset for Machine Learning & AI](https://www.prosoundeffects.com/machine-learning-ai)
23. [Pro Sound Effects — Sound Effects Licensing](https://www.prosoundeffects.com/licensing)
24. [ZapSplat — Standard License Agreement](https://www.zapsplat.com/license-type/standard-license/)
25. [ZapSplat — FAQ (automation prohibition, tiers, formats)](https://www.zapsplat.com/faq/)
26. [Soundly — Subscription differences (FAQ)](https://getsoundly.com/faq/what-are-the-differences-between-the-subscriptions/)
27. [Soundly — Can I use the sounds commercially? (FAQ)](https://getsoundly.com/faq/how-can-i-use-the-sounds/)
28. [Pixabay — API Documentation (images & video only)](https://pixabay.com/api/docs/)
29. [Pixabay — About the API (rate limits)](https://pixabay.com/service/about/api/)
30. [Pixabay — Content License / License Summary](https://pixabay.com/service/license-summary/)
31. [Mixkit — Terms / License](https://mixkit.co/terms/)
32. [Mixkit — Free Sound Effects](https://mixkit.co/free-sound-effects/)
33. [Uppbeat — User Agreement (automation, dataset/AI restrictions)](https://uppbeat.io/user-agreement)
34. [Uppbeat — Pricing](https://uppbeat.io/pricing)
35. [BOOM Library — Terms & Conditions (media license)](https://www.boomlibrary.com/terms-conditions/)
36. [BOOM Library — How many licenses do I need? (single/multi-user)](https://www.boomlibrary.com/support/faq/how-many-licenses-do-i-need/)
37. [BBC Sound Effects — Licensing (RemArc)](https://sound-effects.bbcrewind.co.uk/licensing)
38. [Avosound — RemArc License (BBC Sound Effects terms summary)](https://www.avosound.com/en-us/licensing/remarc-license)
39. [Sonniss — GameAudioGDC archive (all yearly bundles + torrents)](https://sonniss.com/gameaudiogdc/)
40. [Sonniss — #GameAudioGDC Bundle License](https://sonniss.com/gdc-bundle-license/)
41. [Sonniss — GDC current-year Game Audio Bundle](https://gdc.sonniss.com/)
42. [FSD50K — Zenodo record 4060432 (files, splits, per-clip licenses)](https://zenodo.org/records/4060432)
43. [FSD50K: an Open Dataset of Human-Labeled Sound Events — Fonseca et al., arXiv:2010.00475](https://arxiv.org/abs/2010.00475)
44. [AudioSet — Google Research (download page: CSVs, splits, license)](https://research.google.com/audioset/dataset/index.html)
45. [AudioSet Ontology (ontology.json, entry structure, CC-BY-SA 4.0) — GitHub](https://github.com/audioset/ontology)
46. [Audio Set: An ontology and human-labeled dataset for audio events — Gemmeke et al., ICASSP 2017](https://ieeexplore.ieee.org/document/7952261/)
47. [Universal Category System — official site](https://universalcategorysystem.com/)
48. [Tim Nielsen releases the final version of the UCS — A Sound Effect](https://www.asoundeffect.com/universal-category-system-final-version/)
49. [UCS – Universal Category System — Soundminer (adoption list)](https://store.soundminer.com/blogs/news/ucs-universal-category-system)
50. [Universal Category System information (CatID + filename schema) — aXLsound](https://axlsound.com/ucs-info/)
51. [Understanding the Universal Category System (UCS) — Neil Spencer Bruce](https://www.spencerbruce.com/blog1/2025/10/3/understanding-the-universal-category-system-ucs)
52. [Pro Sound Effects Library to Adopt the Universal Category System — PSE blog](https://blog.prosoundeffects.com/universal-category-system-announcement)
53. [Sound Effects Dataset Unification With the Universal Category System — arXiv:2606.05571](https://arxiv.org/abs/2606.05571)
