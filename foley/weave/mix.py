"""Pure-numpy mixing DSP — making a clip sit under the voice (report 06 §3).

Deterministic, testable, shell-out-free primitives for the WEAVE mixer: level
(gain staging), envelope-follower ducking, constant-power panning, a distance
recipe (attenuation + air-absorption low-pass), a pure-numpy reverb send,
equal-power crossfades / declicks, seamless loop/trim to a duration, and overlay.

Everything operates on the working representation (``float32``, time on axis 0);
the mix graph is **stereo** ``(frames, 2)`` so panning composes — :func:`constant_power_pan`
is the mono→stereo point. ``numpy`` is imported lazily inside each function so
``import foley.weave`` stays dol-only (mirroring :mod:`foley.audio`). Nothing here
reaches for ``scipy``/``pyroomacoustics``; those are optional-upgrade paths for a
later slice behind ``foley[weave]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..base import Layer

if TYPE_CHECKING:  # pragma: no cover - typing only
    from numpy import ndarray

# --- Dialogue-relative default levels (report 06 §3.1), as named constants ------
ONE_SHOT_GAIN_DB: float = -9.0  # foreground one-shots: -6..-12 dB under the voice
AMBIENCE_GAIN_DB: float = -21.0  # ambience beds: -18..-24 dB under the voice
STINGER_GAIN_DB: float = -6.0  # non-diegetic stingers: prominent but < voice
DUCK_DB: float = -10.0  # ducking depth under speech (report 06 §3.2: ~8-12 dB)
DUCK_ATTACK_S: float = 0.02  # side-chain attack (report 06 §3.2)
DUCK_RELEASE_S: float = 0.3  # side-chain release (report 06 §3.2)

#: Base per-layer gain (dB, relative to the voice bus at 0 dB). The render applies
#: this before each item's own ``processing.gain_db`` so levels have a sane default.
LAYER_GAIN_DB: "dict[Layer, float]" = {
    Layer.voice: 0.0,
    Layer.sfx_fg: ONE_SHOT_GAIN_DB,
    Layer.ambience: AMBIENCE_GAIN_DB,
    Layer.stinger: STINGER_GAIN_DB,
    Layer.music: AMBIENCE_GAIN_DB,
}

#: Attenuation (dB) applied at maximum distance (distance == 1.0); ~inverse-distance.
DISTANCE_MAX_ATTEN_DB: float = -12.0
#: Air-absorption one-pole low-pass coefficient at maximum distance (0 = none, →1 = darkest).
DISTANCE_MAX_LP: float = 0.85
#: Reverb-send impulse-response length (seconds) and decay time-constant.
REVERB_IR_S: float = 0.18
REVERB_TAU_S: float = 0.05


def db_to_lin(db: float) -> float:
    """Convert decibels to a linear amplitude factor (``10 ** (db/20)``)."""
    return float(10.0 ** (db / 20.0))


def _as_stereo(clip: "ndarray") -> "ndarray":
    """Return ``clip`` as ``(frames, 2)`` (mono is duplicated across channels)."""
    import numpy as np

    if clip.ndim == 1:
        return np.stack([clip, clip], axis=1)
    if clip.shape[1] == 1:
        return np.repeat(clip, 2, axis=1)
    if clip.shape[1] == 2:
        return clip
    mono = clip.mean(axis=1)
    return np.stack([mono, mono], axis=1)


def constant_power_pan(clip: "ndarray", pan: float) -> "ndarray":
    """Pan a (mono or stereo) clip to a stereo image with a constant-power law (report 06 §3.3).

    ``L = cos(θ)``, ``R = sin(θ)`` with ``θ = (pan+1)·π/4`` and ``pan ∈ [-1, 1]``, so
    ``L² + R²`` (perceived loudness) stays flat across the field — no ~3 dB centre dip.

    Args:
        clip: Mono ``(frames,)`` or stereo ``(frames, 2)`` working array.
        pan: -1 (hard left) .. 0 (centre) .. +1 (hard right).

    Returns:
        A stereo ``(frames, 2)`` array.
    """
    import numpy as np

    mono = clip if clip.ndim == 1 else clip.mean(axis=1)
    theta = (float(np.clip(pan, -1.0, 1.0)) + 1.0) * (np.pi / 4.0)
    gains = np.array([np.cos(theta), np.sin(theta)], dtype=mono.dtype)
    return mono[:, None] * gains[None, :]


def speech_duck_gain(
    n_samples: int,
    sample_rate: int,
    speech_spans: "list[tuple[float, float]]",
    *,
    duck_db: float = DUCK_DB,
    attack: float = DUCK_ATTACK_S,
    release: float = DUCK_RELEASE_S,
) -> "ndarray":
    """Build a (linear) gain envelope that dips to ``duck_db`` during speech spans (report 06 §3.2).

    A one-pole attack/release smooths the transitions so the bed dips and recovers
    without clicks. Deterministic and testable — the envelope-follower alternative to
    ``ffmpeg sidechaincompress``.

    Args:
        n_samples: Length of the bed bus in samples.
        sample_rate: Sample rate in Hz.
        speech_spans: ``[(start_s, end_s), ...]`` from the word timeline.
        duck_db: Attenuation depth during speech (negative dB).
        attack: Attack time constant (seconds) as the bed drops.
        release: Release time constant (seconds) as the bed recovers.

    Returns:
        A ``(n_samples,)`` linear gain envelope in ``[db_to_lin(duck_db), 1.0]``.
    """
    import numpy as np

    g = np.ones(n_samples, dtype="float32")
    duck = db_to_lin(duck_db)
    for start, end in speech_spans:
        a = max(0, int(start * sample_rate))
        b = min(n_samples, int(end * sample_rate))
        if b > a:
            g[a:b] = duck
    ca = float(np.exp(-1.0 / max(1e-9, attack * sample_rate)))
    cr = float(np.exp(-1.0 / max(1e-9, release * sample_rate)))
    out = np.empty_like(g)
    acc = 1.0
    for i in range(n_samples):
        target = g[i]
        coef = ca if target < acc else cr
        acc = target + coef * (acc - target)
        out[i] = acc
    return out


def _one_pole_lowpass(clip: "ndarray", coef: float) -> "ndarray":
    """Apply a one-pole low-pass ``y[n] = (1-c)·x[n] + c·y[n-1]`` along axis 0."""
    import numpy as np

    if coef <= 0.0:
        return clip
    x = clip if clip.ndim == 2 else clip[:, None]
    out = np.empty_like(x)
    prev = np.zeros(x.shape[1], dtype=x.dtype)
    one_minus = 1.0 - coef
    for n in range(x.shape[0]):
        prev = one_minus * x[n] + coef * prev
        out[n] = prev
    return out if clip.ndim == 2 else out[:, 0]


def apply_distance(clip: "ndarray", sample_rate: int, distance: float) -> "ndarray":
    """Apply a distance recipe: attenuation + air-absorption low-pass (report 06 §3.4).

    Distance reads as a *combination* of cues: quieter (~inverse-distance) and duller
    (a low-pass, as air absorbs highs). The reverb component of distance is applied
    separately via :func:`reverb_send`. ``distance == 0`` is a no-op.

    Args:
        clip: Working array (mono or stereo).
        sample_rate: Sample rate in Hz (kept for API symmetry / future filters).
        distance: 0 (near) .. 1 (far).

    Returns:
        The attenuated, low-passed clip (a new array; input not mutated).
    """
    d = max(0.0, min(1.0, distance))
    if d == 0.0:
        return clip
    out = clip * db_to_lin(DISTANCE_MAX_ATTEN_DB * d)
    return _one_pole_lowpass(out, DISTANCE_MAX_LP * d)


def reverb_send(clip: "ndarray", sample_rate: int, amount: float) -> "ndarray":
    """Mix a pure-numpy exponential-decay reverb tail into ``clip`` (report 06 §3.5).

    A deterministic dry/wet blend: the clip is convolved with a short
    exponentially-decaying impulse response and mixed back at ``amount``. This is the
    zero-dependency default; ``pyroomacoustics`` / recorded-IR convolution is the
    optional ``foley[weave]`` upgrade. ``amount == 0`` is a no-op (fully dry).

    Args:
        clip: Working array (mono or stereo).
        sample_rate: Sample rate in Hz.
        amount: 0 (dry) .. 1 (fully wet).

    Returns:
        The dry/wet-blended clip (a new array; input not mutated).
    """
    import numpy as np

    a = max(0.0, min(1.0, amount))
    if a == 0.0:
        return clip
    n_ir = max(1, int(REVERB_IR_S * sample_rate))
    t = np.arange(n_ir, dtype="float32")
    ir = np.exp(-t / max(1e-9, REVERB_TAU_S * sample_rate)).astype("float32")
    ir /= float(np.sum(ir))  # unity-gain tail
    x = clip if clip.ndim == 2 else clip[:, None]
    wet = np.empty_like(x)
    for ch in range(x.shape[1]):
        wet[:, ch] = np.convolve(x[:, ch], ir, mode="full")[: x.shape[0]]
    wet = wet if clip.ndim == 2 else wet[:, 0]
    return (1.0 - a) * clip + a * wet


def equal_power_crossfade(
    a: "ndarray", b: "ndarray", overlap_samples: int
) -> "ndarray":
    """Concatenate ``a`` then ``b`` with an equal-power crossfade over ``overlap_samples`` (report 06 §3.6).

    The tail of ``a`` and head of ``b`` are ramped with ``cos``/``sin`` gains so
    perceived loudness stays flat across the seam (no ~3 dB dip). Used for seamless
    bed loops and ambience swaps.

    Args:
        a: The leading clip (mono or stereo).
        b: The trailing clip (same channel layout as ``a``).
        overlap_samples: Crossfade length in samples (clamped to both clip lengths).

    Returns:
        The crossfaded concatenation ``(len(a) + len(b) - overlap,)`` frames.
    """
    import numpy as np

    a = _match_layout(a, b)
    b = _match_layout(b, a)
    ov = int(max(0, min(overlap_samples, a.shape[0], b.shape[0])))
    if ov == 0:
        return np.concatenate([a, b], axis=0)
    t = np.linspace(0.0, 1.0, ov, dtype=a.dtype)
    fade_out = np.cos(t * (np.pi / 2.0))
    fade_in = np.sin(t * (np.pi / 2.0))
    shape = (ov, 1) if a.ndim == 2 else (ov,)
    seam = a[-ov:] * fade_out.reshape(shape) + b[:ov] * fade_in.reshape(shape)
    return np.concatenate([a[:-ov], seam, b[ov:]], axis=0)


def _match_layout(x: "ndarray", like: "ndarray") -> "ndarray":
    """Return ``x`` with the same channel-dimensionality as ``like`` (mono⇄stereo)."""
    if x.ndim == like.ndim:
        return x
    return _as_stereo(x) if like.ndim == 2 else (x.mean(axis=1) if x.ndim == 2 else x)


def declick(
    clip: "ndarray",
    sample_rate: int,
    *,
    fade_in: float = 0.008,
    fade_out: float = 0.012,
) -> "ndarray":
    """Apply short in/out fades so an edit point produces no click (report 06 §3.6).

    Thin wrapper over :func:`foley.audio.fade` (linear ramps), sized in seconds.
    """
    from ..audio import fade

    return fade(
        clip, sample_rate, fade_in_s=fade_in, fade_out_s=fade_out, kind="linear"
    )


def fit_duration(
    clip: "ndarray",
    sample_rate: int,
    *,
    duration: "float | None" = None,
    loop: bool = False,
    crossfade_s: float = 0.05,
) -> "ndarray":
    """Fit ``clip`` to ``duration`` seconds — seamless loop (beds) or trim/pass-through (report 06 §4).

    ``duration is None`` returns the clip unchanged (a one-shot plays once). When
    ``loop`` and the clip is shorter than ``duration``, it is tiled and equal-power
    crossfaded at the seam to fill the span; anything longer than ``duration`` is
    trimmed. A non-looping short clip is returned as-is (it plays once).

    Args:
        clip: Working array (mono or stereo).
        sample_rate: Sample rate in Hz.
        duration: Target duration in seconds (``None`` = full clip length).
        loop: Seamless-loop to fill ``duration`` when shorter.
        crossfade_s: Equal-power crossfade length at each loop seam.

    Returns:
        The duration-fitted clip.
    """
    import numpy as np

    if duration is None:
        return clip
    target = max(0, int(duration * sample_rate))
    n = clip.shape[0]
    if target == 0 or n == 0:
        return clip[:0]
    if n >= target:
        return clip[:target]
    if not loop:
        return clip  # a one-shot shorter than the span plays once
    ov = int(max(0, min(crossfade_s * sample_rate, n // 2)))
    out = clip
    while out.shape[0] < target:
        out = equal_power_crossfade(out, clip, ov)
    return out[:target]


def overlay(bus: "ndarray", clip: "ndarray", onset_samples: int) -> "ndarray":
    """Add ``clip`` into ``bus`` at ``onset_samples`` (report 06 §6.4 ``overlay``).

    Sums (never replaces) into a copy of the bus; a clip whose tail would exceed the
    bus length is truncated to fit (the mix length equals the narration length).

    Args:
        bus: The destination layer bus (stereo ``(frames, 2)``).
        clip: The (mono or stereo) clip to place.
        onset_samples: Start offset in samples (clamped at 0).

    Returns:
        A new bus with the clip summed in.
    """
    import numpy as np

    out = bus.copy()
    start = max(0, int(onset_samples))
    if start >= out.shape[0]:
        return out
    piece = (
        _as_stereo(clip)
        if out.ndim == 2
        else (clip if clip.ndim == 1 else clip.mean(axis=1))
    )
    end = min(out.shape[0], start + piece.shape[0])
    out[start:end] += piece[: end - start].astype(out.dtype, copy=False)
    return out
