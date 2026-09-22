# foley.licensing

License policy for foley: the license_id -> flag-set SSOT, flag derivation
(with per-source overrides), and the fail-closed candidate `keep()` gate.

Stdlib-only (imports only `foley.base`). The dependency direction is one-way:
`licensing -> base`.

The two operational vs copyright flags are DISTINCT and must not be conflated:

> * `redistribute_standalone_ok` is a COPYRIGHT question (may the raw file be
>   re-exposed standalone?).
> * `cache_bytes_ok` is a TOS/OPERATIONAL question (may foley persist the
>   bytes at all?).

E.g. Freesound CC0 is legally redistributable yet its API TOS forbids caching,
so the Freesound adapter passes `overrides={'cache_bytes_ok': False}` — the
item is redistributable but stored by-reference.

### Module Attributes

| [`UNKNOWN_LICENSE_FLAGS`](#foley.licensing.UNKNOWN_LICENSE_FLAGS)   | Fail-closed fallback for unknown / `Proprietary-*` license ids (all False, cap None).                                          |
|--------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| [`LICENSE_FLAGS`](#foley.licensing.LICENSE_FLAGS)           | `license_id` -> default flag set (report 07 §8.1 seed table).                                                                  |
| [`UNKNOWN_LICENSE_META`](#foley.licensing.UNKNOWN_LICENSE_META)    | Fail-closed display fallback for unknown / `Proprietary-*` license ids.                                                        |
| [`LICENSE_META`](#foley.licensing.LICENSE_META)            | `license_id` -> display name + canonical URL (one row per [`LICENSE_FLAGS`](#foley.licensing.LICENSE_FLAGS) key). |

### Functions

| [`apply_license_flags`](#foley.licensing.apply_license_flags)(record, \*[, overrides])      | Populate `record`'s eight derived flags from its `license_id` (+ overrides), in place, and return it.                    |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| [`derive_license_flags`](#foley.licensing.derive_license_flags)(license_id, \*[, overrides]) | Look up the flag set for a `license_id` (fail-closed fallback), then apply per-source overrides.                         |
| [`keep`](#foley.licensing.keep)(record, intended_use)                        | Fail-closed candidate license gate (report 07 §8.2).                                                                     |
| [`keep_sound`](#foley.licensing.keep_sound)(sound_record, intended_use)            | Convenience: apply [`keep()`](#foley.licensing.keep) to a `SoundRecord`'s nested license.          |
| [`license_id_from_cc_url`](#foley.licensing.license_id_from_cc_url)(url)                       | Map a Creative-Commons license URL **or label** to `(license_id, verified)`.                                             |
| [`license_meta`](#foley.licensing.license_meta)(license_id)                          | Return the display [`LicenseMeta`](#foley.licensing.LicenseMeta) for `license_id` (fail-closed fallback). |

### Classes

| [`LicenseFlags`](#foley.licensing.LicenseFlags)([commercial_ok, ...])   | The eight derivable flags for one `license_id` (the table row type).       |
|---------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| [`LicenseMeta`](#foley.licensing.LicenseMeta)(display_name[, url])     | Human-facing display metadata for one `license_id` (name + canonical URL). |

### foley.licensing.LICENSE_FLAGS *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [LicenseFlags](#foley.licensing.LicenseFlags)]* *= {'CC-BY-4.0': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=True, cache_bytes_ok=True, modification_ok=True, ai_training_ok=True, requires_attribution=True, revenue_cap_usd=None), 'CC-BY-NC-4.0': LicenseFlags(commercial_ok=False, embed_in_derivative_ok=True, redistribute_standalone_ok=True, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=True, revenue_cap_usd=None), 'CC-Sampling+-1.0': LicenseFlags(commercial_ok=False, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=True, revenue_cap_usd=None), 'CC0-1.0': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=True, cache_bytes_ok=True, modification_ok=True, ai_training_ok=True, requires_attribution=False, revenue_cap_usd=None), 'ElevenLabs-SFX': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None), 'MIT': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=True, cache_bytes_ok=True, modification_ok=True, ai_training_ok=True, requires_attribution=True, revenue_cap_usd=None), 'Pixabay-Content': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None), 'RemArc': LicenseFlags(commercial_ok=False, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=True, revenue_cap_usd=None), 'Sonniss-GDC': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None), 'Stability-Community': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=False, cache_bytes_ok=True, modification_ok=True, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=1000000), 'unknown': LicenseFlags(commercial_ok=False, embed_in_derivative_ok=False, redistribute_standalone_ok=False, cache_bytes_ok=False, modification_ok=False, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None), 'user-owned': LicenseFlags(commercial_ok=True, embed_in_derivative_ok=True, redistribute_standalone_ok=True, cache_bytes_ok=True, modification_ok=True, ai_training_ok=True, requires_attribution=False, revenue_cap_usd=None)}*

`license_id` -> default flag set (report 07 §8.1 seed table).

Order of `LicenseFlags` positional args:

```default
commercial, embed, redistribute_standalone, cache_bytes, modification,
ai_training, requires_attribution, revenue_cap_usd
```

* **Type:**
  SSOT

### foley.licensing.LICENSE_META *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [LicenseMeta](#foley.licensing.LicenseMeta)]* *= {'CC-BY-4.0': LicenseMeta(display_name='CC BY 4.0', url='https://creativecommons.org/licenses/by/4.0/'), 'CC-BY-NC-4.0': LicenseMeta(display_name='CC BY-NC 4.0', url='https://creativecommons.org/licenses/by-nc/4.0/'), 'CC-Sampling+-1.0': LicenseMeta(display_name='CC Sampling+ 1.0', url='https://creativecommons.org/licenses/sampling+/1.0/'), 'CC0-1.0': LicenseMeta(display_name='CC0 1.0 Universal (Public Domain Dedication)', url='https://creativecommons.org/publicdomain/zero/1.0/'), 'ElevenLabs-SFX': LicenseMeta(display_name='ElevenLabs Sound Effects Terms', url='https://elevenlabs.io/terms-of-use'), 'MIT': LicenseMeta(display_name='MIT License', url='https://opensource.org/license/mit'), 'Pixabay-Content': LicenseMeta(display_name='Pixabay Content License', url='https://pixabay.com/service/license-summary/'), 'RemArc': LicenseMeta(display_name='BBC RemArc Licence', url='https://sound-effects.bbcrewind.co.uk/licensing'), 'Sonniss-GDC': LicenseMeta(display_name='Sonniss GDC Game Audio Bundle License', url='https://sonniss.com/gdc-bundle-license'), 'Stability-Community': LicenseMeta(display_name='Stability AI Community License', url='https://stability.ai/community-license-agreement'), 'unknown': LicenseMeta(display_name='Unknown / unverified license', url=None), 'user-owned': LicenseMeta(display_name='User-owned / original work', url=None)}*

`license_id` -> display name + canonical URL (one row per
[`LICENSE_FLAGS`](#foley.licensing.LICENSE_FLAGS) key). Used only for human-readable credits; never for
permission decisions (those come from [`LICENSE_FLAGS`](#foley.licensing.LICENSE_FLAGS)).

* **Type:**
  SSOT

### *class* foley.licensing.LicenseFlags(commercial_ok=False, embed_in_derivative_ok=False, redistribute_standalone_ok=False, cache_bytes_ok=False, modification_ok=False, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The eight derivable flags for one `license_id` (the table row type).

### *class* foley.licensing.LicenseMeta(display_name, url=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Human-facing display metadata for one `license_id` (name + canonical URL).

The presentation sibling of [`LicenseFlags`](#foley.licensing.LicenseFlags): where `LicenseFlags` holds
the *permission* row consulted by [`keep()`](#foley.licensing.keep), `LicenseMeta` holds the
*display* row consulted by the credits/attribution layer
([`foley.provenance.credits`](foley.provenance.credits.html.md#module-foley.provenance.credits)). Kept here so `licensing` stays the single
license authority; a record’s own `license_name` / `license_url` (when a
source populated them) take precedence over this default.

### foley.licensing.UNKNOWN_LICENSE_FLAGS *= LicenseFlags(commercial_ok=False, embed_in_derivative_ok=False, redistribute_standalone_ok=False, cache_bytes_ok=False, modification_ok=False, ai_training_ok=False, requires_attribution=False, revenue_cap_usd=None)*

Fail-closed fallback for unknown / `Proprietary-*` license ids (all False, cap None).

### foley.licensing.UNKNOWN_LICENSE_META *= LicenseMeta(display_name='Unknown / unverified license', url=None)*

Fail-closed display fallback for unknown / `Proprietary-*` license ids.

### foley.licensing.apply_license_flags(record, , overrides=None)

Populate `record`’s eight derived flags from its `license_id`
(+ overrides), in place, and return it.

Does NOT touch `rights_verified` — verification is a separate concern.

* **Parameters:**
  * **record** ([`LicenseRecord`](foley.base.html.md#foley.base.LicenseRecord)) – The [`LicenseRecord`](foley.base.html.md#foley.base.LicenseRecord) to populate.
  * **overrides** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Optional per-source flag overrides (see
    [`derive_license_flags()`](#foley.licensing.derive_license_flags)).
* **Return type:**
  [`LicenseRecord`](foley.base.html.md#foley.base.LicenseRecord)
* **Returns:**
  The same (mutated) `record`.

### foley.licensing.derive_license_flags(license_id, , overrides=None)

Look up the flag set for a `license_id` (fail-closed fallback), then
apply per-source overrides.

* **Parameters:**
  * **license_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The normalized license id (SPDX or foley-specific token).
  * **overrides** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Optional per-source flag overrides — e.g. Freesound forces
    `cache_bytes_ok=False` on CC0. Keys must be `LicenseFlags` fields.
* **Return type:**
  [`LicenseFlags`](#foley.licensing.LicenseFlags)
* **Returns:**
  The resolved [`LicenseFlags`](#foley.licensing.LicenseFlags) (fallback = all-False
  `UNKNOWN_LICENSE_FLAGS` for unrecognized ids).
* **Raises:**
  [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `overrides` contains a key that is not a
      [`LicenseFlags`](#foley.licensing.LicenseFlags) field.

### foley.licensing.keep(record, intended_use)

Fail-closed candidate license gate (report 07 §8.2).

Run BEFORE ranking/verification in the agent’s `decide()`. Unknown or
unverified rights => reject. Any single unmet requirement => reject.

* **Parameters:**
  * **record** ([`LicenseRecord`](foley.base.html.md#foley.base.LicenseRecord)) – The candidate’s rights record.
  * **intended_use** ([`IntendedUse`](foley.base.html.md#foley.base.IntendedUse)) – The caller’s declared intent.
* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)
* **Returns:**
  `True` only if every requirement in `intended_use` is satisfied by
  `record`; `False` otherwise (including unverified rights).

### foley.licensing.keep_sound(sound_record, intended_use)

Convenience: apply [`keep()`](#foley.licensing.keep) to a `SoundRecord`’s nested license.

* **Parameters:**
  * **sound_record** – A [`SoundRecord`](foley.base.html.md#foley.base.SoundRecord) (its `.license` is the
    SSOT consulted).
  * **intended_use** ([`IntendedUse`](foley.base.html.md#foley.base.IntendedUse)) – The caller’s declared intent.
* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)
* **Returns:**
  The result of `keep(sound_record.license, intended_use)`.

### foley.licensing.license_id_from_cc_url(url)

Map a Creative-Commons license URL **or label** to `(license_id, verified)`.

The single SSOT for turning an external source’s license string into a foley
`license_id` (used by the FSD50K bulk adapter and the Freesound API adapter).
Recognized CC families map to their foley `license_id` with
`rights_verified=True`; anything unknown/missing fails closed to
`('unknown', False)` so [`keep()`](#foley.licensing.keep) drops it while its provenance is still
recorded.

Both representations Freesound uses are handled: the CC **URL** form
(`http://creativecommons.org/publicdomain/zero/1.0/`) and the plain **label**
the search API returns (`"Creative Commons 0"`, `"Attribution"`,
`"Attribution NonCommercial"`).

**Fail-closed for NoDerivatives / ShareAlike.** Any `-nd` / `-sa` variant —
including the `by-nc-nd` and `by-nc-sa` compounds — has NO foley
`LICENSE_FLAGS` row: its extra restrictions (no derivatives / share-alike) are
not expressible by any row we have, so it maps to `('unknown', False)` and is
rejected everywhere. This check runs first, so `by-nc-nd` / `by-nc-sa` are
NOT mis-mapped to plain `CC-BY-NC-4.0` (which would fail-open by granting the
modification / derivative / standalone-redistribution rights those licenses
forbid). Only *after* it are `by-nc` / `sampling` tested before the bare
`by`.

* **Parameters:**
  **url** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – A CC license URL, a CC label string, or `None`.
* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`bool`](https://docs.python.org/3/builtins/functions.html#bool)]
* **Returns:**
  `(license_id, rights_verified)` — `('unknown', False)` when
  unrecognized, missing, or a fail-closed ND/SA variant.

### foley.licensing.license_meta(license_id)

Return the display [`LicenseMeta`](#foley.licensing.LicenseMeta) for `license_id` (fail-closed fallback).

* **Parameters:**
  **license_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The normalized license id.
* **Return type:**
  [`LicenseMeta`](#foley.licensing.LicenseMeta)
* **Returns:**
  The mapped [`LicenseMeta`](#foley.licensing.LicenseMeta), or [`UNKNOWN_LICENSE_META`](#foley.licensing.UNKNOWN_LICENSE_META) for an
  unrecognized / `Proprietary-*` id.
