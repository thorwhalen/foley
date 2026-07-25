"""Install foley's shipped agent kit — the consumer skill + Claude slash command + subagent.

``pip install foley`` ships an agent-facing kit under ``foley/data/``: the
``foley-sound-design`` skill (``gh skill``-installable), a ``/foley-score`` slash command, and a
``sound-designer`` subagent. :func:`install_agent_kit` copies them into a target ``.claude/``
directory so an agent host (Claude Code) discovers them — the "ready to use out of the box" step
for the AI-first surface. Stdlib-only, so importing this keeps ``import foley`` dol-only.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _data_dir() -> Path:
    """The shipped ``foley/data`` directory (resolves from a source tree or an installed wheel)."""
    from importlib.resources import files

    return Path(str(files("foley"))) / "data"


def install_agent_kit(dest="./.claude", *, overwrite: bool = False) -> "list[str]":
    """Copy the shipped skill + slash command + subagent into ``dest`` (a ``.claude`` dir).

    Installs:

    * ``dest/skills/foley-sound-design/`` — the consumer skill (the sound-design playbook),
    * ``dest/commands/foley-score.md`` — the ``/foley-score`` slash command,
    * ``dest/agents/sound-designer.md`` — the ``sound-designer`` subagent.

    Args:
        dest: The target agent-config dir (default ``./.claude`` in the cwd; pass ``~/.claude``
            to install globally for every project).
        overwrite: Replace existing files/dirs (default: skip what already exists).

    Returns:
        The list of installed paths (as strings) — empty entries that already existed are skipped.
    """
    data = _data_dir()
    dest_dir = Path(dest).expanduser()
    installed: "list[str]" = []

    # the skill is a directory
    dst_skill = dest_dir / "skills" / "foley-sound-design"
    if overwrite or not dst_skill.exists():
        if dst_skill.exists():
            shutil.rmtree(dst_skill)
        dst_skill.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(data / "skills" / "foley-sound-design", dst_skill)
        installed.append(str(dst_skill))

    # the slash command + subagent are single files
    for src_sub, target_sub, name in (
        ("claude/commands", "commands", "foley-score.md"),
        ("claude/agents", "agents", "sound-designer.md"),
    ):
        dst = dest_dir / target_sub / name
        if not overwrite and dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(data / src_sub / name, dst)
        installed.append(str(dst))

    return installed
