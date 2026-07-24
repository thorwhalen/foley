"""BBC RemArc (Rewind Archive) — a Ring-2, quarantined corpus.

The BBC Rewind sound-effects archive (report 11 §1.4) is released under the
**RemArc** license: personal / educational / research use only — ``commercial_ok
= False`` **and** ``ai_training_ok = False`` (two hard flags). It is a Ring-2
corpus: web-only (no bulk API), so the user must have downloaded the WAVs
themselves, and it is refused by the fail-closed ingest gate unless the operator
passes explicit consent (``accept_ai_restricted=True``).
"""

from __future__ import annotations

from .base import UniformCorpus, register_corpus

#: The BBC RemArc Ring-2 adapter (non-commercial AND ai_training_ok=False).
BBC_REMARC = register_corpus(
    UniformCorpus(
        name="bbc_remarc",
        ring=2,
        default_license_id="RemArc",
        source="bbc_remarc",
        rights_verified=True,
    )
)
