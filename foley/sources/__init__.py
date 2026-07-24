"""Bulk-corpus source adapters for foley's SOURCE stage.

This package presents downloaded corpora (FSD50K, Clotho, FoleySet, and the
opt-in Sonniss / BBC RemArc) as an ingestable stream of clips + per-clip
licenses, consumed by :func:`foley.bootstrap.bootstrap`. Importing the package
registers every adapter in :data:`CORPUS_REGISTRY`.

The contract here is the narrow **bulk-corpus** :class:`CorpusAdapter` (enumerate
+ license, reusing the existing ingest pipeline); the live/HTTP
``SourceAdapter`` + ``SOURCE_CONFIG`` registry (Freesound tap, generation) is
subtask #5, which will *wrap* these, not replace them.
"""

from __future__ import annotations

from .base import (
    CORPUS_REGISTRY,
    ClipSpec,
    CorpusAdapter,
    UniformCorpus,
    bulk_license,
    corpora_in_rings,
    register_corpus,
    ring_of,
    select_corpora,
)

# Import each adapter module for its registration side effect + named export.
from .bbc_remarc import BBC_REMARC
from .clotho import CLOTHO, ClothoEvalCorpus
from .foleyset import FOLEYSET
from .fsd50k import FSD50K, Fsd50kCorpus
from .sonniss import SONNISS

__all__ = [
    "CORPUS_REGISTRY",
    "ClipSpec",
    "CorpusAdapter",
    "UniformCorpus",
    "bulk_license",
    "corpora_in_rings",
    "register_corpus",
    "ring_of",
    "select_corpora",
    "BBC_REMARC",
    "CLOTHO",
    "ClothoEvalCorpus",
    "FOLEYSET",
    "FSD50K",
    "Fsd50kCorpus",
    "SONNISS",
]
