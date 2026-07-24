"""Stable Audio Open 1.0 generate source (local default; #6).

Auto-discovered by :func:`foley.sources.registry.discover_sources`, which imports
ONLY :mod:`~foley.sources.stable_audio.config` (stdlib-only — no ``torch`` /
``diffusers``). The :class:`~foley.sources.stable_audio.adapter.StableAudioAdapter`
and its heavy ML stack (the ``foley[stable-audio]`` extra) load on first use — never
at ``import foley`` or during discovery — via the module ``__getattr__`` below.
"""

from __future__ import annotations

from .config import SOURCE_CONFIG

__all__ = ["Adapter", "StableAudioAdapter", "SOURCE_CONFIG"]


def __getattr__(name: str):
    """Lazily import the adapter so importing this package stays torch-free."""
    if name in ("Adapter", "StableAudioAdapter"):
        from .adapter import StableAudioAdapter

        return StableAudioAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
