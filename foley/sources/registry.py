"""Live-source adapter registry: auto-discovery + lazy loading (arioso's registry, ported).

Scans :mod:`foley.sources` for sub-**packages** that declare a ``SOURCE_CONFIG``
(a ``config.py`` with the plugin declaration), registers them, and lazily imports
+ instantiates each adapter only on first use. Mirrors ``arioso.registry`` /
``PLATFORM_CONFIG`` (report 10 §4.1).

This is the **live-source** registry (Freesound; hosted generators in #6) — a
*separate* registry from the bulk-corpus
:data:`foley.sources.base.CORPUS_REGISTRY`. The two adapter kinds have different
contracts (``search`` / ``get`` / ``download`` vs ``iter_clips`` /
``resolve_license``) and different façades (:func:`foley.add_from` vs
:func:`foley.bootstrap`). They stay disjoint **by construction**: discovery only
picks up sub-packages (``ispkg`` and not ``_``-prefixed), so the flat bulk-corpus
modules (``fsd50k.py`` …) and the flat helper modules here (``base``, ``http``,
``pull``, ``registry``) are never cross-captured.

Out-of-tree plugins — and test doubles — register directly via
:func:`register_source` (no package needed).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Optional

#: name -> {"config": dict, "adapter": object | None (lazy), "module": str | None}.
_SOURCE_REGISTRY: "dict[str, dict]" = {}

#: Public read alias of the registry (callers/tests inspect discovered sources).
SOURCE_REGISTRY = _SOURCE_REGISTRY


def discover_sources() -> "list[str]":
    """Scan :mod:`foley.sources` sub-packages for a ``SOURCE_CONFIG`` and register them.

    A valid live source is a sub-package of :mod:`foley.sources` (``ispkg`` and
    not ``_``-prefixed) whose ``config.py`` defines a ``SOURCE_CONFIG`` dict with a
    ``name``. Flat modules (bulk-corpus adapters + helpers) are skipped, so this
    never cross-captures the corpus adapters. Only ``config.py`` is imported here
    (stdlib-cheap); the adapter loads lazily in :func:`get_source`. Idempotent —
    an already-registered name (e.g. a test double) is never overwritten.

    Returns:
        The list of discovered source names.
    """
    from . import __path__ as sources_path  # the foley.sources package search path

    discovered: "list[str]" = []
    for _finder, modname, ispkg in pkgutil.iter_modules(sources_path):
        if not ispkg or modname.startswith("_"):
            continue
        try:
            config_module = importlib.import_module(f"foley.sources.{modname}.config")
        except ImportError:
            continue  # a package without an importable config.py is not a source
        config = getattr(config_module, "SOURCE_CONFIG", None)
        if isinstance(config, dict) and config.get("name"):
            name = config["name"]
            _SOURCE_REGISTRY.setdefault(
                name, {"config": config, "adapter": None, "module": modname}
            )
            discovered.append(name)
    return discovered


def register_source(name: str, config: dict, adapter=None) -> None:
    """Register a live source directly (out-of-tree plugin or a test double).

    Overwrites any existing entry for ``name`` — the seam a test uses to inject a
    fake-transport-backed adapter. If ``adapter`` is ``None`` it is lazily built
    from ``config`` on first :func:`get_source` (the source must then be an
    importable ``foley.sources.<name>`` package).

    Args:
        name: The source name (the :func:`add_from` / :func:`get_source` key).
        config: The ``SOURCE_CONFIG`` declaration.
        adapter: An optional pre-instantiated adapter (bypasses lazy loading).
    """
    _SOURCE_REGISTRY[name] = {"config": config, "adapter": adapter, "module": None}


def get_source(name: str) -> dict:
    """Return the ``{'config', 'adapter'}`` entry for ``name``, lazily building the adapter.

    Runs a discovery pass if ``name`` is not yet known, then instantiates the
    adapter on first use (cached in the entry).

    Args:
        name: The source name.

    Returns:
        The registry entry (``{'config': dict, 'adapter': SourceAdapter, ...}``).

    Raises:
        KeyError: If no such source is registered (after discovery).
    """
    if name not in _SOURCE_REGISTRY:
        discover_sources()
    if name not in _SOURCE_REGISTRY:
        raise KeyError(
            f"Unknown source {name!r}. Known: {sorted(_SOURCE_REGISTRY)}. "
            "Register out-of-tree sources with register_source(name, config, adapter)."
        )
    entry = _SOURCE_REGISTRY[name]
    if entry.get("adapter") is None:
        entry["adapter"] = _load_adapter(entry.get("module") or name, entry["config"])
    return entry


def list_sources() -> "list[str]":
    """Return the names of all registered live sources (runs discovery first)."""
    discover_sources()
    return sorted(_SOURCE_REGISTRY)


def _load_adapter(module: Optional[str], config: dict):
    """Import ``foley.sources.<module>.adapter`` and instantiate its ``Adapter``.

    The adapter module exposes an ``Adapter`` class taking the ``config`` dict
    (the arioso convention). Raises an informative error if the module or class is
    absent — a source with no adapter cannot be pulled from.
    """
    adapter_module = importlib.import_module(f"foley.sources.{module}.adapter")
    adapter_class = getattr(adapter_module, "Adapter", None)
    if adapter_class is None:
        raise TypeError(
            f"source {module!r} exposes no 'Adapter' class in its adapter module"
        )
    return adapter_class(config)
