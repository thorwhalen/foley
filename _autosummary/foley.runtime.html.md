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

| [`current_runtime`](#foley.runtime.current_runtime)()       | The active [`RuntimeConfig`](#foley.runtime.RuntimeConfig), or the online default outside any scope.           |
|--------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| [`is_offline`](#foley.runtime.is_offline)()            | Whether an offline runtime scope is currently active.                                                                         |
| [`offline`](#foley.runtime.offline)([config])       | Alias of [`offline_scope()`](#foley.runtime.offline_scope) — `with foley.offline(): ...` for local-first runs. |
| [`offline_scope`](#foley.runtime.offline_scope)([config]) | Apply a [`RuntimeConfig`](#foley.runtime.RuntimeConfig) for the `with` block, restoring obs state on exit.     |

### Classes

| [`RuntimeConfig`](#foley.runtime.RuntimeConfig)([offline, data_egress_allow, ...])   | A frozen runtime posture — the local-first / offline contract as data.   |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|

### foley.runtime.LOCAL *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'local'*

The egress classes a source may declare (`config['data_egress']` SSOT).

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

The active [`RuntimeConfig`](#foley.runtime.RuntimeConfig), or the online default outside any scope.

* **Return type:**
  [`RuntimeConfig`](#foley.runtime.RuntimeConfig)

### foley.runtime.is_offline()

Whether an offline runtime scope is currently active.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

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
