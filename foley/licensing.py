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
    "unknown": UNKNOWN_LICENSE_FLAGS,
}


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
