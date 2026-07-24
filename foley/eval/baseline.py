"""The committed nDCG baseline — the PR gate's SSOT + staleness stamps.

The gate blocks a PR whose ``ndcg@10`` falls below ``value - tolerance`` (report
08 §5). The baseline is a committed **number** (not a frozen per-clip run, which
would be BLAS-drift-fragile across the CI matrix), stamped with the sha256 of the
golden seed + the Ring-0 manifest: if either fixture is edited, the stamp
mismatches and the harness warns "baseline stale — run ``foley eval
--update-baseline``", so a metric shift is attributable to the *system*, not a
silently-shifted corpus. Re-baselining is a deliberate, reviewable one-line diff.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

#: Package data dir (ships in the wheel); the baseline lives beside the seed.
DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "golden" / "baseline.json"
)

#: The regression tolerance from report 08 §5 (Δ nDCG@10 ≥ −0.02).
DEFAULT_TOLERANCE = 0.02


def _sha256(path) -> str:
    """Hex sha256 of a fixture, newline-normalized (empty string if missing).

    Normalizing CRLF/CR → LF before hashing makes the stamp invariant to a
    Windows autocrlf checkout — the sha detects a *content* edit, not a
    line-ending flavour. A no-op on the committed LF fixtures.
    """
    p = Path(path)
    if not p.exists():
        return ""
    data = p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def load_baseline(path=DEFAULT_BASELINE_PATH) -> dict:
    """Load the committed baseline dict from ``path``."""
    return json.loads(Path(path).read_text())


def is_stale(baseline: dict, *, seed_path, manifest_path) -> bool:
    """True if the baseline's fixture stamps no longer match the fixtures on disk."""
    golden = baseline.get("golden", {})
    corpus = baseline.get("corpus", {})
    return golden.get("seed_sha256") != _sha256(seed_path) or corpus.get(
        "manifest_sha256"
    ) != _sha256(manifest_path)


def write_baseline(
    report,
    *,
    path=DEFAULT_BASELINE_PATH,
    metric: str = "ndcg@10",
    tolerance: float = DEFAULT_TOLERANCE,
    seed_path,
    manifest_path,
    embedder_model_id: str = "foley-eval/hashing-bow-v1",
    dim: int = 64,
    rrf_k: int = 60,
    updated_at: str,
    n_items: int,
) -> dict:
    """Write a fresh baseline from ``report`` (the ``--update-baseline`` action).

    Records the mean metric value plus sha256 stamps of the seed + manifest so a
    later fixture edit is detected. ``updated_at`` is passed in (not read from the
    clock) so the caller controls reproducibility.

    Returns:
        The baseline dict that was written.
    """
    baseline = {
        "metric": metric,
        "value": round(float(report.mean.get(metric, 0.0)), 6),
        "tolerance": tolerance,
        "system": {
            "embedder": embedder_model_id,
            "dim": dim,
            "rrf_k": rrf_k,
            "backend": "memory",
        },
        "corpus": {
            "name": "ring0",
            "manifest_sha256": _sha256(manifest_path),
        },
        "golden": {
            "revision": "gld-v1",
            "n_items": n_items,
            "seed_sha256": _sha256(seed_path),
        },
        "updated_at": updated_at,
    }
    Path(path).write_text(json.dumps(baseline, indent=2) + "\n")
    return baseline
