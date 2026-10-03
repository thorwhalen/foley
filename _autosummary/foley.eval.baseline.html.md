# foley.eval.baseline

The committed nDCG baseline — the PR gate’s SSOT + staleness stamps.

The gate blocks a PR whose `ndcg@10` falls below `value - tolerance` (report
08 §5). The baseline is a committed **number** (not a frozen per-clip run, which
would be BLAS-drift-fragile across the CI matrix), stamped with the sha256 of the
golden seed + the Ring-0 manifest: if either fixture is edited, the stamp
mismatches and the harness warns “baseline stale — run `foley eval
--update-baseline`”, so a metric shift is attributable to the *system*, not a
silently-shifted corpus. Re-baselining is a deliberate, reviewable one-line diff.

### Module Attributes

| [`DEFAULT_BASELINE_PATH`](#foley.eval.baseline.DEFAULT_BASELINE_PATH)   | Package data dir (ships in the wheel); the baseline lives beside the seed.        |
|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| [`DEFAULT_TOLERANCE`](#foley.eval.baseline.DEFAULT_TOLERANCE)       | The regression tolerance from report 08 §5 (Δ [nDCG@10](mailto:nDCG@10) ≥ −0.02). |

### Functions

| [`is_stale`](#foley.eval.baseline.is_stale)(baseline, \*, seed_path, manifest_path)   | True if the baseline's fixture stamps no longer match the fixtures on disk.   |
|-----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`load_baseline`](#foley.eval.baseline.load_baseline)([path])                              | Load the committed baseline dict from `path`.                                 |
| [`write_baseline`](#foley.eval.baseline.write_baseline)(report, \*[, path, metric, ...])    | Write a fresh baseline from `report` (the `--update-baseline` action).        |

### foley.eval.baseline.DEFAULT_BASELINE_PATH *= PosixPath('/home/runner/work/foley/foley/foley/data/golden/baseline.json')*

Package data dir (ships in the wheel); the baseline lives beside the seed.

### foley.eval.baseline.DEFAULT_TOLERANCE *= 0.02*

The regression tolerance from report 08 §5 (Δ [nDCG@10](mailto:nDCG@10) ≥ −0.02).

### foley.eval.baseline.is_stale(baseline, , seed_path, manifest_path)

True if the baseline’s fixture stamps no longer match the fixtures on disk.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### foley.eval.baseline.load_baseline(path=PosixPath('/home/runner/work/foley/foley/foley/data/golden/baseline.json'))

Load the committed baseline dict from `path`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### foley.eval.baseline.write_baseline(report, , path=PosixPath('/home/runner/work/foley/foley/foley/data/golden/baseline.json'), metric='ndcg@10', tolerance=0.02, seed_path, manifest_path, embedder_model_id='foley-eval/hashing-bow-v1', dim=64, rrf_k=60, updated_at, n_items, revision='gld-v1')

Write a fresh baseline from `report` (the `--update-baseline` action).

Records the mean metric value plus sha256 stamps of the seed + manifest so a
later fixture edit is detected. `updated_at` is passed in (not read from the
clock) so the caller controls reproducibility. `revision` labels the golden-set
generation (bumped when the frozen set is regrown).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  The baseline dict that was written.
