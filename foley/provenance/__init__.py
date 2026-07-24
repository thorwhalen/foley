"""Provenance layer for foley — attribution/credits (and, later, disclosure).

This subpackage keeps published output legal and traceable. Its first half (#9a)
is :mod:`foley.provenance.credits` — the stdlib-only TASL attribution / credits
generator (``CREDITS.md`` + JSON manifest) that reads the ``LicenseRecord`` SSOT.

The sibling ``disclosure.py`` (#9b, after generation lands) — AudioSeal
watermarking, C2PA content-credential writers, and the EU AI Act Art. 50
disclosure checklist — is intentionally NOT imported here so ``import foley``
stays dependency-light; it arrives with the ``foley[provenance]`` extra.
"""

from __future__ import annotations

from .credits import (
    CreditEntry,
    Credits,
    attribution_line,
    credit_entry,
    credits_for,
    credits_manifest,
    render_credits_md,
)

__all__ = [
    "CreditEntry",
    "Credits",
    "attribution_line",
    "credit_entry",
    "credits_for",
    "credits_manifest",
    "render_credits_md",
]
