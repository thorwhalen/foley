"""Freesound APIv2 retrieve source — CC0 sounds, stored by-reference (``foley[freesound]``).

Declares :data:`SOURCE_CONFIG` (auto-discovered by
:mod:`foley.sources.registry`) and the :class:`FreesoundAdapter` (aliased
``Adapter`` for the registry's lazy loader). Importing this package is dol-only —
and it is also **discovery-light**: :func:`foley.sources.registry.discover_sources`
imports only ``config.py``, so ``adapter.py`` (and, later, its lazy ``requests``)
is not loaded until an adapter is actually built. To preserve that, the adapter
classes are exposed via a module-level ``__getattr__`` rather than eagerly imported
here.
"""

from __future__ import annotations

from .config import SOURCE_CONFIG

__all__ = ["Adapter", "FreesoundAdapter", "SOURCE_CONFIG"]


def __getattr__(name: str):
    """Lazily expose ``Adapter`` / ``FreesoundAdapter`` (loads ``adapter.py`` on demand)."""
    if name in ("Adapter", "FreesoundAdapter"):
        from . import adapter as _adapter

        return getattr(_adapter, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
