# 14 — SFX search, library and corpus targets, client libraries, and the shared vocabulary

Date: 2026-10-03. Scope: SFX *retrieval* targets (search APIs, stores, local library apps, research corpora) and the Python / JS / MCP clients that reach them. Generation targets are out of scope. This is a DELTA on foley's July 2026 research: foley report 01 (sources) [1], report 07 (licensing) [2] and report 11 (corpora) [3]. Anything those reports already established is cited, not re-derived. Claims marked **(unverified)** were not confirmed against a primary source on the access date.

## Summary

1. **Freesound is still the anchor, but foley's adapter calls a deprecated endpoint.** `/apiv2/search/text/` was deprecated in November 2025 in favour of `/apiv2/search/` [4]. foley's config still points at the old path, while the MTG client has already moved [9].
2. **Freesound's `gen_ai_preference` field has four values** [4][7]: `no-additional-preferences`, `open-source-models`, `noncommercial-open-source-models` and `no-gen-ai`. foley honours only `no-gen-ai`. For a commercial film, `noncommercial-open-source-models` should block as well.
3. **The Freesound API terms say commercial use of the API "will be negotiated on a case by case basis with UPF"** [6]. Only "limited intermediate copies" may be kept [6]. That supports `cache_bytes_ok=False`, but it also means a commercial production pipeline built on the API needs a word with UPF. The sounds' own CC licences are a separate question.
4. **Openverse is keyless and returns rich licence data, but it is weak as an SFX source.** Live tests showed the following [14][17]:
   - Its Freesound records are a 2024–25 snapshot.
   - `category=sound_effect` returns 0 hits for Freesound content, because its `category` is null.
   - Anonymous use is capped at 20 req/min, 200 req/day and `page_size` ≤ 20.
   - Its 3.98M "wikimedia_audio" records are mostly pronunciation clips.

   Use it for discovery and to get ready-made `attribution` strings, then resolve each hit back to its source.
5. **A real licence bug in foley's Clotho adapter** [55]:
   - Clotho's captions are under a Tampere University licence for **non-commercial use only**.
   - About 16% of the eval-split audio is CC-BY-NC-3.0 or Sampling+ (140 and 31 of 1,045 clips).

   foley stamps every clip `CC-BY-4.0`, which fails open. Report 11's "captions CC-BY 4.0" is also wrong.
6. **Vendors now expose SFX search through MCP, not public REST.** Epidemic Sound has an official MCP server (beta, Sep 2025) with `SearchSoundEffects`, `SearchSimilarToSoundEffect` and `DownloadSoundEffect`, authenticated by OAuth or a per-account API key [24][25]. Splice has an official MCP server (beta) with `describe_a_sound` and `download_asset` [27][28]. A paying subscriber can now reach these catalogues directly; no partner deal is needed.
7. **Every commercial library forbids AI training.** That covers Sonniss (still, in GDC 2026 [41][42]), Envato (its acceptable-use policy [30]), Artlist (licence of 2026-04-01 [32]), Pixabay (no scraping "for machine learning purposes" [37]), BBC RemArc ("research" excludes AI training [40]) and Free To Use Sounds [47]. The Professional Sound Alliance (PSE, BOOM, Sound Ideas; 2026-09-24) is lobbying against AI scraping [45].
   - **Consequence:** foley's position that CLAP embedding counts as training keeps every one of these out of the default index. Only CC0/CC-BY sources and paid data licences (PSE [43], Soundsnap [35]) can be indexed.
8. **CC BY-SA sounds are effectively unusable in a film you don't release under BY-SA.** CC 4.0 says a sound recording "synched in timed relation with a moving image" always produces Adapted Material [21]. ShareAlike would therefore require the film itself to carry a BY-SA-compatible licence. Most Wikimedia Commons audio is BY-SA. foley already fails closed on `-sa` (good) and should document why.
9. **Client libraries are thin and stale, and one is a trap.** On PyPI, `freesound-python` is a **dependency-confusion placeholder** [11]; the official MTG client installs from GitHub only [9]. `freesound-api` (PyPI, MIT, 2022) is a clone [10]. Openverse's typed clients are LGPL-3.0 alphas from 2024 [18][19]. Howler and Tone handle playback only [66].
10. **Recommended additions to foley:**
    - a keyless Openverse adapter, used for discovery only;
    - a Wikimedia Commons adapter that excludes SA;
    - a "your own licensed library" adapter that parses UCS filenames and BWF/iXML metadata (the professional workflow: the user's purchased BOOM/PSE/Sonniss packs);
    - the full UCS 8.2.1 master in place of the 66-line seed;
    - Epidemic/Splice adapters routed through their MCP servers for subscribers.

---

## 1. Delta table: what changed since foley's July 2026 research

| # | Finding | Where foley stands | Source |
|---|---|---|---|
| D1 | Freesound text search moved to `GET /apiv2/search/`; `/search/text/` is deprecated (Nov 2025) | `foley/sources/freesound/config.py` still sets `"path": "/search/text/"` | [4][9] |
| D2 | `gen_ai_preference` ∈ {`no-additional-preferences`, `open-source-models`, `noncommercial-open-source-models`, `no-gen-ai`}; there is also a voice-recording opt-out for speech models (the opt-out's API field is **(unverified)**) | adapter only maps `no-gen-ai` → `ai_training_ok=False` | [4][7] |
| D3 | Freesound filter fields `category` / `subcategory` are the Broad Sound Taxonomy (BST); report 01 called it `bst_category` | not mapped in `param_map` | [4][8] |
| D4 | Freesound API ToS §3: commercial use of the *API* is negotiated case by case with UPF; §1(b): only intermediate copies, deleted when no longer needed; §4(a): no access to Content outside "your Application" | `cache_bytes_ok=False` is consistent; the commercial-API question is not surfaced anywhere | [6] |
| D5 | Openverse limits measured live: anonymous burst 20/min, sustained 200/day, `page_size` ≤ 20, result depth ~240 per query; `duration` in **milliseconds**; Freesound rows have `category: null` | no Openverse adapter | [14][17] |
| D6 | Clotho captions are non-commercial (Tampere licence); audio licences are per file (CC0 / BY-3.0 / BY-NC-3.0 / Sampling+) | `clotho.py` stamps a uniform `CC-BY-4.0` and ingests captions into BM25 | [55] |
| D7 | Epidemic Sound MCP server (beta), with SFX tools and a self-serve API key valid one year | report 01 treated Epidemic as partner-only | [24][25][26] |
| D8 | Splice MCP server (beta, official Claude connector): search free, downloads cost credits, 100 per rolling 24 h | not in report 01 | [27][28] |
| D9 | New keyless CC0 "SFX for agents" APIs: sfxmint (AI-generated or procedural, ~4.6k) and lotsofsounds (re-hosted Freesound CC0, `fs-<id>` ids) | not in report 01 | [26][65] |
| D10 | Sonniss GDC 2026 bundle: 7.47 GB from 17 vendors; AI/ML training still prohibited; archive > 200 GB | consistent with Ring-2 quarantine | [41][42] |
| D11 | Professional Sound Alliance (2026-09-24) against "data piracy"; PSE licenses curated sets for AI training through Musical AI | consistent | [44][45] |
| D12 | Artlist Pro licence (2026-04-01): no training or fine-tuning; assets may be *inputs* to AI services; no standalone use | not in report 01 | [31][32] |
| D13 | Envato acceptable-use policy forbids using Assets to train AI; the Envato *Market* API (AudioJungle) has an item search; Elements has no public API | report 01 only covered Mixkit | [29][30] |
| D14 | Adobe Stock's official Search API documents no `content_type:audio`; audio search exists only through the website's internal Ajax endpoint | not in report 01 | [33][34] |
| D15 | PyPI `freesound-python` is a dependency-confusion placeholder | `optional_dependencies` names `requests` only (safe) | [11] |
| D16 | CC 4.0: syncing a sound recording to moving image always creates Adapted Material, so ShareAlike binds the film | foley fails closed on `-sa` (correct, but undocumented) | [21] |
| D17 | Internet Archive `licenseurl` is asserted by the uploader. Example: a commercial "Valentino Sound Effects Library" CD is tagged with the Public Domain Mark | report 01: "license-check per item" | [22] |
| D18 | foley's `QUERY_AFFORDANCES` names the text field `text`; the Freesound `param_map` uses the key `query` | an internal vocabulary mismatch | code |

---

## 2. Target inventory: the overview matrix

`kind`: **API** = searchable programmatic API · **MCP** = vendor MCP server · **corpus** = downloadable dataset · **store** = web store without an API · **app** = local library app. "Film?" means: may a sound from this source be used, embedded, in a commercially distributed film?

| id | kind | auth | client pkgs | sound licence | API / site terms that bite | Film? | AI-train? | maturity |
|---|---|---|---|---|---|---|---|---|
| `freesound` | API | token (search, previews) / OAuth2 (original download) | MTG `freesound-python` (GitHub, MIT); `freesound-api` (PyPI, MIT); npm `freesound-client` (MIT) | per sound: CC0 / BY / BY-NC / Sampling+ | intermediate copies only; commercial API use negotiated; 60/min, 2000/day | CC0/BY yes; NC no; Sampling+ only transformed | per-uploader `gen_ai_preference` | mature |
| `openverse` | API | anonymous, or OAuth2 client-credentials | `openverse-api-client` (PyPI, LGPL-3, alpha); `@openverse/api-client` (npm, LGPL-3, alpha) | per record (CC family, PDM) | no scraping; "made using Openverse" notice; licences unverified by Openverse | per record | per record | stable API, stale SFX index |
| `wikimedia_commons` | API | none (User-Agent required) | any MediaWiki client (e.g. `requests`) | per file, mostly BY-SA | Wikimedia API etiquette | CC0/BY/PD yes; **BY-SA in a film forces BY-SA** | per file | mature |
| `internet_archive` | API | none | `internetarchive` (PyPI) **(unverified licence)** | per item, uploader-asserted | IA terms | only after manual verification | unknown | mature API, unreliable rights |
| `epidemic_sound` | API + MCP | API key / OAuth (ES Connect, MCP) | none official on PyPI/npm; OpenAPI spec | subscription licence | no local caching (report 01); MP3 only | yes, with an active subscription | not granted **(unverified)** | API v0; MCP beta |
| `splice` | MCP | OAuth (identity scopes only) | none | royalty-free per downloaded sample | credits; 100 downloads per rolling 24 h | yes (royalty-free sample licence) | Splice says it won't train on your uploads; the user's right to train is **(unverified)** | beta |
| `storyblocks` | API (enterprise) | HMAC | none | royalty-free | no standalone use | yes | no | stable (report 01) |
| `pond5` | API (partner) | partner key | none | royalty-free per item | partner terms | yes (purchased) | no **(unverified)** | report 01 |
| `envato_market` (AudioJungle) | API | personal token / OAuth bearer | none official | per-item purchased licence | acceptable-use policy: no AI training | yes (purchased licence) | **no** | stable |
| `artlist` | API (enterprise) | partner | none | subscription licence | no training; no standalone use | yes | **no** | enterprise |
| `adobe_stock` | store (official API excludes audio) | — | — | Adobe Stock licence | — | yes (licensed) | no **(unverified)** | n/a |
| `soundsnap` | store + enterprise dataset/API | contract | none | subscription; "pre-cleared for gen AI" via dataset deals | contract | yes | **yes, via contract** | enterprise |
| `pro_sound_effects` | store + enterprise data licence | contract | none | perpetual / subscription; AI only via data licence | standard EULA forbids AI | yes | via data licence | enterprise |
| `bbc_sfx` | store (web only) | — | — | RemArc: personal, educational, research | "research" ≠ AI training | **no** (commercial licence via PSE) | **no** | stable |
| `sonniss_gdc` | corpus (HTTP / torrent) | — | — | royalty-free, no attribution | no resale; **no AI training** | yes | **no** | annual |
| `pixabay_audio` | store (API serves images/video only) | — | — | Pixabay Content Licence | no scraping, including for ML | yes | **no** | stable |
| `zapsplat` | store | — | — | Standard (attribution) / Gold | automation prohibited (report 01) | yes | no **(unverified)** | stable |
| `mixkit` | store | — | — | Mixkit SFX Free Licence | no standalone or competing redistribution (report 01) | yes | no (Envato acceptable-use policy) **(unverified for Mixkit)** | stable |
| `uppbeat` | store | — | — | free (credit) / premium | automation forbidden; dataset/AI barred (report 01) | yes | **no** | stable |
| `youtube_audio_library` | store (inside YouTube Studio) | — | — | YouTube AL licence, or CC-BY for some tracks | use outside YouTube not stated | YouTube yes; elsewhere **(unverified)** | no | stable |
| `free_to_use_sounds` | store (paid bundles via Gumroad) | — | — | commercial OK; no resale | AI needs a separate licence | yes | **no** (separate licence) | small vendor |
| `boom_library` | store + packs | — | — | single-/multi-user media licence | no redistribution; Alliance founder | yes | **no** | stable |
| `soundly` | app (desktop + cloud) | app login | none | commercial, within a project | no API | yes | no | stable |
| `fsd50k` | corpus | — | — | per clip CC0/BY/BY-NC/Sampling+ | — | after filtering | CC0/BY yes | stable |
| `clotho` | corpus + benchmark | — | — | audio per file; **captions non-commercial** | — | audio after filtering; captions **no** | research | stable |
| `audioset` | labels only | — | — | labels CC-BY 4.0; ontology CC-BY-SA; audio belongs to YouTube uploaders | YouTube ToS | **no** (audio) | labels only | stable |
| `audiocaps` | labels only | — | — | repo MIT; audio from YouTube | YouTube ToS | **no** | benchmark | stable |
| `vggsound` | labels only | — | — | annotations CC-BY 4.0; copyright stays with video owners | YouTube ToS | **no** | labels only | stable |
| `esc50` | corpus | — | — | CC-BY-NC 3.0 (the ESC-10 subset is CC-BY) | — | **no** (ESC-10 yes) | research | stable |
| `wavcaps` | corpus | — | — | **academic only** | — | **no** | research only | stable |
| `foleyset`, `envsound_ucs` | corpus | — | — | per report 11 (CC-BY / inherited) **(not re-verified)** | — | per report 11 | per report 11 | 2026 |
| `sfxmint`, `lotsofsounds` | API + MCP (keyless) | none | npm `sfxmint` CLI | CC0 (asserted) | — | yes, if the CC0 claim holds | asserted CC0 | new (Sep 2026) |

---

## 3. Target cards

Native names appear verbatim in `code`. Cards are short where report 01 already covers a target.

### 3.1 `freesound` (Freesound APIv2; search API)

- **Access / auth** [5]. Token auth (`token=` query parameter, or the `Authorization: Token` header foley uses) covers search, instance, analysis and previews. OAuth2 is required for original download, upload, describe, comment, rate and bookmark.
- **Throttling** [5]. Standard: 60/min and 2000/day. Download and write operations: 30/min and 500/day. HTTP 429 when exceeded.
- **Search** [4]. `GET /apiv2/search/`, which replaces the old text search (deprecated Nov 2025). Native parameters:
  - `query` (supports `+` and `-` modifiers)
  - `filter` (Solr syntax)
  - `sort`: `score`, `duration_desc`, `duration_asc`, `created_desc`, `created_asc`, `downloads_desc`, `downloads_asc`, `rating_desc`, `rating_asc`
  - `fields`, `page` (default 1), `page_size` (default 15, max 150)
  - `group_by_pack` (1/0), `weights`
  - `similar_to` (a sound id **or a float vector**)
  - `similarity_space`: `laion_clap` (512-d) or `freesound_classic` (100-d)
- **Filter fields** [4]: `license`, `duration`, `tag`, `samplerate`, `channels`, `type`, `bitrate`, `username`, `is_geotagged`, `category` and `subcategory` (BST), `pack`, `is_remix`, `created`, and content descriptors without the `ac_` prefix (`loudness`, `pitch`, `bpm`, `note_name`, `spectral_centroid`). `license` filter values: `"Creative Commons 0"`, `"Attribution"`, `"Attribution NonCommercial"`. Sampling+ is legacy; whether it can be used as a filter value is **(unverified)**.
- **Result fields** [4]. Default: `id,name,tags,username,license`. Also available: `description`, `gen_ai_preference`, `type`, `channels`, `duration` (seconds), `samplerate`, `bitdepth`, `filesize`, `created`, `pack`, `avg_rating`, `num_downloads`, `url`, and `previews.{preview-hq-mp3, preview-lq-mp3, preview-hq-ogg, preview-lq-ogg}`. `license` is returned as a CC **URL**.
- **Download** [4]. `GET /apiv2/sounds/<id>/download/` returns the original format and needs OAuth2. Previews (MP3/OGG) need only the token.
- **Sound licences**. Per sound [1][2].
- **API terms** [6]:
  - §1(b): "limited intermediate copies … deleted when no longer required". Do not cache bytes.
  - §3: commercial use of the API is negotiated case by case with UPF; call limits are at Freesound's discretion.
  - §4(a): no access to Content outside your Application.
  - §4(c): no redistribution in breach of the Content Licences.
  - Attribution follows the CC licence; report 07 §4 covers the TASL template.
- **AI-training signal** [7]. The account-level "Generative AI preferences" panel (announced 2026-07-10) is exposed per sound as `gen_ai_preference`. It is a *preference*, not a licence term: it is "complementary to the CC license terms". Freesound also publishes "Data Packs" for model developers [7].
- **Clients.** Covered in §4.
- **Maturity**: mature. Note the endpoint migration (D1).

### 3.2 `openverse` (WordPress Foundation; search API; keyless)

- **Access** [14]. `GET https://api.openverse.org/v1/audio/`, anonymous, or with a Bearer token obtained via `POST /v1/auth_tokens/register/` then `POST /v1/auth_tokens/token/` (client credentials). Other endpoints: `/v1/audio/{id}/`, `/{id}/related/` (similarity), `/{id}/waveform/` (peaks), `/{id}/thumb/`, `/v1/audio/stats/`, `/v1/rate_limit/`.
- **Limits, measured 2026-10-03** [14]. Rate-limit headers: `x-ratelimit-limit-anon_burst: 20/min` and `x-ratelimit-limit-anon_sustained: 200/day`. An anonymous `page_size=21` returns 401 "page_size may not exceed 20 for anonymous requests". Results are capped at roughly 240 per query (`result_count` 240, `page_count` 120 at `page_size=2`). Registered users get "slightly higher limits".
- **Search parameters (verbatim)** [14]:
  - `q` (≤ 200 characters); or `title=`, `tags=` or `creator=` instead of `q`
  - `source` and `excluded_source` (from `/stats/`: `freesound` 591,450; `jamendo` 644,709; `wikimedia_audio` 3,978,562 [17])
  - `license`: `by`, `by-nc`, `by-nc-nd`, `by-nc-sa`, `by-nd`, `by-sa`, `cc0`, `nc-sampling+`, `pdm`, `sampling+`
  - `license_type`: `all`, `all-cc`, `commercial`, `modification`
  - `category`: `audiobook`, `music`, `news`, `podcast`, `pronunciation`, `sound_effect`
  - `length`: `shortest`, `short`, `medium`, `long`
  - `extension`, `filter_dead`, `mature`, `peaks`
  - experimental: `unstable__sort_by` (`relevance` / `indexed_on`), `unstable__sort_dir`, `unstable__collection`, `unstable__authority`
- **Result fields (verbatim, live response)** [14][15]: `id` (UUID), `title`, `indexed_on`, `foreign_landing_url`, `url` (for Freesound this is the `-hq.mp3` *preview*), `creator`, `creator_url`, `license`, `license_version`, `license_url`, `provider`, `source`, `category`, `genres`, `filesize`, `filetype`, `tags[].{name, accuracy, unstable__provider}`, `alt_files[].{url, bit_rate, filesize, filetype, sample_rate}` (for Freesound, the OAuth-gated `/download/` URL), `attribution` (a ready-made sentence), `fields_matched`, `mature`, `audio_set`, `duration` (**ms**), `bit_rate`, `sample_rate`, `thumbnail`, `detail_url`, `related_url`, `waveform`, `unstable__sensitivity`.
- **Measured caveats.**
  - `category=sound_effect&q=door` returns 0, because Freesound records have `category: null`, so the SFX category filter is unusable.
  - `q=whoosh` with `source=wikimedia_audio` returns Lingua Libre *pronunciations* of the word "whoosh".
  - The newest Freesound `indexed_on` dates seen were 2024-05 to 2025-07, so the index is stale relative to live Freesound.
- **Terms** [16]:
  - "You must not scrape the content in the Openverse catalog".
  - Apps must "prominently indicate that it was made using Openverse but is not endorsed or certified by Openverse".
  - Openverse "reserves the right to charge fees for commercial uses … and/or for heavy usage".
  - Openverse "does not verify its licensing status". Records must therefore be resolved at the source before `rights_verified=True`.
- **Licence mapping trap.** `nc-sampling+` and `pdm` need explicit rows. foley's `license_id_from_cc_url` sends `nc-sampling+` to `unknown`, but only by accident: the `-sa` substring guard matches `-sampling`. The PDM → CC0 widening is already [foley#56](https://github.com/thorwhalen/foley/issues/56).
- **Clients** [18][19]. `openverse-api-client` (PyPI 0.0.1a3, 2024-04, LGPL-3.0, sourcehut) and `@openverse/api-client` (npm 0.0.1-a1, 2024-04, LGPL-3.0-or-later, "thoroughly typed"). Both are alphas and LGPL; plain `requests`/`fetch` against the OpenAPI schema [14] is simpler.

### 3.3 `wikimedia_commons` (search API; keyless)

- **Access** [20]. MediaWiki Action API at `https://commons.wikimedia.org/w/api.php`, no key; send a descriptive `User-Agent`.
- **Search.** `action=query&list=search&srnamespace=6&srsearch=<q> filetype:audio`, or the generator form `generator=search&gsrnamespace=6&gsrsearch=…&prop=imageinfo&iiprop=url|mime|size|extmetadata` (tested 2026-10-03). Native paging: `srlimit` / `sroffset` (`gsrlimit` / `gsroffset`).
- **Result fields (verbatim, live)** [20]: `title` (`File:…`), `imageinfo[].{url, mime, size, duration}`, and `extmetadata.{LicenseShortName, License, LicenseUrl, UsageTerms, AttributionRequired, Artist, Credit, ImageDescription, Categories, DateTimeOriginal, Copyrighted, Restrictions}`. The licence comes per file, as structured data.
- **Sound licences.** Per file. Both "thunder" hits were `cc-by-sa-4.0`. **BY-SA in a film forces the film to be BY-SA-compatible** [21], so filter to CC0 / BY / PD.
- **Maturity**: mature API. SFX coverage is incidental (field recordings, archival sounds, pronunciations).

### 3.4 `internet_archive` (search API; keyless)

- **Access** [22]. `https://archive.org/advancedsearch.php?q=…&fl[]=identifier&fl[]=licenseurl&rows=…&page=…&output=json`, using Lucene query syntax (`mediatype:audio`, `subject:"sound effects"`, `licenseurl:*publicdomain*`). There is also the Scrape API (`/services/search/v1/scrape?q=…&fields=…&count=…`) for deep paging, and the Metadata API (`/metadata/<identifier>`) for file lists.
- **Measured.** `subject:"sound effects" AND mediatype:audio` gives 3,040 items. The "sound effects" + `licenseurl` PD query gives 821 items. These include "Valentino Sound Effects Library: DVD-2; CD-13" carrying the **Public Domain Mark**, a commercial library whose PD status is doubtful.
- **Rule.** `rights_verified=False` by default; IA licences are uploader-asserted.

### 3.5 `epidemic_sound` (partner API + MCP)

- **REST**: the Partner Content API, OpenAPI spec v0.1.17 [23].
  - `GET /v0/sound-effects/search` takes `term`, `offset`, `limit`, `sort` ∈ {`best-match`, `newest`, `popular`, `length`, `title`}, `order` ∈ {`asc`, `desc`} and `includeExplicit`.
  - Category browsing: `/v0/sound-effects/categories` (`type` = `all` / `featured`), `/categories/{categoryId}/tracks`, and `/collections`.
  - `GET /v0/sound-effects/{trackId}/download` takes `format` = `mp3` (the only option) and `quality` = `normal` / `high`.
  - Result `SoundEffectResponse` fields: `id`, `title`, `added`, `length`, `images`. Security schemes: `ApiKeyAuth`, `PartnerAuth`, `UserAuth`, `EpidemicSoundConnectAuth`.
- **MCP (beta, 2025-09-30)** [24][25][26]. Server `https://www.epidemicsound.com/a/mcp-server/mcp` per the MCP registry; the docs page says `/a/mcp-service/mcp`, so verify which is live.
  - SFX tools: `SearchSoundEffects`, `SearchSimilarToSoundEffect`, `DownloadSoundEffect`. Plus music, edit and voiceover tools.
  - Auth: OAuth, or a personal API key from `/account/api-keys`, valid one year, sent as `Authorization: Bearer`.
- **Licence**: tied to the user's subscription. Report 01: no local caching, MP3 only.
- **For foley**: an adapter for the user's own subscription, by reference only. This is the realistic path to a large, rights-cleared commercial SFX catalogue for a commercial film if the user subscribes.

### 3.6 `splice` (MCP only)

- Official MCP server `https://mcp.splice.com/mcp` (beta) [27][28]. Tools: `describe_a_sound` (natural-language search), `create_stack`, `prompt_to_stack`, `share_stack`, `download_asset`.
- OAuth with only `openid profile email offline_access`, so **search and download are not separated at consent**; a third-party listing warns that an agent allowed to browse can spend credits (**(unverified)** beyond that listing).
- Downloads cost 1 credit per new sample, capped at 100 per rolling 24 h.
- Catalogue: music-production samples first; it includes "Cinematic FX" and foley-type content.
- No public REST API.

### 3.7 `envato_market` (AudioJungle; search API)

- Envato API at `https://api.envato.com`, `GET /v1/discovery/search/search/item` [29]. Parameters: `term`, `site` (e.g. `audiojungle.net`), `category`, `page_size`, `sort_by`. `length_min` / `length_max` appear in a fetched summary of the docs **(unverified)**. Also `/search/more-like-this` (similarity) and `/search/comment`.
- Auth: personal token or OAuth Bearer. "Dynamically rate limited" (429 + `Retry-After`).
- Licences are per-item purchases. **Envato's acceptable-use policy prohibits using Assets "to train, develop, or enhance" AI** [30].
- Envato *Elements* (the subscription catalogue) has no public API.
- **For foley**: low value; this is purchase-and-link, not retrieval.

### 3.8 Enterprise and partner APIs: `artlist`, `storyblocks`, `pond5`, `soundsnap`, `pro_sound_effects`

- **Artlist**. Enterprise API at developer.artlist.io: Search API plus a Download API returning signed MP3/WAV URLs. It covers music, and its in-app offering advertises SFX [31]. Pro licence of 2026-04-01 [32]: no use "in datasets for machine learning, AI training"; no standalone use; assets may be used as *inputs* to AI services that don't claim the outputs.
- **Storyblocks / Pond5**. Unchanged from report 01 [1].
- **Soundsnap**. About 800k SFX. Enterprise APIs and datasets cost $100k/year to $500k/purchase, sold as "pre-cleared for generative AI and other machine learning applications" [35]. No public developer docs (apitracker lists none).
- **Pro Sound Effects**. Enterprise data licence (report 01). In 2026 it licenses curated sets for AI training through Musical AI, with output-attribution tagging [44]. It co-founded the Professional Sound Alliance [45]. PSE is also the commercial route for BBC SFX [40].

### 3.9 Web stores without an API

- **`adobe_stock`**. The official `https://stock.adobe.io/Rest/Media/1/Search/Files` (`x-api-key`, `x-Product`) documents `content_type:photo|illustration|vector|video|template|3d` and no audio [33]. The website's audio search goes through `https://stock.adobe.com/<lang>/Ajax/Search` with `k`, `limit`, `order`, `search_page` and `filters[content_type:audio]=1`. SearXNG scrapes it and reads the fields `title`, `audio_data`, `length` (ms) and `asset_type` [34]. That is not a sanctioned API.
- **`pixabay_audio`**. The API covers images and video only (`/api/` and `/api/videos/`). It is limited to 100 requests/60 s, requests "must be cached for 24 hours", and "systematic mass downloads are not allowed" [36]. The site terms (2024-11-18) prohibit scraping "including without limitation for machine learning purposes" [37]. The Content Licence bars standalone redistribution [38].
- **`bbc_sfx`** [39]:
  - More than 33,000 sounds; RemArc is personal, educational and research only.
  - "Research" excludes AI training and data mining.
  - Commercial use is licensed through PSE [40].
  - No API (report 01). The site blocked automated fetching on the access date.
- **`youtube_audio_library`**. Inside YouTube Studio only; no API. Sounds are "copyright-safe" and won't be claimed by Content ID. CC tracks must be credited in the description. Use **outside YouTube is not addressed** on the help page [46].
- **`free_to_use_sounds`**. Paid bundles on Gumroad (25,000+ recordings, 48–192 kHz / 24–32-bit WAV, ambisonic and binaural). Commercial use OK; no resale. AI/ML use needs a separately negotiated licence [47].
- **`zapsplat`, `mixkit`, `uppbeat`, `boom_library`**. Unchanged from report 01: no API, automation forbidden or no standalone redistribution [1][50][51][52][53]. BOOM is a founding voice of the anti-AI-scraping alliance [45].

### 3.10 Local library apps: `soundly`, plus Soundminer and BaseHead as a class

- **Soundly**. Desktop app plus cloud library and DAW plugins; no public API [48]. The size of the Pro core library is reported variously (10k+ to ~100k) **(unverified)** [49]. It supports UCS.
- **The class.** Soundminer, BaseHead and Soundly all index the user's **own local library** and read UCS filenames and BWF/iXML metadata (§5.3). foley has no adapter for this. It is the professional route: a film's sound editor searches packs they own (BOOM, PSE, Sonniss, Free To Use Sounds), licensed for their production. A UCS-aware local-library corpus adapter is the most valuable missing source (§6).

### 3.11 Research corpora: licence and film-usability

| corpus | ships audio? | licence (verbatim where possible) | commercial film? |
|---|---|---|---|
| FSD50K | yes (Zenodo 4060432) | per clip: CC0 38.8% / BY 45.9% / BY-NC 11.8% / Sampling+ 3.5% (report 11 [3]; record [54]) | the CC0/BY slice, with credits |
| Clotho v2.1 | yes (Zenodo 4783391) | audio per file, from the CSV `license` column. Eval split: CC0 452, BY-3.0 422, **BY-NC-3.0 140, Sampling+ 31**. Captions: Tampere University licence, "only for experimental and non-commercial purposes … Any commercial use … strictly prohibited" [55] | CC0/BY audio only; **captions never** |
| AudioSet | no (YouTube IDs) | labels CC-BY 4.0; ontology CC-BY-SA 4.0 [56] | no (audio); labels yes |
| AudioCaps | no (YouTube IDs) | repository MIT [57]; audio belongs to the uploaders | no |
| VGGSound | no (YouTube IDs) | "available to download for commercial/research purposes under CC-BY 4.0"; "copyright remains with the original video owners" [60] | no (audio) |
| ESC-50 | yes (GitHub) | CC-BY-NC 3.0; the ESC-10 subset is CC-BY [58] | ESC-10 only |
| WavCaps | yes (HF `cvssp/WavCaps`) | "Only academic uses are allowed" (~400k: FreeSound 262,300; AudioSet-SL 108,317; BBC 31,201; SoundBible 1,232) [59] | no |
| FoleySet / EnvSound-UCS | per report 11 | per report 11 [3] **(not re-verified)** | per report 11 |

---

## 4. Client libraries and MCP servers

### 4.1 Python

| package | where | licence | last release | notes |
|---|---|---|---|---|
| MTG `freesound-python` | GitHub only: `pip install git+https://github.com/MTG/freesound-python` [9] | MIT | pushed 2025-12-23 | official; already uses `SEARCH = '/search/'`. Methods: `search`, `get_sound`, `Sound.retrieve` (OAuth2), `Sound.retrieve_preview`, `get_similar`, `get_analysis`. Pager iterates pages |
| `freesound-python` (PyPI) | PyPI [11] | — | 2024-01 | **dependency-confusion placeholder. Never install.** |
| `freesound-api` | PyPI [10] | MIT | 1.1.0.2, 2022-12 | "Clone of freesound-python"; predates the endpoint move |
| `openverse-api-client` | PyPI / sourcehut [18] | LGPL-3.0 | 0.0.1a3, 2024-04 | alpha |
| `internetarchive` | PyPI | **(unverified)** | — | official IA CLI and library |
| (none) | — | — | — | no Python client exists for Epidemic, Splice, Envato audio, Pixabay audio, Soundsnap or BBC |

### 4.2 JavaScript / TypeScript

| package | licence | last release | notes |
|---|---|---|---|
| `freesound-client` (npm, amilajack) [12] | MIT | 0.4.4, 2022-09 | TS client; stale endpoint **(unverified)** |
| `freesound-api` (npm) [13] | MIT | 1.1.2, 2026-05 | no repository link in package metadata **(unverified provenance)** |
| `freesound` (npm) | none declared | 0.0.4, 2016 | abandoned |
| `@openverse/api-client` [19] | LGPL-3.0-or-later | 0.0.1-a1, 2024-04 | typed; alpha |
| `sfxmint` CLI [65] | — | 2026 | writes audio plus a `sounds.json` manifest (source URL, SHA-256, licence); ships a Web Audio `createSoundboard` |
| `howler` 2.2.4, `tone` 15.1.22 [66] | MIT | — | **playback and synthesis only; they search nothing.** They matter for an in-browser audition UI in reelee-web, not as sources |

### 4.3 MCP servers that already wrap SFX sources

| server | wraps | transport / auth | notes |
|---|---|---|---|
| `com.epidemicsound/mcp-server` (official) [24][26] | Epidemic SFX + music | streamable-http / SSE; OAuth or API key | beta |
| Splice MCP (official) [27][28] | Splice samples | OAuth | beta; credits |
| `com.sfxmint/sounds` [26][65] | sfxmint CC0 (AI-generated / procedural) | streamable-http, keyless | role-based "kits" |
| `com.lotsofsounds/mcp` [26][65] | re-hosted Freesound CC0 (`fs-<id>`) | streamable-http, keyless sample tier | a Freesound re-host; trust its provenance less than Freesound itself |
| `johnkimdw/freesound-mcp-server` [65] | Freesound | Python / Docker; API key | 8★, MIT, updated 2026-09 |
| `timjrobinson/FreesoundMCPServer` [65] | Freesound | Node; API key | 2★, MIT |
| `sandraschi/sfx-mcp` [65] | Freesound CC0 | FastMCP; API key | advertises a "local cache", which conflicts with Freesound API ToS §1(b) [6] |
| `MuShan-bit/freesound-mcp` | Freesound | — | 1★ |
| `ronnqvist/sfx-mcp`, `ai.blipsmith/sound-effects` | generation (ElevenLabs / proprietary) | — | out of scope (generation) |
| `sawa-zen/sound-effects-mcp` (npm) | plays canned notification sounds | — | not a source |
| `com.101soundboards/search` | 101soundboards | — | rights unknown; meme clips; avoid |

**Takeaway.** No existing MCP server combines more than one source, and none carries a normalised licence record. foley's MCP surface would be the first licence-gated, multi-source SFX MCP.

---

## 5. Jargon: concepts, native names, and proposed canonical names

Rule used: a concept gets a canonical name only if ≥ 2 providers share the concept. The name chosen is the most common spelled-out native form; foley's current name is shown where it differs. A concept that shares a *name* but not a *meaning* is flagged and is not canonicalised under that name.

### 5.1 Search and retrieval

| concept | Freesound | Openverse | Epidemic | Envato | Wikimedia | Internet Archive | others | proposed canonical | foley today |
|---|---|---|---|---|---|---|---|---|---|
| free-text query | `query` | `q` | `term` | `term` | `srsearch` | `q` | Pixabay `q`, lotsofsounds `q`, Splice `describe_a_sound` | `query` | `text` (base.py) vs `query` (param_map): **pick one** |
| results per page | `page_size` (≤150) | `page_size` (≤20 anon) | `limit` | `page_size` | `srlimit` | `rows` | lotsofsounds `limit` | `page_size` (paging); top-k across sources stays a facade concept | `k` |
| page / offset | `page` | `page` | `offset` | `page` **(unverified)** | `sroffset` | `page` | — | `page` (convert where a provider uses `offset`) | — |
| sort | `sort` (`score`, `duration_asc`, …) | `unstable__sort_by` + `unstable__sort_dir` | `sort` + `order` | `sort_by` | `srsort` | `sort[]` | Adobe web `order` | `sort` ∈ {`relevance`, `newest`, `popular`, `duration`} + `order` | `sort` = `score\|duration\|created\|downloads` |
| relevance (the sort value) | `score` | `relevance` | `best-match` | — | `relevance` | — | Adobe `relevance` | `relevance` | `score` |
| duration filter | `filter=duration:[lo TO hi]` (s) | `length` buckets `shortest\|short\|medium\|long` | (sort by `length` only) | `length_min/max` **(unverified)** | — | — | Adobe slider | `duration_range` (seconds) + bucket fallback | `duration_range` ✓ |
| licence filter | `filter=license:"Creative Commons 0"` | `license=cc0,by` | — (subscription) | — | (category / structured data) | `licenseurl:` in `q` | — | `license` (normalised ids) | `license` ✓ |
| commercial-use shorthand | — | `license_type=commercial` | — | — | — | — | — | `commercial_ok` | `commercial_ok` ✓ |
| tags | `filter=tag:x` | `tags=` | — | **(unverified)** | — | `subject:` | lotsofsounds `tags` | `tags` | (via `filters`) |
| taxonomy category | `category` / `subcategory` (BST) | — | `categoryId` (ES taxonomy) | `category` | `Categories` (wiki) | `subject` | Adobe "Music \| Sound effects" | `ucs_category` (map each native taxonomy to UCS) | `ucs_category` ✓ |
| media kind (SFX vs music) | BST top level | `category` (`sound_effect`, `music`, …) | separate endpoints | `site` | `filetype:audio` | `mediatype:audio` | Adobe `content_type:audio` | `kind` (`sfx` default). **Same name "category" as above, different meaning: do not merge** | — |
| similar-to search | `similar_to` + `similarity_space` | `/related/` | `SearchSimilarToSoundEffect` | `more-like-this` | — | — | Splice "Search with Sound" | `similar_to` (id) | — |
| semantic / embedding space | `similarity_space=laion_clap` | — | (internal) | — | — | — | Splice `describe_a_sound` | `semantic_text` (facade-side CLAP) | `semantic_text` ✓ |
| explicit / sensitive | — | `mature`, `unstable__include_sensitive_results` | `includeExplicit` | — | — | — | — | `include_explicit` | — |
| restrict sources | — | `source` / `excluded_source` | — | `site` | — | `collection:` | — | `sources` (facade fan-out list) | — |
| preview vs original | `previews[preview-hq-mp3]` vs `/download/` (OAuth2) | `url` (source preview) vs `alt_files` | download `quality=normal\|high` | — | `imageinfo.url` (original) | `/download/<id>/<file>` | lotsofsounds `stream_url` | `preview_url` + `download(id, quality=)` | `download_source: preview` |

**Result metadata.**

| concept | Freesound | Openverse | Epidemic | Wikimedia | IA | proposed |
|---|---|---|---|---|---|---|
| id | `id` (int) | `id` (UUID) | `id` | `pageid` / `title` | `identifier` | `id` = `<source>:<native id>` (foley already does `freesound:<id>`) |
| title | `name` | `title` | `title` | `title` / `ObjectName` | `title` | `title` |
| duration | `duration` (s) | `duration` (**ms**) | `length` (s) | `duration` (s) | per-file `length` | `duration_s` (convert at the adapter) |
| licence | `license` (CC URL) | `license` + `license_version` + `license_url` | — | `License` / `LicenseShortName` / `LicenseUrl` | `licenseurl` | `license_url` (raw) → `license_id` (normalised) |
| author | `username` | `creator` / `creator_url` | — | `Artist` | `creator` | `creator` (+ `creator_url`) |
| tags | `tags` | `tags[].name` | — | `Categories` | `subject` | `tags` |
| landing page | `url` | `foreign_landing_url` | — | page URL | `https://archive.org/details/<id>` | `source_url` |
| sample rate | `samplerate` | `sample_rate`, `alt_files[].sample_rate` | — | — | per file | `sample_rate` |
| ready credit line | — (template in FAQ) | `attribution` | — | `AttributionRequired` + `Credit` | — | `attribution_text` |
| AI-use signal | `gen_ai_preference` | — | — | — | — | `ai_training_ok` (derived) |

### 5.2 Licensing vocabulary

| concept | native names | proposed canonical (`license_id` or flag) | note |
|---|---|---|---|
| public-domain dedication | Freesound `"Creative Commons 0"`, Openverse `cc0`, Wikimedia `CC0`, URL `publicdomain/zero/1.0` | `CC0-1.0` | commercial, standalone and training all OK |
| Public Domain Mark | Openverse `pdm`, URL `publicdomain/mark/1.0`, IA `licenseurl` | `PDM-1.0` (its own row, **not** CC0) | a *label*, not a waiver; foley maps it to CC0 today ([foley#56](https://github.com/thorwhalen/foley/issues/56)) |
| attribution | Freesound `"Attribution"`, Openverse `by`, Wikimedia `CC BY 4.0`, Clotho `by/3.0` | `CC-BY-4.0`, `CC-BY-3.0` (keep the version) | credit as TASL (report 07 §4) |
| non-commercial | `"Attribution NonCommercial"`, `by-nc`, `by-nc/3.0` | `CC-BY-NC-*` | blocks a commercial film |
| share-alike | Openverse `by-sa`, Wikimedia `cc-by-sa-4.0` | `CC-BY-SA-*` (fail closed for film) | sync to picture = Adapted Material [21] |
| no-derivatives | `by-nd`, `by-nc-nd` | `CC-BY-ND-*` (fail closed) | sync to picture is an adaptation, so ND forbids it |
| sampling | Freesound `Sampling+`, Openverse `sampling+`, `nc-sampling+` | `CC-Sampling+-1.0`, `CC-NC-Sampling+-1.0` | retired 2011 (report 07 §3.4) |
| royalty-free (a pricing model, not a licence) | Pixabay "Content License", Sonniss "royalty-free", Storyblocks, Zapsplat "Standard License", Mixkit "Free License" | `Proprietary-<vendor>` + flags | standalone redistribution and AI training usually barred |
| standard vs extended licence | Adobe Stock "Standard / Extended"; Envato "Regular / Extended" **(audio tier names unverified)** | the `license_tier` field | scope / print-run / broadcast differences |
| subscription-bound | Epidemic, Artlist, Soundly, Splice credits, Uppbeat Premium | flag `subscription_bound=True` | Epidemic/Soundly: rights survive cancellation for published work (report 01) |
| attribution required | Openverse `attribution`; Wikimedia `AttributionRequired: "true"`; Zapsplat free tier; Uppbeat free tier; CC-BY | `requires_attribution` | — |
| standalone redistribution | Pixabay "Standalone basis"; Artlist "standalone content"; ElevenLabs "isolated files" | `redistribute_standalone_ok` | — |
| caching allowed (operational) | Freesound "intermediate copies"; Pixabay "cached for 24 hours"; Epidemic "no local caching" | `cache_bytes_ok` | a terms-of-service fact, not a copyright one |
| AI training | Freesound `gen_ai_preference`; Sonniss "training artificial intelligence"; Envato "train, develop, or enhance"; Pixabay "machine learning purposes"; Artlist "datasets for machine learning"; BBC "research ≠ AI training" | `ai_training_ok` (+ `ai_training_scope` ∈ {`any`, `open_source_only`, `nc_open_source_only`, `none`}) | Freesound's two middle values need the scope |
| platform-claim safety | YouTube AL "copyright-safe / won't be claimed through Content ID"; Uppbeat "safelisting" | flag `content_id_safe` | relevant to a YouTube release |
| registry of the "unknown" | — | `unknown` + `rights_verified=False` | fail-closed (report 07 §8) |

### 5.3 SFX-industry jargon (for queries, taxonomy and export)

| term | meaning | where it shows up natively | proposed use in a facade |
|---|---|---|---|
| **foley** | sync sounds performed to picture: footsteps ("feet"), cloth ("moves"), props | UCS `FOLY*` CatIDs **(exact CatIDs unverified)**; FoleySet's taxonomy | `layer="foley"` |
| **hard effects / spot effects** | discrete cut-to-picture sounds (door, gunshot, car-by) | Soundminer `Category`; vendor packs | `layer="hard_fx"` |
| **backgrounds (BG) / ambience / atmos** | continuous location beds | UCS `AMB*` (e.g. `AMBUrbn` [61]); Freesound BST "Soundscapes" (report 01) | `layer="ambience"` (foley's golden set uses `bed`) |
| **room tone** | the "silence" of a location, used to fill dialogue gaps | keywords only | a query alias for ambience with low level |
| **walla** | unintelligible crowd voices | UCS crowd categories **(unverified)** | ambience subtype; voice-safety gate (report 07 §7) |
| **one-shot** vs **loop** | a single event vs a seamlessly repeatable clip | Splice and sample stores; Adobe `is_loop` [33]; foley `GENERATION_AFFORDANCES.loop` | `loopable: bool` |
| **stinger** | a short punctuating sound or musical hit | stock music/SFX stores | tag |
| **whoosh / swish / pass-by**, **impact / hit**, **riser**, **drone** | design-SFX archetypes, especially in trailers | category names in Epidemic, Artlist and BOOM packs | tags mapped to UCS (`WHSH*`, `IMPC*` **(unverified CatIDs)**) |
| **designed** vs **natural/field** | processed or composited vs recorded as-is | Soundminer `Rec Type` [62] | `provenance.kind` |
| **UCS** | Universal Category System 8.2.1 (Jan 2024), public domain; Category → SubCategory → **CatID** [61] | Soundly, Soundminer, BaseHead, PSE, BOOM (report 01) | the canonical taxonomy (`ucs_category`) |
| **UCS filename** | `CatID_FXName_CreatorID_SourceID[_UserData].wav`; only the leading CatID is mandatory (axlsound) | vendor libraries | parse on ingest; emit on export |
| **BWF `bext`** | Broadcast Wave chunk: `Description` (256 chars), `Originator`, `OriginatorReference`, `OriginationDate`, `OriginationTime`, `TimeReference`, `UMID`, loudness fields, `CodingHistory` [63] | every pro WAV | read `Description` as the caption; write provenance on export |
| **iXML** | an XML chunk in WAV (`PROJECT`, `SCENE`, `TAKE`, `NOTE`, `TRACK_LIST`, `USER`, …) [64]; Soundminer and Steinberg store UCS Category/SubCategory there | field recorders, Soundminer | read/write UCS + licence |
| **Soundminer fields** | `Description`, `Keywords`, `Track Title`, `FX Name`, `Category`, `SubCategory`, `Manufacturer`, `Library`, `Designer` / `Recordist`, `Mic Perspective`, `Microphone`, `Rec Medium`, `Rec Type`, `Location`, `Notes`, `ShortID`, `ISRC` [62] | Soundminer, BaseHead | the target schema for "export to an editor's library" |
| **Broad Sound Taxonomy (BST)** | Freesound's 5 / 23 two-level taxonomy, exposed as `category` / `subcategory` [4][8] | Freesound | a coarse pre-filter mapped from UCS |
| **AudioSet ontology** | 632 classes with MIDs (report 01) | FSD50K, AudioSet, VGGSound-like corpora | the ML-label layer (foley already has it) |

---

## 6. What foley's current sources miss, with recommendations

foley currently has these sources: retrieve `freesound`; generate `elevenlabs` and `stable_audio`; corpora `fsd50k`, `clotho`, `foleyset`, `sonniss`, `bbc_remarc`. Ordered by value for a commercial film.

1. **Freesound endpoint (D1).** Change `search_endpoint.path` to `/search/` and re-record the cassettes. Old-path sunset date: **(unverified)**.
2. **The full `gen_ai_preference` mapping (D2).** `no-gen-ai` → `ai_training_ok=False`. `noncommercial-open-source-models` → `False` when `IntendedUse.commercial`. `open-source-models` → allowed only when the embedding model is open source; LAION-CLAP qualifies. Record the raw value in the `LicenseRecord`.
3. **Freesound licences beyond CC0.** `accepted_license_ids` is `["CC0-1.0"]`. foley already generates TASL credits, so admit `CC-BY-*` when `IntendedUse.can_attribute`. That roughly doubles the usable pool (FSD50K's split suggests BY ≈ CC0).
4. **Freesound BST and similarity.** Map `ucs_category` to a coarse `category`/`subcategory` pre-filter. Add `similar_to=<id>` ("more like this one"). Experiment with passing a CLAP *text* embedding as the `similar_to` vector in `laion_clap` space: server-side text→audio over all of Freesound, not just the indexed subset **(unverified that Freesound accepts text-side vectors meaningfully)**.
5. **The Freesound commercial-API question (D4).** Surface the ToS §3 note in the source config and docs. Optionally email UPF for the film's production use.
6. **Fix the Clotho licensing (D6).** Read `clotho_metadata_*.csv` `license` per file, the same way `fsd50k.py` does. Keep CC versions. Mark captions as a separate non-commercial asset: either exclude them from the BM25 index when the index is used commercially, or keep captions in an eval-only store. Correct report 11's "captions CC-BY 4.0".
7. **An Openverse adapter: keyless, licence-rich, discovery only.**
   - Use it for Jamendo and Wikimedia reach and its ready `attribution` strings.
   - Do not use `category=sound_effect`.
   - Convert `duration` from ms.
   - Respect anonymous limits (20/min, 200/day, `page_size` ≤ 20).
   - For Freesound-provided rows, resolve back through the Freesound adapter, which is fresher and licence-verified.
   - Show the "made using Openverse" notice.
   - Add explicit `nc-sampling+` and `pdm` rows instead of relying on the `-sa` substring accident.
8. **A Wikimedia Commons adapter.** Keyless; licence comes from `extmetadata`. Default filter CC0 / BY / PD; SA and ND fail closed, and document the sync-to-picture rule [21] in report 07.
9. **An Internet Archive adapter, opt-in.** Public-domain archival sounds (1940s radio discs, for example). Keep `rights_verified=False` until a human confirms, given D17.
10. **A "my licensed library" local adapter: the biggest gap.** Point foley at a folder of owned packs (BOOM, PSE, Sonniss, Free To Use Sounds). Parse UCS filenames into CatID, FXName, CreatorID and SourceID. Read BWF `bext.Description` and iXML/Soundminer fields as caption and tags. Take the licence from a per-folder sidecar the user writes once (e.g. `Sonniss-GDC`, `Proprietary-BOOM`). Index for human-facing search, with the AI-training gate already in place: Ring-2 consent.
11. **The full UCS master.** Replace the partial seed (`foley/index/taxonomy/seed.py`, of which only `DOORWood` and `WEATHRain` are confident) with the public-domain UCS 8.2.1 spreadsheet and its synonyms [61]. Then add the EnvSound-UCS mapping tables (report 11 §3.1).
12. **UCS/BWF export.** When a sound leaves foley (for `an`'s sounds store, or an editor's library), write a UCS filename and `bext.Description`. Put iXML `USER` fields carrying licence and provenance. This is interop with Soundminer, Soundly and BaseHead, and complements [foley#66](https://github.com/thorwhalen/foley/issues/66).
13. **Subscriber adapters through vendor MCP.** Add `epidemic_sound` (API key, by reference, MP3, no cache) and, lower priority, `splice` (credits; gate download behind explicit approval because OAuth scopes don't separate search from spend). These are the realistic large, rights-cleared commercial SFX catalogues for a film. Mark the licence `subscription_bound`.
14. **Keyless CC0 agent APIs (`sfxmint`, `lotsofsounds`).** Optional and low priority. sfxmint is AI-generated, so treat it as `is_ai_generated` with an asserted CC0. lotsofsounds re-hosts Freesound, so prefer the original Freesound record.
15. **Vocabulary hygiene (D18).** Rename `QUERY_AFFORDANCES["text"]` → `query` (or the reverse) so the affordance key and the `param_map` key agree. Add `page`, `similar_to`, `include_explicit`, `sources` and `kind` as affordances. Keep `sort` values as {`relevance`, `newest`, `popular`, `duration`}, with `score` as a Freesound-native value only.
16. **Licence-model additions.**
    - `PDM-1.0` as its own row ([foley#56](https://github.com/thorwhalen/foley/issues/56)).
    - Keep CC 3.0 versus 4.0.
    - `ai_training_scope` for Freesound's graded preferences.
    - `subscription_bound`, `content_id_safe`, `license_tier`.
    - A `terms_notes` field for API-level obligations (the Openverse notice, Freesound ToS §3).
17. **Client hygiene.** Never depend on PyPI `freesound-python` (D15). If foley ever wants the MTG client, vendor it or install from Git. foley's own `requests` transport is already the better seam.
18. **Paid AI-cleared data (deferred).** If foley ever *trains* (as opposed to indexing for human search), the only commercial-grade SFX that are licensed for it are PSE's data licence, Soundsnap's datasets and Freesound CC0. Record this as the boundary, not as work.

---

## REFERENCES

1. [foley report 01 — SFX Source APIs & Sound Libraries (July 2026)](https://github.com/thorwhalen/foley/blob/main/misc/docs/research/01-sfx-source-apis.md)
2. [foley report 07 — Licensing, Rights, Provenance & Attribution (July 2026)](https://github.com/thorwhalen/foley/blob/main/misc/docs/research/07-licensing-provenance.md)
3. [foley report 11 — Bootstrap Corpora & Benchmarks (July 2026)](https://github.com/thorwhalen/foley/blob/main/misc/docs/research/11-bootstrap-corpora-benchmarks.md)
4. [Freesound APIv2 — Resources (search, filters, fields, gen_ai_preference, download)](https://freesound.org/docs/api/resources_apiv2.html)
5. [Freesound APIv2 — Overview (token vs OAuth2, throttling)](https://freesound.org/docs/api/overview.html)
6. [Freesound — API Terms of Use](https://freesound.org/help/tos_api/)
7. [Freesound Blog — New "Generative AI preferences" panel (2026-07-10)](https://blog.freesound.org/?p=2417)
8. [Freesound Blog — Introducing the Broad Sound Taxonomy](https://blog.freesound.org/?p=2206)
9. [MTG/freesound-python — official Python client (GitHub, MIT)](https://github.com/MTG/freesound-python)
10. [PyPI — freesound-api (clone of freesound-python, MIT)](https://pypi.org/project/freesound-api/)
11. [PyPI — freesound-python (dependency-confusion placeholder)](https://pypi.org/project/freesound-python/)
12. [npm — freesound-client (amilajack, MIT)](https://www.npmjs.com/package/freesound-client)
13. [npm — freesound-api](https://www.npmjs.com/package/freesound-api)
14. [Openverse API — reference and OpenAPI schema (audio endpoint, auth, rate limits)](https://api.openverse.org/v1/)
15. [Openverse — API media properties (audio fields)](https://docs.openverse.org/meta/media_properties/api.html)
16. [Openverse — Terms of Service](https://docs.openverse.org/terms_of_service.html)
17. [Openverse — audio source stats endpoint](https://api.openverse.org/v1/audio/stats/)
18. [openverse-api-client — Python client (sourcehut, LGPL-3.0)](https://sr.ht/~sara/openverse-api-client/)
19. [npm — @openverse/api-client (LGPL-3.0-or-later)](https://www.npmjs.com/package/@openverse/api-client)
20. [MediaWiki — API:Search](https://www.mediawiki.org/wiki/API:Search) and [Extension:CommonsMetadata (extmetadata fields)](https://www.mediawiki.org/wiki/Extension:CommonsMetadata)
21. [Creative Commons — BY-SA 4.0 legal code (Adapted Material: sound synched to moving image; ShareAlike)](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)
22. [Internet Archive — Advanced Search](https://archive.org/advancedsearch.php) and [Metadata API](https://archive.org/developers/metadata.html)
23. [Epidemic Sound — Partner Content API OpenAPI spec](https://partner-content-api.epidemicsound.com/docs/spec.json)
24. [Epidemic Sound — MCP server documentation (tools, auth)](https://developers.epidemicsound.com/docs/mcp)
25. [Epidemic Sound — Introducing the Epidemic Sound MCP Server (2025-09-30)](https://www.epidemicsound.com/blog/mcp-server/)
26. [Official MCP Registry — server search (epidemicsound, sfxmint, lotsofsounds, …)](https://registry.modelcontextprotocol.io/v0/servers?search=sound)
27. [Splice — Getting started with the Splice MCP server (beta)](https://support.splice.com/en/articles/14442749-getting-started-with-the-splice-mcp-server-beta)
28. [Splice — MCP server](https://splice.com/tools/mcp-server)
29. [Envato API — documentation (Market catalog search)](https://build.envato.com/api/)
30. [Envato Elements — User Terms / Acceptable Use (AI-training prohibition)](https://help.elements.envato.com/hc/en-us/articles/360000629006)
31. [Artlist — Bring Artlist assets into your app (Enterprise API)](https://artlist.io/blog/bring-artlist-into-your-app/)
32. [Artlist — Pro License permitting assets in AI (2026-04-01, PDF)](https://help-center.artlist.io/media/w5mglb2w/current-pro-license-permitting-assets-in-ai-clean-01042026.pdf)
33. [Adobe Stock API — Search reference (content_type filters)](https://developer.adobe.com/stock/docs/api/11-search-reference/)
34. [SearXNG Adobe Stock engine commit (audio via stock.adobe.com Ajax)](https://gitea.zaclys.com/zaclys/searxng/commit/02ebea58fb788aef3499366b941ade650417937d)
35. [Datarade — Soundsnap data provider profile (APIs/datasets, AI-cleared)](https://datarade.ai/data-providers/soundsnap/profile)
36. [Pixabay — API documentation (images and videos only)](https://pixabay.com/api/docs/)
37. [Pixabay — Terms of Service (2024-11-18; scraping incl. for ML prohibited)](https://pixabay.com/service/terms/)
38. [Pixabay — Content License summary](https://pixabay.com/service/license-summary/)
39. [BBC Sound Effects — Licensing (RemArc)](https://sound-effects.bbcrewind.co.uk/licensing)
40. [Mixmag — The BBC's sound effect archive offers 33,000 samples for free (RemArc; AI training excluded; PSE for commercial)](https://mixmag.net/read/bbc-sound-effect-archive-free-audio-samples-news)
41. [Sonniss — #GameAudioGDC Bundle License](https://sonniss.com/gdc-bundle-license/)
42. [rekkerd.org — Sonniss releases GDC 2026 Game Audio Bundle](https://rekkerd.org/sonniss-releases-gdc-2026-game-audio-bundle/)
43. [Pro Sound Effects — Audio Dataset for Machine Learning & AI](https://www.prosoundeffects.com/machine-learning-ai)
44. [Record of the Day — Musical AI and Pro Sound Effects partner to create licensed datasets for AI training](https://www.recordoftheday.com/on-the-move/news-press/musical-ai-and-pro-sound-effects-partner-to-create-licensed-datasets-for-ai-training)
45. [Music Business Worldwide — Sound designers and SFX libraries launch Professional Sound Alliance (2026-09-24)](https://www.musicbusinessworldwide.com/sound-designers-and-sfx-libraries-launch-professional-sound-alliance-to-fight-ai-scraping-now-sound-will-have-protection-of-our-own/)
46. [YouTube Help — Use music and sound effects from the Audio Library](https://support.google.com/youtube/answer/3376882?hl=en)
47. [Free To Use Sounds — home](https://www.freetousesounds.com/) and [AI & Machine Learning policy](https://www.freetousesounds.com/aiml/)
48. [Soundly — How can I use the sounds? (FAQ)](https://getsoundly.com/faq/how-can-i-use-the-sounds/)
49. [A Sound Effect — Soundly 2 is here](https://asoundeffect.com/soundly-2-is-here/)
50. [ZapSplat — FAQ](https://www.zapsplat.com/faq/)
51. [Mixkit — Licenses](https://mixkit.co/license/)
52. [Uppbeat — User Agreement](https://uppbeat.io/user-agreement)
53. [BOOM Library — Terms & Conditions](https://www.boomlibrary.com/terms-conditions/)
54. [FSD50K — Zenodo record 4060432](https://zenodo.org/records/4060432)
55. [Clotho — Zenodo record 4783391 (per-file Freesound licences; Tampere University caption licence)](https://zenodo.org/records/4783391)
56. [AudioSet — Google Research dataset page](https://research.google.com/audioset/dataset/index.html)
57. [AudioCaps — GitHub (cdjkim/audiocaps)](https://github.com/cdjkim/audiocaps)
58. [ESC-50 — GitHub (CC BY-NC 3.0; ESC-10 CC BY)](https://github.com/karolpiczak/ESC-50)
59. [WavCaps — GitHub (academic use only)](https://github.com/XinhaoMei/WavCaps)
60. [VGGSound — Oxford VGG dataset page (CC BY 4.0 annotations)](https://www.robots.ox.ac.uk/~vgg/data/vggsound/)
61. [Universal Category System — official site (UCS 8.2.1, Jan 2024)](https://universalcategorysystem.com/) and [aXLsound — UCS info (CatID + filename)](https://axlsound.com/ucs-info/)
62. [A Sound Effect — Sound Effects Metadata Style Guide (Kai Paquin)](https://www.asoundeffect.com/metadata-style-guide/)
63. [EBU Tech 3285 — Broadcast Wave Format (bext chunk)](https://tech.ebu.ch/docs/tech/tech3285.pdf)
64. [iXML specification (Gallery)](http://www.gallery.co.uk/ixml/)
65. SFX MCP servers on GitHub: [johnkimdw/freesound-mcp-server](https://github.com/johnkimdw/freesound-mcp-server), [timjrobinson/FreesoundMCPServer](https://github.com/timjrobinson/FreesoundMCPServer), [sandraschi/sfx-mcp](https://github.com/sandraschi/sfx-mcp), [flreey/sfxmint-mcp](https://github.com/flreey/sfxmint-mcp), [lotsofsounds/free-sound-effects-api](https://github.com/lotsofsounds/free-sound-effects-api), [ronnqvist/sfx-mcp](https://github.com/ronnqvist/sfx-mcp)
66. [npm — howler](https://www.npmjs.com/package/howler) and [npm — tone](https://www.npmjs.com/package/tone)
