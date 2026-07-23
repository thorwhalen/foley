"""foley INDEX stage — make every sound findable by keyword *and* meaning.

The retrieval keystone (report 04 / report 10 §5): a CLAP joint embedding space,
a hybrid vector+keyword index with Reciprocal Rank Fusion, a ``dol``-native
:class:`SoundLibrary` façade composing the byte/metadata stores with the two
indexes, and the UCS/AudioSet taxonomy resolver — all behind small, swappable
protocols with zero-config defaults.

Everything heavy (``torch``/``transformers``/``lancedb``/``sqlite_vec``) is
lazy-imported inside the method that needs it, so ``import foley.index`` costs
only the stdlib; install the capability you use via the matching extra
(``foley[clap]``, ``foley[index]``, ``foley[index-sqlite]``).
"""

from . import taxonomy
from .embedders import (
    CLAP_SAMPLE_RATE,
    DEFAULT_CLAP_DIM,
    DEFAULT_CLAP_MODEL_ID,
    ClapEmbedder,
    default_embedder,
)
from .indexes import (
    LanceIndex,
    MemoryIndex,
    SqliteVecIndex,
    default_index,
    lancedb_available,
    sqlite_vec_loadable,
)
from .library import SoundLibrary, default_library
from .protocols import Embedder, KeywordIndex, VectorIndex
from .search import (
    DEFAULT_CANDIDATE_K,
    RRF_K,
    FusedHit,
    fuse_hits,
    hybrid_search,
    reciprocal_rank_fusion,
    vector_search,
)
from .taxonomy import CatIdResolution, parse_ucs_filename, resolve_catid

__all__ = [
    # protocols
    "Embedder",
    "VectorIndex",
    "KeywordIndex",
    # embedders
    "ClapEmbedder",
    "default_embedder",
    "DEFAULT_CLAP_MODEL_ID",
    "DEFAULT_CLAP_DIM",
    "CLAP_SAMPLE_RATE",
    # index backends
    "MemoryIndex",
    "LanceIndex",
    "SqliteVecIndex",
    "default_index",
    "lancedb_available",
    "sqlite_vec_loadable",
    # search / fusion
    "RRF_K",
    "DEFAULT_CANDIDATE_K",
    "FusedHit",
    "reciprocal_rank_fusion",
    "fuse_hits",
    "hybrid_search",
    "vector_search",
    # library façade
    "SoundLibrary",
    "default_library",
    # taxonomy
    "taxonomy",
    "resolve_catid",
    "parse_ucs_filename",
    "CatIdResolution",
]
