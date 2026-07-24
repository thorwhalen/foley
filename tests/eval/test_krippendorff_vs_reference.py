"""Opt-in oracle: foley's pure-numpy Krippendorff's α == the ``krippendorff`` PyPI package.

The guarantee that lets foley hand-roll α (report 08 §2.3) without shipping the PyPI
package into CI: the shipped implementation is proven equal to the reference here, and
this test is SKIPPED in CI (``krippendorff`` is not in the ``test`` extra) — it runs only
where it is installed. Mirrors ``tests/eval/test_metrics_vs_ranx.py``.
"""

import pytest

np = pytest.importorskip("numpy")
kd = pytest.importorskip("krippendorff")

from foley.eval.reliability import krippendorff_alpha  # noqa: E402

_N_TRIALS = 200
_LEVELS = ("nominal", "ordinal", "interval")


def _random_matrix(rng):
    """A random (raters × units) ordinal matrix with ~20% missing ratings."""
    n_raters = int(rng.integers(2, 5))
    n_units = int(rng.integers(4, 12))
    data = rng.integers(0, 4, size=(n_raters, n_units)).astype(float)
    data[rng.random((n_raters, n_units)) < 0.2] = np.nan
    # guard: every unit needs ≥ 2 present ratings for a defined coincidence
    for u in range(n_units):
        if np.sum(~np.isnan(data[:, u])) < 2:
            data[:2, u] = rng.integers(0, 4, size=2)
    return data


def test_krippendorff_alpha_matches_reference():
    """foley's α equals the reference package across random trials and all levels."""
    rng = np.random.default_rng(20260724)
    for _ in range(_N_TRIALS):
        data = _random_matrix(rng)
        for level in _LEVELS:
            mine = krippendorff_alpha(data, level=level)
            ref = float(kd.alpha(reliability_data=data, level_of_measurement=level))
            assert mine == pytest.approx(ref, abs=1e-9), (level, mine, ref)
