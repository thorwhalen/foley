"""Onboarding — check what foley needs, tell the user how to get it (accompy-style, #12).

Generalizes WEAVE's binary-only :mod:`foley.weave.requirements` into a single
capability audit across everything foley can optionally use: **system binaries**
(``ffmpeg`` / ``rubberband`` — reused verbatim from the WEAVE SSOT), **API keys**
(derived from each source adapter's declared ``config['auth']`` — one SSOT for the env
var + sign-up URL), and **importable extras** (``py2mcp`` for the MCP server, the CLAP /
index / provenance stacks). A :class:`~foley.weave.requirements.Requirement` carries a
``probe`` discriminator (``binary`` / ``env`` / ``importable``) so one dispatch handles
all three. Nothing here runs an installer — it surfaces the exact per-platform command
or sign-up URL so the user (or agent) can opt in. Stdlib-only; keeps ``import foley``
dol-only.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys

from .weave.requirements import REQUIREMENTS as _WEAVE_REQUIREMENTS
from .weave.requirements import Requirement, _install_hint

#: Extra LLM/agent API key not tied to a source adapter (the SELECT agent's real path).
_ANTHROPIC_KEY = Requirement(
    name="ANTHROPIC_API_KEY",
    purpose="the LLM-backed SELECT agent (foley[agent]); the deterministic fakes need no key",
    url="https://console.anthropic.com/settings/keys",
    install={},
    probe="env",
)

#: Importable extras that unlock a capability when installed.
_IMPORTABLE_REQUIREMENTS = {
    "py2mcp": Requirement(
        name="py2mcp",
        purpose="serve foley to agents over MCP (foley[mcp])",
        url="https://pypi.org/project/py2mcp/",
        install={"any": "pip install 'foley[mcp]'"},
        probe="importable",
    ),
}

#: How each ``probe`` kind checks availability.
_PROBES = {
    "binary": lambda name: shutil.which(name) is not None,
    "env": lambda name: bool(os.environ.get(name)),
    "importable": lambda name: importlib.util.find_spec(name) is not None,
}


def _derive_key_requirements() -> "dict[str, Requirement]":
    """Derive the per-source API-key requirements from each ``SOURCE_CONFIG['auth']``.

    The env-var name and sign-up URL live in the source config (SSOT), so this never
    hard-codes them. Sources with no ``auth`` (e.g. local stable-audio) contribute none.
    """
    from .sources.registry import SOURCE_REGISTRY, discover_sources

    discover_sources()
    reqs: "dict[str, Requirement]" = {}
    for name, entry in SOURCE_REGISTRY.items():
        auth = entry["config"].get("auth") or {}
        env_var = auth.get("env_var")
        if not env_var:
            continue
        reqs[env_var] = Requirement(
            name=env_var,
            purpose=f"the {name} source adapter (foley[{name}])",
            url=auth.get("apply_url", ""),
            install={},
            probe="env",
        )
    return reqs


def build_requirements() -> "dict[str, Requirement]":
    """Assemble the full requirement set: system binaries + API keys + importable extras."""
    reqs: "dict[str, Requirement]" = dict(_WEAVE_REQUIREMENTS)  # ffmpeg / rubberband
    reqs.update(
        _derive_key_requirements()
    )  # FREESOUND_API_KEY / ELEVENLABS_API_KEY / …
    reqs[_ANTHROPIC_KEY.name] = _ANTHROPIC_KEY
    reqs.update(_IMPORTABLE_REQUIREMENTS)  # py2mcp
    return reqs


def _available(req: Requirement) -> bool:
    """Whether ``req`` is satisfied, dispatching on its ``probe``."""
    return _PROBES.get(req.probe, _PROBES["binary"])(req.name)


def check_requirements(
    *, names: "tuple[str, ...] | None" = None, verbose: bool = False
) -> "dict[str, bool]":
    """Report which optional foley capabilities are available (``{name: is_available}``).

    Args:
        names: Which requirements to check (default: the full assembled set).
        verbose: If ``True``, print an actionable hint for each missing requirement.

    Returns:
        ``{requirement_name: available}``. Everything-absent is fine — foley degrades
        (deterministic fakes, offline mode, in-process DSP); the report just shows what
        each capability would unlock.
    """
    reqs = build_requirements()
    keys = names or tuple(reqs)
    status: "dict[str, bool]" = {}
    for key in keys:
        req = reqs[key]
        ok = _available(req)
        status[key] = ok
        if verbose and not ok:
            hint = _install_hint(req) if req.install else (req.url or "(set it)")
            print(f"[foley] optional: {req.name} — {req.purpose}\n    get it: {hint}")
    return status


def verify_and_setup(*, names: "tuple[str, ...] | None" = None) -> "dict[str, dict]":
    """Return a per-requirement status + guidance report (never runs an installer).

    Returns:
        ``{name: {'available', 'purpose', 'install', 'url', 'probe'}}``.
    """
    reqs = build_requirements()
    keys = names or tuple(reqs)
    report: "dict[str, dict]" = {}
    for key in keys:
        req = reqs[key]
        report[key] = {
            "available": _available(req),
            "purpose": req.purpose,
            "install": _install_hint(req) if req.install else "",
            "url": req.url,
            "probe": req.probe,
        }
    return report


def capability_report(*, runtime=None) -> dict:
    """A JSON-safe capability + posture snapshot for the CLI, docs, and the MCP tool.

    Groups requirements into ``keys`` (env), ``extras`` (importable), ``system``
    (binary), adds the current offline posture and the available source list, and
    lists ``degraded_tools`` — capabilities whose requirement is unmet.

    Args:
        runtime: A :class:`foley.runtime.RuntimeConfig` (default: the active one).

    Returns:
        ``{keys, extras, system, offline, sources, degraded_tools}`` — all JSON-safe.
    """
    from .runtime import current_runtime
    from .sources.registry import list_sources

    cfg = runtime or current_runtime()
    reqs = build_requirements()
    groups = {"env": {}, "importable": {}, "binary": {}}
    degraded: "list[str]" = []
    for name, req in reqs.items():
        ok = _available(req)
        groups.get(req.probe, groups["binary"])[name] = ok
        if not ok:
            degraded.append(name)
    return {
        "keys": groups["env"],
        "extras": groups["importable"],
        "system": groups["binary"],
        "offline": cfg.offline,
        "sources": list_sources(egress_allow=cfg.data_egress_allow),
        "degraded_tools": sorted(degraded),
    }
