"""ElevenLabs Sound Effects generate source (hosted; #6).

Auto-discovered by :func:`foley.sources.registry.discover_sources`, which imports
ONLY :mod:`~foley.sources.elevenlabs.config` (stdlib-only). The
:class:`~foley.sources.elevenlabs.adapter.ElevenLabsAdapter` and its lazy
``requests`` dependency (the ``foley[elevenlabs]`` extra) load on first use — never
at ``import foley`` or during discovery — via the module ``__getattr__`` below.
"""

from __future__ import annotations

from .config import SOURCE_CONFIG

__all__ = ["Adapter", "ElevenLabsAdapter", "SOURCE_CONFIG"]


def __getattr__(name: str):
    """Lazily import the adapter so importing this package stays requests-free."""
    if name in ("Adapter", "ElevenLabsAdapter"):
        from .adapter import ElevenLabsAdapter

        return ElevenLabsAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
