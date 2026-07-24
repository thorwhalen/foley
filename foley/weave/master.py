"""Mastering — loudness-normalize + true-peak-limit the finished mix (report 06 §5).

Normalises the whole program to a :class:`~foley.base.MasterProfile` integrated-loudness
target (ITU-R BS.1770-4 / EBU R128 via ``pyloudnorm``) and holds an inter-sample
**true-peak** ceiling. It reuses :func:`foley.audio.loudness_normalize` (the same
BS.1770 meter Tier-0 QC uses) for the LUFS stage and :func:`foley.qc.true_peak_dbtp`
(oversampled) for the ceiling — so ``pyloudnorm`` comes from the existing ``audio``
extra (no redundant dependency) and is imported function-locally, keeping ``import
foley.weave`` dol-only.

The default ``engine='auto'`` masters fully in-process (portable, testable). A
two-pass ``ffmpeg loudnorm`` path (the "guarantee the numbers" master, report 06
§5.4) is a reserved upgrade behind :func:`foley.weave.requirements.check_requirements`;
until it lands, ``engine='ffmpeg'`` / ``'auto'`` degrade to the in-process path.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from ..base import MasterProfile
from .mix import db_to_lin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from numpy import ndarray


@dataclass
class MasterReport:
    """What the master stage did — a JSON-serialisable audit row for the run-artifact."""

    target_lufs: float
    input_lufs: float
    output_lufs: float
    true_peak_dbtp: float
    true_peak_ceiling_db: float
    gain_db: float
    limited: bool
    engine: str

    def to_dict(self) -> dict:
        """Return the plain-dict form (for ``WeaveResult.master_report`` / obs)."""
        return asdict(self)


def _measure_lufs(samples: "ndarray", sample_rate: int) -> float:
    """Integrated loudness (LUFS) of ``samples``; ``-inf`` when too short to gate."""
    import pyloudnorm as pyln

    if samples.shape[0] < math.ceil(0.4 * sample_rate):
        return float("-inf")
    return float(pyln.Meter(sample_rate).integrated_loudness(samples))


def _true_peak_limit(
    mix: "ndarray", sample_rate: int, ceiling_db: float
) -> "tuple[ndarray, float, bool]":
    """Scale ``mix`` so its inter-sample true peak sits at/below ``ceiling_db``.

    Returns ``(mix, true_peak_dbtp, limited)``. A true-peak-safe *scale* (not a
    lookahead limiter) — simple, deterministic, and never raises the ceiling.
    """
    import numpy as np

    from ..qc import true_peak_dbtp

    tp = true_peak_dbtp(mix, sample_rate)
    if not np.isfinite(tp) or tp <= ceiling_db:
        return mix, tp, False
    out = mix * db_to_lin(ceiling_db - tp)
    return out, true_peak_dbtp(out, sample_rate), True


def master(
    mix: "ndarray",
    sample_rate: int,
    profile: MasterProfile,
    *,
    engine: str = "auto",
) -> "tuple[ndarray, MasterReport]":
    """Master ``mix`` to ``profile`` — LUFS-normalise then true-peak-limit (report 06 §5).

    Args:
        mix: The summed working mix (stereo ``(frames, 2)`` float32).
        sample_rate: Sample rate in Hz.
        profile: The :class:`~foley.base.MasterProfile` (target LUFS / true-peak / LRA).
        engine: ``'auto'``/``'inprocess'`` master in-process (default). ``'ffmpeg'``
            is reserved (report 06 §5.4) and currently degrades to in-process.

    Returns:
        ``(mastered_mix, MasterReport)``. Loudness is measured before and after so the
        report is a faithful audit; when a true-peak limit engages, output LUFS may
        sit slightly below target (peak-safety wins over exact loudness).
    """
    from ..audio import loudness_normalize

    normalized, input_lufs = loudness_normalize(
        mix,
        sample_rate,
        target_lufs=profile.target_lufs,
        peak_ceiling_dbfs=profile.true_peak_db,
    )
    limited_mix, tp, limited = _true_peak_limit(
        normalized, sample_rate, profile.true_peak_db
    )
    output_lufs = _measure_lufs(limited_mix, sample_rate)
    gain_db = (
        output_lufs - input_lufs
        if math.isfinite(output_lufs) and math.isfinite(input_lufs)
        else 0.0
    )
    report = MasterReport(
        target_lufs=profile.target_lufs,
        input_lufs=input_lufs,
        output_lufs=output_lufs,
        true_peak_dbtp=tp,
        true_peak_ceiling_db=profile.true_peak_db,
        gain_db=gain_db,
        limited=limited,
        engine="inprocess",
    )
    return limited_mix, report
