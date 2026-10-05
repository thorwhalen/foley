# foley.runtime

Runtime posture — local-first / offline mode as one verifiable contract (#12, report 12).

`RuntimeConfig` couples the three things “offline” must mean into a single frozen,
inspectable value, each a **consumer of an existing SSOT** (no parallel policy):

* **data egress** — `data_egress_allow` filters the source registry by each adapter’s
  already-declared `config['data_egress']` (`foley.sources` SSOT), so a network
  adapter is simply not available offline.
* **telemetry** — `telemetry=False` disables the observability run-artifact export
  (`foley.obs`), so nothing leaves the device.
* **redaction** — `redaction_mode` routes narration-derived fields through the ready
  `foley.obs.redact.REDACT_FIELDS` redactor, so prompts/queries/narration never sit
  in even a local run store.

[`offline()`](#foley.runtime.offline) (`offline_scope`) applies the posture for the duration of a `with`
block via a [`contextvars.ContextVar`](https://docs.python.org/3/library/contextvars.html#contextvars.ContextVar) and **restores** the prior obs state on
exit — per-call granularity, not a process-global flip. Stdlib-only, so importing this
keeps `import foley` dol-only.

### Module Attributes

| [`LOCAL`](#foley.runtime.LOCAL)   | The egress classes a source may declare (`config['data_egress']` SSOT).   |
|----------------------------------------------------------|---------------------------------------------------------------------------|

### Functions

| [`current_runtime`](#foley.runtime.current_runtime)()                                  | The active [`RuntimeConfig`](#foley.runtime.RuntimeConfig); outside any scope, the one `$FOLEY_OFFLINE` selects.   |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| [`is_offline`](#foley.runtime.is_offline)()                                       | Whether an offline runtime scope is currently active.                                                                             |
| [`load_pretrained`](#foley.runtime.load_pretrained)(loader, model_id, \*[, ...])       | Call `loader(model_id, **kwargs)` — a `from_pretrained` — honouring the posture.                                                  |
| [`no_download`](#foley.runtime.no_download)(what, \*, how_to_fetch)                | Under an offline posture, forbid outbound connections in this context for the block.                                              |
| [`offline`](#foley.runtime.offline)([config])                                  | Alias of [`offline_scope()`](#foley.runtime.offline_scope) — `with foley.offline(): ...` for local-first runs.     |
| [`offline_scope`](#foley.runtime.offline_scope)([config])                            | Apply a [`RuntimeConfig`](#foley.runtime.RuntimeConfig) for the `with` block, restoring obs state on exit.         |
| [`require_egress`](#foley.runtime.require_egress)(data_egress, \*, what)              | Raise [`EgressBlocked`](#foley.runtime.EgressBlocked) unless the active runtime allows `data_egress`.              |
| [`require_local_files`](#foley.runtime.require_local_files)(paths, \*, what, how_to_fetch) | Under an offline posture, raise [`ModelNotCached`](#foley.runtime.ModelNotCached) unless every path exists.         |
| [`runtime_scope`](#foley.runtime.runtime_scope)(config)                              | Make `config` the current posture for the block — the ContextVar only.                                                            |

### Classes

| [`RuntimeConfig`](#foley.runtime.RuntimeConfig)([offline, data_egress_allow, ...])   | A frozen runtime posture — the local-first / offline contract as data.   |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|

### Exceptions

| [`EgressBlocked`](#foley.runtime.EgressBlocked)   | Raised when a call would send data off the device under an offline posture.     |
|------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`ModelNotCached`](#foley.runtime.ModelNotCached)  | Raised under an offline posture when a model's weights are not on this machine. |

### *exception* foley.runtime.EgressBlocked

Bases: [`PermissionError`](https://docs.python.org/3/builtins/exceptions.html#PermissionError)

Raised when a call would send data off the device under an offline posture.

Every external path checks the active [`RuntimeConfig`](#foley.runtime.RuntimeConfig) through
[`require_egress()`](#foley.runtime.require_egress) — the source registry, the generate and pull façades, and
the LLM resolver — so `with foley.offline():` holds on every surface, not only
in the MCP tools.

### foley.runtime.LOCAL *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'local'*

The egress classes a source may declare (`config['data_egress']` SSOT).

### *exception* foley.runtime.ModelNotCached

Bases: [`EgressBlocked`](#foley.runtime.EgressBlocked)

Raised under an offline posture when a model’s weights are not on this machine.

foley never downloads weights inside [`offline()`](#foley.runtime.offline) (#86); the message names the
model and how to fetch it beforehand, online.

### *class* foley.runtime.RuntimeConfig(offline=False, data_egress_allow=<factory>, telemetry=True, redaction_mode='hash', http_resilience=True)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A frozen runtime posture — the local-first / offline contract as data.

* **Parameters:**
  * **offline** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Whether this posture is offline/local-first.
  * **data_egress_allow** ([`frozenset`](https://docs.python.org/3/builtins/stdtypes.html#frozenset)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – The egress classes a source may use to be available
    (`{'local'}` offline; `{'local','external'}` online).
  * **telemetry** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Whether the obs run-artifact export is on.
  * **redaction_mode** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `'hash'` (default, salted), `'off'` (drop), or `'full'`
    (raw — local-debug only).
  * **http_resilience** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Whether HTTP source adapters are wrapped with the
    throttle/backoff/circuit-breaker ([`foley.sources.resilience`](foley.sources.resilience.html.md#module-foley.sources.resilience)).

#### allows(data_egress)

Whether a source declaring `data_egress` is available under this posture.

An unknown/absent declaration is **rejected** (fail-closed): a source that does
not say where its data goes is never used offline.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### *classmethod* default()

The online default: all egress allowed, telemetry on, hashed redaction.

* **Return type:**
  [`RuntimeConfig`](#foley.runtime.RuntimeConfig)

#### *classmethod* from_env()

Build from the environment: `FOLEY_OFFLINE` in {1,true,yes} → offline-local.

* **Return type:**
  [`RuntimeConfig`](#foley.runtime.RuntimeConfig)

#### *classmethod* offline_local()

The local-first offline posture: local-only egress, telemetry off, hashed redaction.

* **Return type:**
  [`RuntimeConfig`](#foley.runtime.RuntimeConfig)

### foley.runtime.current_runtime()

The active [`RuntimeConfig`](#foley.runtime.RuntimeConfig); outside any scope, the one `$FOLEY_OFFLINE` selects.

* **Return type:**
  [`RuntimeConfig`](#foley.runtime.RuntimeConfig)

### foley.runtime.is_offline()

Whether an offline runtime scope is currently active.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### foley.runtime.load_pretrained(loader, model_id, , how_to_fetch=None, \*\*kwargs)

Call `loader(model_id, **kwargs)` — a `from_pretrained` — honouring the posture.

Online, it is a plain call. Under [`offline()`](#foley.runtime.offline) it passes
`local_files_only=True` (no Hub request at all) and turns a cache miss (an
`OSError`) into [`ModelNotCached`](#foley.runtime.ModelNotCached); any other error passes through as is.
foley’s `from_pretrained` loads (CLAP, Stable Audio) go through here; loaders
with no local-only switch (AudioSeal, whisperX) go through [`no_download()`](#foley.runtime.no_download).

* **Parameters:**
  * **loader** – e.g. `ClapModel.from_pretrained`.
  * **model_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The Hub repo id.
  * **how_to_fetch** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – The pre-download instruction for the error (default: the
    `huggingface-cli download` command).
  * **\*\*kwargs** – Passed to `loader`.

### foley.runtime.no_download(what, , how_to_fetch)

Under an offline posture, forbid outbound connections in this context for the block.

For model loaders that have no local-only switch (AudioSeal, whisperX): inside the
block a non-loopback connection or name lookup made from this context is refused,
and an error whose cause is that refusal is re-raised as [`ModelNotCached`](#foley.runtime.ModelNotCached)
naming `what` and `how_to_fetch`. A cached model still loads (the libraries fall
back to their cache when the network is refused); an unrelated error passes through
unchanged. Online it does nothing. Threads a loader starts itself do not inherit
the block (they start with a fresh context); the loaders guarded here make their
first request from the calling thread.

### foley.runtime.offline(config=None)

Alias of [`offline_scope()`](#foley.runtime.offline_scope) — `with foley.offline(): ...` for local-first runs.

### foley.runtime.offline_scope(config=None)

Apply a [`RuntimeConfig`](#foley.runtime.RuntimeConfig) for the `with` block, restoring obs state on exit.

Defaults to [`RuntimeConfig.offline_local()`](#foley.runtime.RuntimeConfig.offline_local). Disables telemetry export and sets
the redaction mode for the scope; the prior obs enabled-state and redaction mode are
captured on entry and restored on exit (so a scope never leaks its posture).

* **Parameters:**
  **config** ([`RuntimeConfig`](#foley.runtime.RuntimeConfig) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – The posture to apply (default: offline-local).
* **Yields:**
  The applied [`RuntimeConfig`](#foley.runtime.RuntimeConfig).

### foley.runtime.require_egress(data_egress, , what)

Raise [`EgressBlocked`](#foley.runtime.EgressBlocked) unless the active runtime allows `data_egress`.

* **Parameters:**
  * **data_egress** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – The egress class the call needs (`'local'` | `'external'`);
    `None` (undeclared) is always refused — callers that read a source’s
    declaration map a missing one to `'external'` first.
  * **what** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A short description for the error (`"source 'elevenlabs'"`).
* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### foley.runtime.require_local_files(paths, , what, how_to_fetch, min_bytes=None)

Under an offline posture, raise [`ModelNotCached`](#foley.runtime.ModelNotCached) unless every path exists.

`min_bytes` maps a path to the size below which the library would re-download it
(a truncated download), so such a file counts as missing too.

For model files a library downloads itself (PANNs fetches its checkpoint and label
CSV with `wget`, even at import), checked before that library is touched.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### foley.runtime.runtime_scope(config)

Make `config` the current posture for the block — the ContextVar only.

Unlike [`offline_scope()`](#foley.runtime.offline_scope) it leaves the process-wide obs settings alone (safe to
enter from many threads at once); telemetry still follows the posture, because
[`foley.obs.is_enabled()`](foley.obs.html.md#foley.obs.is_enabled) reads [`current_runtime()`](#foley.runtime.current_runtime).
