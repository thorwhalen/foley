# foley.agent_kit

Install foley’s shipped agent kit — the consumer skill + Claude slash command + subagent.

`pip install foley` ships an agent-facing kit under `foley/data/`: the
`foley-sound-design` skill (`gh skill`-installable), a `/foley-score` slash command, and a
`sound-designer` subagent. [`install_agent_kit()`](#foley.agent_kit.install_agent_kit) copies them into a target `.claude/`
directory so an agent host (Claude Code) discovers them — the “ready to use out of the box” step
for the AI-first surface. Stdlib-only, so importing this keeps `import foley` dol-only.

### Functions

| [`install_agent_kit`](#foley.agent_kit.install_agent_kit)([dest, overwrite])   | Copy the shipped skill + slash command + subagent into `dest` (a `.claude` dir).   |
|-----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|

### foley.agent_kit.install_agent_kit(dest='./.claude', , overwrite=False)

Copy the shipped skill + slash command + subagent into `dest` (a `.claude` dir).

Installs:

* `dest/skills/foley-sound-design/` — the consumer skill (the sound-design playbook),
* `dest/commands/foley-score.md` — the `/foley-score` slash command,
* `dest/agents/sound-designer.md` — the `sound-designer` subagent.

* **Parameters:**
  * **dest** – The target agent-config dir (default `./.claude` in the cwd; pass `~/.claude`
    to install globally for every project).
  * **overwrite** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Replace existing files/dirs (default: skip what already exists).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
* **Returns:**
  The list of installed paths (as strings) — empty entries that already existed are skipped.
