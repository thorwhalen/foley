"""Canonical data models for foley — the single source of truth (SSOT) types.

This module is stdlib-only and declarative: it defines the dataclasses, enums,
and affordance registries every other layer shares, plus generic dict/JSON
(de)serialization. It contains NO policy (see ``foley.licensing``) and NO I/O
(see ``foley.stores`` / ``foley.audio``).

Serialization contract:
    * ``record.to_dict()``  -> a plain dict (nested dataclasses recursed via
      ``dataclasses.asdict``; enum members preserved, and JSON-safe because every
      enum subclasses ``str``).
    * ``record.to_json()``  -> a JSON string.
    * ``Cls.from_dict(d)`` / ``Cls.from_json(s)`` -> reconstructs, coercing enum
      fields from their string values and nested ``LicenseRecord`` from its dict.
      Unknown keys are ignored (forward-compatible schema evolution); missing keys
      fall back to field defaults.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

SCHEMA_VERSION: int = 1


# ---------------------------------------------------------------------------
# Enums — closed, cross-layer, persisted vocabularies
# ---------------------------------------------------------------------------
# All enums subclass ``(str, Enum)`` so they (a) give enum ergonomics, (b) compare
# equal to their persisted string value, and (c) serialize to their ``.value``
# string under ``json.dumps`` with no custom encoder. ``from_dict`` coerces the
# string back via ``EnumClass(value)``.


class StorageMode(str, Enum):
    """How a sound's bytes are held (DERIVED from ``license.cache_bytes_ok``)."""

    by_value = "by_value"  # bytes cached in the byte store
    by_reference = "by_reference"  # URI + provenance only; no bytes stored


class AcquisitionMethod(str, Enum):
    """How a sound entered foley (retrieval channel or origin)."""

    api = "api"
    bulk = "bulk"
    scrape_pointer = "scrape_pointer"
    generated = "generated"
    user = "user"


class CandidateOrigin(str, Enum):
    """Whether a candidate was retrieved from the index or freshly generated."""

    retrieved = "retrieved"
    generated = "generated"


class Salience(str, Enum):
    """How prominent a sound event is within a passage."""

    high = "high"
    medium = "medium"
    low = "low"


class Layer(str, Enum):
    """Mix layer (shared by ``SoundEvent`` now and ``TimelineItem`` later)."""

    voice = "voice"
    sfx_fg = "sfx_fg"
    ambience = "ambience"
    stinger = "stinger"
    music = "music"


class VerifyLevel(str, Enum):
    """Which rung of the verification ladder produced a ``Verdict``."""

    clap = "clap"
    listen = "listen"
    judge = "judge"


# NOTE: ``QCStatus`` lives in ``foley.qc`` (tightly coupled to ``QCReport``), NOT
# here — ``base.py`` keeps ``SoundRecord.qc`` as a plain ``Optional[dict]`` so it
# never imports ``qc.py`` (avoids a base->qc dependency and keeps ``import
# foley.base`` free of numpy).


# ---------------------------------------------------------------------------
# Affordances + the two registries (mirrors ``arioso.base.AFFORDANCES``)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Affordance:
    """Descriptor for a unified parameter affordance (arioso analog).

    Attributes:
        name: Canonical parameter name used at the façade level.
        type: Expected Python type.
        description: Human-readable description.
        default: Default value (``None`` = no default / required).
        stage: ``'query'`` (search/find/filter) or ``'generate'``.
    """

    name: str
    type: type
    description: str
    default: Any = None
    stage: str = "query"


#: Unified query-stage parameters (search / find / filter surface).
QUERY_AFFORDANCES: dict[str, Affordance] = {
    "text": Affordance("text", str, "Natural-language query"),
    "semantic_text": Affordance(
        "semantic_text", str, "Query for CLAP semantic space", stage="query"
    ),
    "k": Affordance("k", int, "Number of results", 10),
    "filters": Affordance("filters", dict, "Metadata predicates (SQL-style)"),
    "ucs_category": Affordance("ucs_category", str, "UCS CatID facet"),
    "audioset_label": Affordance(
        "audioset_label", str, "AudioSet ontology facet (rolls up children)"
    ),
    "duration_range": Affordance("duration_range", tuple, "(min_s, max_s)"),
    "min_snr": Affordance("min_snr", float, "QC filter: min SNR dB"),
    "commercial_ok": Affordance("commercial_ok", bool, "License filter shorthand"),
    "license": Affordance("license", str, "Explicit license id constraint"),
    "sort": Affordance("sort", str, "score|duration|created|downloads", "score"),
    "rerank": Affordance("rerank", bool, "Apply second-stage rerank", False),
}

#: Unified generation-stage parameters (generate backends map onto these).
GENERATION_AFFORDANCES: dict[str, Affordance] = {
    "prompt": Affordance("prompt", str, "Sound description", stage="generate"),
    "duration": Affordance(
        "duration", float, "Seconds; None => backend default", stage="generate"
    ),
    "prompt_influence": Affordance(
        "prompt_influence", float, "0..1 unified guidance", 0.3, "generate"
    ),
    "negative_prompt": Affordance(
        "negative_prompt", str, "Content to exclude", stage="generate"
    ),
    "steps": Affordance("steps", int, "Diffusion/flow steps", stage="generate"),
    "seed": Affordance(
        "seed", int, "Reproducibility (capture in provenance)", stage="generate"
    ),
    "loop": Affordance("loop", bool, "Seamless-loopable clip", False, "generate"),
    "output_format": Affordance(
        "output_format", str, "wav|opus|mp3", "wav", "generate"
    ),
}


# ---------------------------------------------------------------------------
# Serialization mixin (generic, stdlib-only)
# ---------------------------------------------------------------------------


def _decode(tp: Any, value: Any) -> Any:
    """Coerce a JSON-decoded value into the field type ``tp``.

    Handles ``Optional``/``Union``, list/set/tuple containers (recursing into
    the element type), ``str``-enums (via ``EnumClass(value)``), and nested
    dataclasses (via their ``from_dict`` when present, else ``**value``).
    Anything else (``dict``, primitives) is returned unchanged.

    Args:
        tp: The declared field type (a resolved type hint).
        value: The raw JSON-decoded value.

    Returns:
        The value coerced to ``tp`` (or unchanged when no coercion applies).
    """
    if value is None:
        return None
    origin = typing.get_origin(tp)
    if origin is Union:  # Optional[X] / X | None
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        return _decode(args[0], value) if len(args) == 1 else value
    if origin in (list, set, tuple):
        args = typing.get_args(tp)
        item_tp = args[0] if args else object
        seq = [_decode(item_tp, v) for v in value]
        return tuple(seq) if origin is tuple else (set(seq) if origin is set else seq)
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)
    if dataclasses.is_dataclass(tp):
        return tp.from_dict(value) if hasattr(tp, "from_dict") else tp(**value)
    return value


class SerializableMixin:
    """Adds ``to_dict``/``to_json``/``from_dict``/``from_json`` to a dataclass.

    Stdlib-only, DRY, no-magic (de)serialization. Every SSOT dataclass below
    inherits this instead of hand-rolling per-class encoders/decoders.
    """

    def to_dict(self) -> dict:
        """Return the recursive plain-dict form.

        Enum members are preserved (and remain JSON-safe because every enum
        subclasses ``str``); nested dataclasses are recursed via
        ``dataclasses.asdict``.
        """
        return dataclasses.asdict(self)

    def to_json(self, *, indent: Optional[int] = None) -> str:
        """Return a JSON string (str-enums serialize to their ``.value``).

        Args:
            indent: Optional pretty-print indent passed to ``json.dumps``.
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "SerializableMixin":
        """Reconstruct an instance from a plain dict.

        Enum fields and nested dataclasses are coerced via :func:`_decode`.
        Unknown keys are ignored (forward-compatible); missing keys fall back
        to field defaults.

        Args:
            d: A plain dict (typically from ``to_dict()`` or ``json.loads``).
        """
        hints = typing.get_type_hints(cls)
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {
            k: _decode(hints.get(k, object), v) for k, v in d.items() if k in known
        }
        return cls(**kwargs)

    @classmethod
    def from_json(cls, s: str) -> "SerializableMixin":
        """Reconstruct an instance from a JSON string.

        Args:
            s: A JSON string (typically from ``to_json()``).
        """
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# LicenseRecord — rights + provenance SSOT
# ---------------------------------------------------------------------------


@dataclass
class LicenseRecord(SerializableMixin):
    """Per-sound rights + provenance. SSOT for BOTH ``keep()`` and storage mode.

    The eight derived flags default fail-closed here (the bare-record baseline);
    populate them from the ``license_id`` via
    ``foley.licensing.apply_license_flags`` (source overrides win). Never
    hand-set the derived flags — always route through the policy layer.
    """

    # identity / origin
    source: str  # 'freesound' | 'user' | 'stable_audio' | ...
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    acquisition_method: AcquisitionMethod = AcquisitionMethod.user
    retrieved_at: Optional[str] = None  # ISO-8601
    adapter_version: Optional[str] = None
    content_sha256: Optional[str] = None

    # rights (normalized)
    license_id: str = "unknown"  # SPDX id or RemArc / Sonniss-GDC / ElevenLabs-SFX / Stability-Community / Proprietary-<vendor>
    license_name: Optional[str] = None
    license_version: Optional[str] = None
    license_url: Optional[str] = None
    rights_holder: Optional[str] = None
    creator_name: Optional[str] = None
    creator_url: Optional[str] = None

    # derived flags (SSOT for filtering; fail-closed baseline)
    commercial_ok: bool = False
    embed_in_derivative_ok: bool = True  # normal case
    redistribute_standalone_ok: bool = False  # COPYRIGHT: raw-file re-exposure
    cache_bytes_ok: bool = False  # OPERATIONAL: may foley persist bytes? (Freesound TOS => False even for CC0)
    modification_ok: bool = False
    ai_training_ok: bool = False
    revenue_cap_usd: Optional[int] = None  # e.g. 1_000_000 for Stability-Community

    # attribution
    requires_attribution: bool = False
    attribution_text: Optional[str] = None
    notice_text_required: Optional[str] = None

    # provenance / transformation
    transformations: list = field(default_factory=list)  # ordered ops; non-empty => "(modified)"

    # generation (present iff AI-generated)
    is_ai_generated: bool = False
    generator_model: Optional[str] = None
    generator_version: Optional[str] = None
    generation_prompt: Optional[str] = None
    generation_seed: Optional[int] = None
    generation_params: dict = field(default_factory=dict)
    watermark: Optional[dict] = None  # {"present": True, "method": "audioseal", "version": ...}
    c2pa_manifest_ref: Optional[str] = None

    # safety / disclosure
    contains_recognizable_voice: bool = False
    potential_trademark: bool = False
    disclosure_recommended: bool = False  # EU AI Act Art.50 hint
    rights_verified: bool = False  # False => unknown => fail-closed
    verified_at: Optional[str] = None
    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# SoundRecord — canonical per-sound record
# ---------------------------------------------------------------------------


@dataclass
class SoundRecord(SerializableMixin):
    """Canonical SSOT per sound.

    Audio bytes + CLAP vector live in SEPARATE stores keyed by the same id; this
    record holds a content-hash ``uri``, never raw bytes.
    """

    # identity
    id: str
    content_sha256: Optional[str] = None  # content-address key into `sounds`
    hash_algo: str = "sha256"

    # storage (report 09)
    uri: Optional[str] = None  # content key | local path | s3://… | https://…
    storage_mode: StorageMode = StorageMode.by_reference  # DERIVED from license.cache_bytes_ok
    archive_format: Optional[str] = None  # 'flac'
    source_sample_rate: Optional[int] = None  # preserved native rate (e.g. 96/192 kHz)
    source_bit_depth: Optional[int] = None

    # rights + provenance
    license: LicenseRecord = field(default_factory=lambda: LicenseRecord(source="user"))

    # descriptive text (feeds BM25 + display)
    caption: Optional[str] = None
    tags: list = field(default_factory=list)

    # controlled taxonomy
    ucs_category: Optional[str] = None
    ucs_subcategory: Optional[str] = None
    audioset_labels: list = field(default_factory=list)

    # audio technical facts
    duration_s: Optional[float] = None
    sample_rate: Optional[int] = None  # working/delivered rate
    channels: Optional[int] = None
    loudness_lufs: Optional[float] = None
    format: Optional[str] = None  # 'wav'|'flac'|'opus'|'mp3'

    # quality control (report 08; QCReport.to_dict())
    qc: Optional[dict] = None

    # retrieval index refs (NOT inlined in list views)
    embedding_model: Optional[str] = None
    embedding_dim: Optional[int] = None
    embedding_ref: Optional[str] = None

    # cross-work continuity
    named_cue: Optional[str] = None

    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# SELECT-stage models — SoundEvent, Verdict, Candidate
# ---------------------------------------------------------------------------


@dataclass
class SoundEvent(SerializableMixin):
    """One salient, physically-audible event decomposed from a passage."""

    query: str
    layer: Layer = Layer.sfx_fg
    diegetic: bool = True
    salience: Salience = Salience.medium
    onset: Optional[str] = None  # symbolic anchor, resolved by WEAVE
    loop: bool = False
    ucs_catid: Optional[str] = None
    audioset: list = field(default_factory=list)
    era_place: Optional[str] = None  # anachronism guard


@dataclass
class Verdict(SerializableMixin):
    """The result of one verification rung for a candidate."""

    match: bool
    confidence: float  # 0..1
    reason: str = ""
    level: VerifyLevel = VerifyLevel.clap


@dataclass
class Candidate(SerializableMixin):
    """A ranked, license-checked, (optionally) verified sound for one SoundEvent.

    Retrieval and generation return the SAME shape; only ``origin`` differs.
    Nested ``sound`` / ``event`` / ``verdict`` dataclasses are decoded generically
    by :func:`_decode` — no per-field code needed.
    """

    sound: SoundRecord
    origin: CandidateOrigin = CandidateOrigin.retrieved
    event: Optional[SoundEvent] = None
    clap_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    verdict: Optional[Verdict] = None
    license_ok: Optional[bool] = None  # result of keep()
    preview_uri: Optional[str] = None


# ---------------------------------------------------------------------------
# IntendedUse — the caller's rights intent
# ---------------------------------------------------------------------------


@dataclass
class IntendedUse(SerializableMixin):
    """What the caller intends to do with a sound; consumed by ``keep()``."""

    commercial: bool = True
    publish: bool = True
    redistribute_standalone: bool = False
    will_train: bool = False
    can_attribute: bool = True
    revenue_usd: int = 0
    allow_voice_or_trademark: bool = False
