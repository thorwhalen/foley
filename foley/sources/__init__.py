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
    SourceAdapter,
    UniformCorpus,
    api_license,
    bulk_license,
    corpora_in_rings,
    register_corpus,
    ring_of,
    select_corpora,
)

# Import each bulk-corpus adapter module for its registration side effect + export.
from .bbc_remarc import BBC_REMARC
from .clotho import CLOTHO, ClothoEvalCorpus
from .foleyset import FOLEYSET
from .fsd50k import FSD50K, Fsd50kCorpus
from .sonniss import SONNISS

# Live-source contract (#5): registry auto-discovery + the add_from pull facade.
# The freesound adapter package is NOT imported here — it is auto-discovered
# lazily by discover_sources()/get_source(), keeping `import foley` light.
from .pull import add_from
from .registry import (
    SOURCE_REGISTRY,
    discover_sources,
    get_source,
    list_sources,
    register_source,
)

__all__ = [
    # bulk-corpus contract (#4)
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
    # live-source contract (#5)
    "SourceAdapter",
    "api_license",
    "add_from",
    "SOURCE_REGISTRY",
    "discover_sources",
    "get_source",
    "list_sources",
    "register_source",
]
