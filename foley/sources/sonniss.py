"""Sonniss GameAudioGDC — a Ring-2, quarantined corpus.

Sonniss GameAudioGDC (report 11 §1.3) is a large, commercially-usable SFX drop,
BUT its license **prohibits using the audio to train AI/ML models** — and
CLAP-embedding + persisting a corpus into foley's index is exactly that kind of
derivation. So it is licensed ``Sonniss-GDC`` (``commercial_ok=True`` but
``ai_training_ok=False``) and lives in **Ring 2**: never fetched, never in the
default bootstrap rings, and refused by the fail-closed ingest gate unless the
operator passes explicit consent (``accept_ai_restricted=True``).

The user points the adapter at their own downloaded Sonniss tree; foley never
downloads or bundles it.
"""

from __future__ import annotations

from .base import UniformCorpus, register_corpus

#: The Sonniss Ring-2 adapter (ai_training_ok=False → quarantined by default).
SONNISS = register_corpus(
    UniformCorpus(
        name="sonniss",
        ring=2,
        default_license_id="Sonniss-GDC",
        source="sonniss",
        rights_verified=True,
    )
)
