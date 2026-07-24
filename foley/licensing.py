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

from dataclasses import dataclass, replace
from typing import Optional

from .base import IntendedUse, LicenseRecord


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
    "CC-BY-4.0": LicenseFlags(True, True, True, True, True, True, True, None),
    "CC-BY-NC-4.0": LicenseFlags(False, True, True, True, True, False, True, None),
    # commercial only as a transformed sample -> default-exclude
    "CC-Sampling+-1.0": LicenseFlags(False, True, False, True, True, False, True, None),
    "RemArc": LicenseFlags(False, True, False, True, True, False, True, None),
    "Sonniss-GDC": LicenseFlags(True, True, False, True, True, False, False, None),
    "Pixabay-Content": LicenseFlags(True, True, False, True, True, False, False, None),
    # paid tier
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

#: Creative-Commons URL / label substrings, checked in order (NC and Sampling+
#: BEFORE the bare ``by`` so a compound license never mis-maps to plain CC-BY).
#: Each entry is ``(needle, license_id)``; a match sets ``rights_verified=True``.
_CC_URL_MARKERS: "tuple[tuple[tuple[str, ...], str], ...]" = (
    (("zero", "publicdomain", "creative commons 0", "cc0"), "CC0-1.0"),
    (("by-nc", "attribution noncommercial"), "CC-BY-NC-4.0"),
    (("sampling",), "CC-Sampling+-1.0"),
)


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
    for needles, license_id in _CC_URL_MARKERS:
        if any(n in u for n in needles):
            return license_id, True
    if "/by/" in u or u.rstrip("/").endswith("/by") or "attribution" in u:
        return "CC-BY-4.0", True
    return "unknown", False


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
    "CC-BY-4.0": LicenseMeta(
        "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"
    ),
    "CC-BY-NC-4.0": LicenseMeta(
        "CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"
    ),
    "CC-Sampling+-1.0": LicenseMeta(
        "CC Sampling+ 1.0", "https://creativecommons.org/licenses/sampling+/1.0/"
    ),
    "RemArc": LicenseMeta(
        "BBC RemArc Licence", "https://sound-effects.bbcrewind.co.uk/licensing"
    ),
    "Sonniss-GDC": LicenseMeta(
        "Sonniss GDC Game Audio Bundle License", "https://sonniss.com/gdc-bundle-license"
    ),
    "Pixabay-Content": LicenseMeta(
        "Pixabay Content License", "https://pixabay.com/service/license-summary/"
    ),
    "ElevenLabs-SFX": LicenseMeta(
        "ElevenLabs Sound Effects Terms", "https://elevenlabs.io/terms-of-use"
    ),
    "Stability-Community": LicenseMeta(
        "Stability AI Community License",
        "https://stability.ai/community-license-agreement",
    ),
    "MIT": LicenseMeta("MIT License", "https://opensource.org/license/mit"),
    "user-owned": LicenseMeta("User-owned / original work", None),
    "unknown": UNKNOWN_LICENSE_META,
}


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
    if intended_use.will_train and not record.ai_training_ok:
        return False
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
