"""License policy for foley: the license_id -> flag-set SSOT, flag derivation
(with per-source overrides), and the fail-closed candidate ``keep()`` gate.

Stdlib-only (imports only ``foley.base``). The dependency direction is one-way:
``licensing -> base``.

The two operational vs copyright flags are DISTINCT and must not be conflated:

    * ``redistribute_standalone_ok`` is a COPYRIGHT question (may the raw file be
      re-exposed standalone?).
    * ``cache_bytes_ok`` is a TOS/OPERATIONAL question (may foley persist the
      bytes at all?).

E.g. Freesound CC0 is legally redistributable yet its API TOS forbids caching,
so the Freesound adapter passes ``overrides={'cache_bytes_ok': False}`` — the
item is redistributable but stored by-reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

from .base import IntendedUse, LicenseRecord

#: The ONE rights intent every verb and surface defaults to (#63, maintainer decision
#: 2026-10-03): commercial publishing, attributable. NC and SA material is refused
#: unless a caller explicitly passes a different :class:`~foley.base.IntendedUse` (or
#: ``commercial_ok=False``). Treat it as read-only; copy with ``dataclasses.replace``.
DEFAULT_INTENDED_USE = IntendedUse(commercial=True, publish=True, can_attribute=True)


def intended_use_for(
    intended_use: Optional[IntendedUse] = None, *, commercial_ok: Optional[bool] = None
) -> IntendedUse:
    """The rights intent a verb runs under — every verb and surface resolves it here (#63).

    An explicit ``intended_use`` wins; else :data:`DEFAULT_INTENDED_USE`, with
    ``commercial`` overridden when ``commercial_ok`` is given (``False`` is the explicit
    opt-in to non-commercial material). Always a fresh copy, so callers may mutate it.
    """
    if intended_use is not None:
        return intended_use
    if commercial_ok is None:
        return replace(DEFAULT_INTENDED_USE)
    return replace(DEFAULT_INTENDED_USE, commercial=bool(commercial_ok))


@dataclass(frozen=True)
class LicenseFlags:
    """The eight derivable flags for one ``license_id`` (the table row type)."""

    commercial_ok: bool = False
    embed_in_derivative_ok: bool = False
    redistribute_standalone_ok: bool = False
    cache_bytes_ok: bool = False
    modification_ok: bool = False
    ai_training_ok: bool = False
    requires_attribution: bool = False
    revenue_cap_usd: Optional[int] = None


#: Fail-closed fallback for unknown / ``Proprietary-*`` license ids (all False, cap None).
UNKNOWN_LICENSE_FLAGS = LicenseFlags()

#: SSOT: ``license_id`` -> default flag set (report 07 §8.1 seed table).
#:
#: Order of ``LicenseFlags`` positional args::
#:
#:     commercial, embed, redistribute_standalone, cache_bytes, modification,
#:     ai_training, requires_attribution, revenue_cap_usd
LICENSE_FLAGS: dict[str, LicenseFlags] = {
    "CC0-1.0": LicenseFlags(True, True, True, True, True, True, False, None),
    # The Public Domain Mark is a LABEL ("believed free of copyright"), not a grant:
    # its flags are permissive, but license_id_from_cc_url never marks it verified, so
    # keep() refuses it until a human has checked the claim (#56).
    "PDM-1.0": LicenseFlags(True, True, True, True, True, True, False, None),
    # CC-BY / CC-BY-NC rows exist per version (rights do not differ across versions,
    # the credit does): see _CC_VERSIONED below, merged into this table after it.
    # commercial only as a transformed sample -> default-exclude
    "CC-Sampling+-1.0": LicenseFlags(False, True, False, True, True, False, True, None),
    "RemArc": LicenseFlags(False, True, False, True, True, False, True, None),
    "Sonniss-GDC": LicenseFlags(True, True, False, True, True, False, False, None),
    "Pixabay-Content": LicenseFlags(True, True, False, True, True, False, False, None),
    # ElevenLabs, by the account's plan (the same codes as `an`'s PROVIDER_TERMS). The
    # plan is never assumed: the adapter reads it from plan= / $FOLEY_ELEVENLABS_PLAN
    # and refuses to generate when it is unknown (#56).
    "elevenlabs-paid-plan": LicenseFlags(
        True, True, False, True, True, False, False, None
    ),
    # free plan: non-commercial, attribution required
    "elevenlabs-free-plan": LicenseFlags(
        False, True, False, True, True, False, True, None
    ),
    # LEGACY (records made before the plan was explicit): a paid plan was assumed.
    # Re-stamp them with foley.restamp_rights (see the CHANGELOG / PR for #56).
    "ElevenLabs-SFX": LicenseFlags(True, True, False, True, True, False, False, None),
    "Stability-Community": LicenseFlags(
        True, True, False, True, True, False, False, 1_000_000
    ),
    "MIT": LicenseFlags(True, True, True, True, True, True, True, None),
    # The user's own local content (default for `foley.ingest`): full rights and
    # cacheable => stored by-value. The natural contrast to a Freesound-API pull:
    # a Freesound sound keeps its own per-clip CC id (CC0-1.0 / CC-BY-4.0 / …) but
    # the adapter passes ``overrides={'cache_bytes_ok': False}`` to
    # :func:`apply_license_flags` because the Freesound API TOS forbids caching the
    # bytes even for CC0 — a by-reference override on top of the CC row, NOT a
    # separate flattened ``Freesound-API`` license_id (which would lose the per-CC
    # commercial/attribution variance). See ``foley.sources.freesound``.
    "user-owned": LicenseFlags(True, True, True, True, True, True, False, None),
    "unknown": UNKNOWN_LICENSE_FLAGS,
}

#: The CC versions foley has rows for (Freesound, FSD50K, Clotho and Wikimedia use these).
CC_VERSIONS: "tuple[str, ...]" = ("2.0", "2.5", "3.0", "4.0")

#: ``(family id prefix, URL path segment, display label, flags)`` for versioned CC families.
_CC_VERSIONED: "tuple[tuple[str, str, str, LicenseFlags], ...]" = (
    ("CC-BY", "by", "CC BY", LicenseFlags(True, True, True, True, True, True, True, None)),
    (
        "CC-BY-NC",
        "by-nc",
        "CC BY-NC",
        LicenseFlags(False, True, True, True, True, False, True, None),
    ),
)

LICENSE_FLAGS.update(
    {
        f"{prefix}-{v}": flags
        for prefix, _seg, _label, flags in _CC_VERSIONED
        for v in CC_VERSIONS
    }
)

#: Creative-Commons URL / label substrings, checked in order (NC and Sampling+
#: BEFORE the bare ``by`` so a compound license never mis-maps to plain CC-BY).
#: Each entry is ``(needle, license_id)``; a match sets ``rights_verified=True``.
_CC_URL_MARKERS: "tuple[tuple[tuple[str, ...], str], ...]" = (
    (("publicdomain/zero", "creative commons 0", "creative commons zero", "cc0"), "CC0-1.0"),
    # ``noncommercial`` subsumes the spaced label ("attribution noncommercial") AND the
    # hyphenated/bare forms ("Attribution-NonCommercial", "noncommercial"), so no NC work
    # slips through to the plain-CC-BY fallback below (which would fail OPEN by granting
    # commercial rights). Checked AFTER the -nd/-sa guard, so by-nc-nd/by-nc-sa still fail
    # closed. Mirrors the generic ND/SA needles.
    (("by-nc", "noncommercial"), "CC-BY-NC"),
    (("sampling",), "CC-Sampling+-1.0"),
)

#: Public Domain Mark needles (checked after CC0's ``publicdomain/zero``).
_PDM_MARKERS: "tuple[str, ...]" = ("publicdomain/mark", "public domain mark", "pdm")

#: A CC version in a URL (``/by/3.0/``) or a label (``Attribution 3.0``).
_CC_VERSION_RE = re.compile(r"(?<![\d.])([1-4]\.[05])(?![\d.])")

#: The version assumed when a source gives a CC family with no version at all
#: (Freesound's search labels: ``"Attribution"``). Rights are the same across versions;
#: only the credit's version is a guess, so the record keeps the label it was given.
DEFAULT_CC_VERSION = "4.0"


def license_id_from_cc_url(url: Optional[str]) -> "tuple[str, bool]":
    """Map a Creative-Commons license URL **or label** to ``(license_id, verified)``.

    The single SSOT for turning an external source's license string into a foley
    ``license_id`` (used by the FSD50K bulk adapter and the Freesound API adapter).
    Recognized CC families map to their foley ``license_id`` with
    ``rights_verified=True``; anything unknown/missing fails closed to
    ``('unknown', False)`` so :func:`keep` drops it while its provenance is still
    recorded.

    Both representations Freesound uses are handled: the CC **URL** form
    (``http://creativecommons.org/publicdomain/zero/1.0/``) and the plain **label**
    the search API returns (``"Creative Commons 0"``, ``"Attribution"``,
    ``"Attribution NonCommercial"``).

    **Fail-closed for NoDerivatives / ShareAlike.** Any ``-nd`` / ``-sa`` variant —
    including the ``by-nc-nd`` and ``by-nc-sa`` compounds — has NO foley
    ``LICENSE_FLAGS`` row: its extra restrictions (no derivatives / share-alike) are
    not expressible by any row we have, so it maps to ``('unknown', False)`` and is
    rejected everywhere. This check runs first, so ``by-nc-nd`` / ``by-nc-sa`` are
    NOT mis-mapped to plain ``CC-BY-NC-4.0`` (which would fail-open by granting the
    modification / derivative / standalone-redistribution rights those licenses
    forbid). Only *after* it are ``by-nc`` / ``sampling`` tested before the bare
    ``by``.

    **The version is kept** (#56): ``/by/3.0/`` maps to ``CC-BY-3.0`` and is credited
    as 3.0; a versionless label (``"Attribution"``) gets :data:`DEFAULT_CC_VERSION`.
    **The Public Domain Mark is not CC0**: it maps to ``PDM-1.0`` with
    ``rights_verified=False`` (a claim about the work, not a licence anyone granted).

    Args:
        url: A CC license URL, a CC label string, or ``None``.

    Returns:
        ``(license_id, rights_verified)`` — ``('unknown', False)`` when
        unrecognized, missing, or a fail-closed ND/SA variant.
    """
    if not url:
        return "unknown", False
    u = url.lower()
    # NoDerivatives / ShareAlike (and the nc-nd / nc-sa compounds) fail closed —
    # BEFORE the by-nc marker, which would otherwise substring-match 'by-nc-nd' /
    # 'by-nc-sa' and mis-map a stricter license to plain CC-BY-NC (fail-open).
    if any(marker in u for marker in ("-nd", "-sa", "noderiv", "sharealike")):
        return "unknown", False
    if any(n in u for n in _PDM_MARKERS) or (
        "publicdomain" in u and "zero" not in u
    ):
        return "PDM-1.0", False  # a label, not a grant: never auto-verified (#56)
    for needles, license_id in _CC_URL_MARKERS:
        if any(n in u for n in needles):
            return _versioned(license_id, u)
    if "/by/" in u or u.rstrip("/").endswith("/by") or "attribution" in u:
        return _versioned("CC-BY", u)
    return "unknown", False


def _versioned(family: str, url: str) -> "tuple[str, bool]":
    """``(family-version id, verified)`` for a versioned CC family; others pass through.

    The version comes from the URL or label; with none given, :data:`DEFAULT_CC_VERSION`.
    A version foley has no row for fails closed (``'unknown'``) rather than borrowing
    another version's credit.
    """
    if family not in {prefix for prefix, *_ in _CC_VERSIONED}:
        return family, True
    m = _CC_VERSION_RE.search(url)
    version = m.group(1) if m else DEFAULT_CC_VERSION
    license_id = f"{family}-{version}"
    if license_id not in LICENSE_FLAGS:
        return "unknown", False
    return license_id, True


# ---------------------------------------------------------------------------
# License display metadata — the license_id -> (human name, canonical URL) SSOT
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LicenseMeta:
    """Human-facing display metadata for one ``license_id`` (name + canonical URL).

    The presentation sibling of :class:`LicenseFlags`: where ``LicenseFlags`` holds
    the *permission* row consulted by :func:`keep`, ``LicenseMeta`` holds the
    *display* row consulted by the credits/attribution layer
    (:mod:`foley.provenance.credits`). Kept here so ``licensing`` stays the single
    license authority; a record's own ``license_name`` / ``license_url`` (when a
    source populated them) take precedence over this default.
    """

    display_name: str
    url: Optional[str] = None


#: Fail-closed display fallback for unknown / ``Proprietary-*`` license ids.
UNKNOWN_LICENSE_META = LicenseMeta("Unknown / unverified license", None)

#: SSOT: ``license_id`` -> display name + canonical URL (one row per
#: :data:`LICENSE_FLAGS` key). Used only for human-readable credits; never for
#: permission decisions (those come from :data:`LICENSE_FLAGS`).
LICENSE_META: dict[str, LicenseMeta] = {
    "CC0-1.0": LicenseMeta(
        "CC0 1.0 Universal (Public Domain Dedication)",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    "PDM-1.0": LicenseMeta(
        "Public Domain Mark 1.0 (unverified claim)",
        "https://creativecommons.org/publicdomain/mark/1.0/",
    ),
    "CC-Sampling+-1.0": LicenseMeta(
        "CC Sampling+ 1.0", "https://creativecommons.org/licenses/sampling+/1.0/"
    ),
    "RemArc": LicenseMeta(
        "BBC RemArc Licence", "https://sound-effects.bbcrewind.co.uk/licensing"
    ),
    "Sonniss-GDC": LicenseMeta(
        "Sonniss GDC Game Audio Bundle License",
        "https://sonniss.com/gdc-bundle-license",
    ),
    "Pixabay-Content": LicenseMeta(
        "Pixabay Content License", "https://pixabay.com/service/license-summary/"
    ),
    "elevenlabs-paid-plan": LicenseMeta(
        "ElevenLabs Terms (paid plan)", "https://elevenlabs.io/terms-of-use"
    ),
    "elevenlabs-free-plan": LicenseMeta(
        "ElevenLabs Terms (free plan: non-commercial, attribution required)",
        "https://elevenlabs.io/terms-of-use",
    ),
    "ElevenLabs-SFX": LicenseMeta(
        "ElevenLabs Sound Effects Terms (legacy: paid plan assumed)",
        "https://elevenlabs.io/terms-of-use",
    ),
    "Stability-Community": LicenseMeta(
        "Stability AI Community License",
        "https://stability.ai/community-license-agreement",
    ),
    "MIT": LicenseMeta("MIT License", "https://opensource.org/license/mit"),
    "user-owned": LicenseMeta("User-owned / original work", None),
    "unknown": UNKNOWN_LICENSE_META,
}

LICENSE_META.update(
    {
        f"{prefix}-{v}": LicenseMeta(
            f"{label} {v}", f"https://creativecommons.org/licenses/{seg}/{v}/"
        )
        for prefix, seg, label, _flags in _CC_VERSIONED
        for v in CC_VERSIONS
    }
)


def license_meta(license_id: str) -> LicenseMeta:
    """Return the display :class:`LicenseMeta` for ``license_id`` (fail-closed fallback).

    Args:
        license_id: The normalized license id.

    Returns:
        The mapped :class:`LicenseMeta`, or :data:`UNKNOWN_LICENSE_META` for an
        unrecognized / ``Proprietary-*`` id.
    """
    return LICENSE_META.get(license_id, UNKNOWN_LICENSE_META)


def derive_license_flags(
    license_id: str, *, overrides: Optional[dict] = None
) -> LicenseFlags:
    """Look up the flag set for a ``license_id`` (fail-closed fallback), then
    apply per-source overrides.

    Args:
        license_id: The normalized license id (SPDX or foley-specific token).
        overrides: Optional per-source flag overrides — e.g. Freesound forces
            ``cache_bytes_ok=False`` on CC0. Keys must be ``LicenseFlags`` fields.

    Returns:
        The resolved :class:`LicenseFlags` (fallback = all-False
        ``UNKNOWN_LICENSE_FLAGS`` for unrecognized ids).

    Raises:
        ValueError: If ``overrides`` contains a key that is not a
            :class:`LicenseFlags` field.
    """
    flags = LICENSE_FLAGS.get(license_id, UNKNOWN_LICENSE_FLAGS)
    if overrides:
        allowed = {f for f in LicenseFlags.__dataclass_fields__}
        bad = set(overrides) - allowed
        if bad:
            raise ValueError(f"Unknown license flag override(s): {sorted(bad)}")
        flags = replace(flags, **overrides)
    return flags


def apply_license_flags(
    record: LicenseRecord, *, overrides: Optional[dict] = None
) -> LicenseRecord:
    """Populate ``record``'s eight derived flags from its ``license_id``
    (+ overrides), in place, and return it.

    Does NOT touch ``rights_verified`` — verification is a separate concern.

    Args:
        record: The :class:`~foley.base.LicenseRecord` to populate.
        overrides: Optional per-source flag overrides (see
            :func:`derive_license_flags`).

    Returns:
        The same (mutated) ``record``.
    """
    f = derive_license_flags(record.license_id, overrides=overrides)
    record.commercial_ok = f.commercial_ok
    record.embed_in_derivative_ok = f.embed_in_derivative_ok
    record.redistribute_standalone_ok = f.redistribute_standalone_ok
    record.cache_bytes_ok = f.cache_bytes_ok
    record.modification_ok = f.modification_ok
    record.ai_training_ok = f.ai_training_ok
    record.requires_attribution = f.requires_attribution
    record.revenue_cap_usd = f.revenue_cap_usd
    return record


# ---------------------------------------------------------------------------
# AI-use scope (Freesound's gen_ai_preference, #69)
# ---------------------------------------------------------------------------

#: The ``ai_training_scope`` values (``None`` = no narrowing beyond ``ai_training_ok``).
AI_TRAINING_SCOPES: "tuple[str, ...]" = (
    "none",
    "open_source_only",
    "nc_open_source_only",
)

#: Freesound ``gen_ai_preference`` -> ``(ai_training_ok override, ai_training_scope)``.
#: ``None`` as the override leaves the CC row's flag alone. An unlisted value fails
#: closed (see :func:`ai_scope_from_gen_ai_preference`).
GEN_AI_PREFERENCE_SCOPES: "dict[str, tuple[Optional[bool], Optional[str]]]" = {
    "no-additional-preferences": (None, None),
    "open-source-models": (None, "open_source_only"),
    "noncommercial-open-source-models": (None, "nc_open_source_only"),
    "no-gen-ai": (False, "none"),
}


def ai_scope_from_gen_ai_preference(
    preference: Optional[str],
) -> "tuple[Optional[bool], Optional[str]]":
    """Map a Freesound ``gen_ai_preference`` to ``(ai_training_ok override, scope)``.

    All four published values are honoured (only ``no-gen-ai`` was before #69). A
    missing value means no stated preference; an unrecognised one fails closed.
    """
    if preference is None:
        return None, None
    return GEN_AI_PREFERENCE_SCOPES.get(preference, (False, "none"))


def ai_use_permitted(
    record: LicenseRecord, *, open_source_model: bool, commercial: bool
) -> bool:
    """Whether AI use of the sound (CLAP-embedding it counts) is allowed here.

    ``ai_training_ok`` must hold, and the record's ``ai_training_scope`` must admit
    this use: ``open_source_only`` needs an open-source model, ``nc_open_source_only``
    also needs a non-commercial purpose, ``none`` admits nothing.

    Args:
        record: The rights record.
        open_source_model: Whether the model using the audio is open source (the
            embedder's ``open_source`` attribute; LAION-CLAP is).
        commercial: Whether the purpose is commercial (foley's default intent).
    """
    if not record.ai_training_ok:
        return False
    scope = record.ai_training_scope
    if scope is None:
        return True
    if scope == "open_source_only":
        return open_source_model
    if scope == "nc_open_source_only":
        return open_source_model and not commercial
    return False  # 'none' or an unrecognised scope: fail closed


def keep(record: LicenseRecord, intended_use: IntendedUse) -> bool:
    """Fail-closed candidate license gate (report 07 §8.2).

    Run BEFORE ranking/verification in the agent's ``decide()``. Unknown or
    unverified rights => reject. Any single unmet requirement => reject.

    Args:
        record: The candidate's rights record.
        intended_use: The caller's declared intent.

    Returns:
        ``True`` only if every requirement in ``intended_use`` is satisfied by
        ``record``; ``False`` otherwise (including unverified rights).
    """
    if not record.rights_verified:
        return False
    if intended_use.commercial and not record.commercial_ok:
        return False
    if intended_use.publish and not record.embed_in_derivative_ok:
        return False
    if intended_use.redistribute_standalone and not record.redistribute_standalone_ok:
        return False
    if intended_use.will_train and not ai_use_permitted(
        record, open_source_model=False, commercial=intended_use.commercial
    ):
        return False  # the trainer's model is unknown here, so a scoped grant fails closed
    cap = record.revenue_cap_usd
    if cap is not None and intended_use.revenue_usd >= cap:
        return False
    if record.requires_attribution and not intended_use.can_attribute:
        return False
    if not intended_use.allow_voice_or_trademark and (
        record.contains_recognizable_voice or record.potential_trademark
    ):
        return False
    return True


def keep_sound(sound_record, intended_use: IntendedUse) -> bool:
    """Convenience: apply :func:`keep` to a ``SoundRecord``'s nested license.

    Args:
        sound_record: A :class:`~foley.base.SoundRecord` (its ``.license`` is the
            SSOT consulted).
        intended_use: The caller's declared intent.

    Returns:
        The result of ``keep(sound_record.license, intended_use)``.
    """
    return keep(sound_record.license, intended_use)
