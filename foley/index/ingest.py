"""The ingestion pipeline — turn any audio file into a searchable SoundRecord.

``probe -> QC -> supervised tag -> zero-shot tag -> caption -> resolve taxonomy
-> embed -> assemble -> store`` (report 03 Stages 0-5, report 08 §3 QC gate,
report 09 §5 decode-once). It is almost entirely **composition** over primitives
that already exist:

    * decode / archive: :func:`foley.audio.load` / :func:`~foley.audio.encode`
      (decode once, then fan the one array out to QC + taggers + embedder),
    * QC gate: :func:`foley.qc.run_qc` (a ``fail`` clip is quarantined, not added),
    * embed: the library's :class:`~foley.index.embedders.ClapEmbedder` (the vector
      is reused for zero-shot tagging — no second CLAP pass),
    * taxonomy: :func:`foley.index.taxonomy.resolve_catid` (tags+caption -> UCS),
    * store + index: :meth:`foley.index.library.SoundLibrary.add`
      (the by-value/by-reference license gate + vector upsert + BM25 index).

Enrichment stages degrade gracefully: a missing ``foley[tag]`` (PANNs) or
captioner is skipped with a note, never a crash — only the CLAP embedding is
required (retrieval-first). Everything heavy is lazy-imported; importing this
module costs only the stdlib.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

from ..audio import ARCHIVE_FORMAT, WORKING_SAMPLE_RATE, encode, load, to_working
from ..base import AcquisitionMethod, LicenseRecord, SerializableMixin, SoundRecord
from ..licensing import apply_license_flags
from ..qc import DEFAULT_QC_THRESHOLDS, QCStatus, QCThresholds, run_qc
from ..stores import content_key
from .taxonomy import resolve_catid

if TYPE_CHECKING:  # pragma: no cover - typing only
    from numpy import ndarray

    from ..audio import AudioSource

#: Audio file extensions the folder walker ingests.
AUDIO_EXTS: tuple[str, ...] = (
    ".wav", ".flac", ".aiff", ".aif", ".ogg", ".mp3", ".opus", ".m4a",
)

#: QC status ordering (worse -> better) for the admission gate.
_QC_RANK = {"fail": 0, "warn": 1, "pass": 2}


# ---------------------------------------------------------------------------
# result / report types
# ---------------------------------------------------------------------------


@dataclass
class IngestResult(SerializableMixin):
    """The outcome of ingesting one clip.

    ``status``: ``'pass'``/``'warn'`` (ingested), ``'quarantined'`` (QC-rejected,
    not added), ``'skipped_dup'`` (content already in the library), or
    ``'error'``. ``record`` is present only when the clip was ingested.
    """

    id: str
    status: str
    record: Optional[SoundRecord] = None
    qc: Optional[dict] = None
    notes: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class IngestReport(SerializableMixin):
    """The rolled-up outcome of a folder ingest (JSON-serializable)."""

    root: str
    results: "list[IngestResult]" = field(default_factory=list)

    def record(self, result: IngestResult) -> None:
        """Append one :class:`IngestResult`."""
        self.results.append(result)

    def error(self, path, exc: Exception) -> None:
        """Record a per-file error without aborting the run."""
        self.results.append(
            IngestResult(id=str(path), status="error", error=repr(exc))
        )

    def _by_status(self, *statuses: str) -> "list[IngestResult]":
        return [r for r in self.results if r.status in statuses]

    @property
    def ingested(self) -> "list[IngestResult]":
        """Results that were added to the library (``pass`` or ``warn``)."""
        return self._by_status("pass", "warn")

    @property
    def quarantined(self) -> "list[IngestResult]":
        """Results rejected by the QC gate."""
        return self._by_status("quarantined")

    @property
    def skipped(self) -> "list[IngestResult]":
        """Results skipped as content-addressed duplicates."""
        return self._by_status("skipped_dup")

    @property
    def errored(self) -> "list[IngestResult]":
        """Results that raised during ingest."""
        return self._by_status("error")

    def summary(self) -> dict:
        """A counts dict for a console/CLI summary."""
        return {
            "total": len(self.results),
            "ingested": len(self.ingested),
            "quarantined": len(self.quarantined),
            "skipped": len(self.skipped),
            "errored": len(self.errored),
        }


# ---------------------------------------------------------------------------
# stage helpers (probe / metadata / gate)
# ---------------------------------------------------------------------------


@dataclass
class _Probe:
    wav: "ndarray"
    native_sr: int
    channels: int
    format: Optional[str]
    bit_depth: Optional[int]


def _bit_depth_from_subtype(subtype: Optional[str]) -> Optional[int]:
    """Map a libsndfile subtype (``PCM_24``, ``FLOAT`` …) to a bit depth."""
    if not subtype:
        return None
    mapping = {"FLOAT": 32, "DOUBLE": 64, "ALAW": 8, "ULAW": 8}
    if subtype in mapping:
        return mapping[subtype]
    digits = "".join(ch for ch in subtype if ch.isdigit())
    return int(digits) if digits else None


def _sound_meta(src) -> "tuple[Optional[str], Optional[int]]":
    """Return ``(format, bit_depth)`` from the container header (best-effort)."""
    try:
        import soundfile as sf

        if isinstance(src, (str, os.PathLike)):
            info = sf.info(str(src))
        elif isinstance(src, (bytes, bytearray)):
            info = sf.info(io.BytesIO(bytes(src)))
        else:
            return None, None
        fmt = (info.format or "").lower() or None
        return fmt, _bit_depth_from_subtype(info.subtype)
    except Exception:
        return None, None


def _probe(src: "AudioSource") -> _Probe:
    """Decode ``src`` once and read its container metadata (report 03 Stage 0)."""
    wav, native_sr = load(src)
    channels = 1 if wav.ndim == 1 else int(wav.shape[1])
    fmt, bit_depth = _sound_meta(src)
    return _Probe(
        wav=wav,
        native_sr=int(native_sr),
        channels=channels,
        format=fmt,
        bit_depth=bit_depth,
    )


def _below(status: QCStatus, min_status: QCStatus) -> bool:
    """True if ``status`` is worse than the admission floor ``min_status``."""
    return _QC_RANK.get(status.value, 0) < _QC_RANK.get(min_status.value, 0)


def _src_name(src) -> Optional[str]:
    """The basename of a path-like source (for UCS-filename taxonomy parsing)."""
    if isinstance(src, (str, os.PathLike)):
        return Path(str(src)).name
    return None


def _reference_uri(src) -> Optional[str]:
    """A fetchable URI for a by-reference sound: the resolved local path if
    ``src`` is path-like (index-in-place), else ``None``."""
    if isinstance(src, (str, os.PathLike)):
        return str(Path(str(src)).expanduser().resolve())
    return None


def _audio_identity(wav) -> str:
    """Reproducible content id from the canonical decoded PCM.

    Hashing the float32 samples (not the FLAC container, whose Vorbis-comment
    vendor string embeds the libFLAC version) keeps the id/dedup key stable across
    machines and library upgrades — the local<->cloud idempotency promise.
    """
    import numpy as np

    canonical = np.ascontiguousarray(np.asarray(wav, dtype=np.float32))
    return content_key(canonical.tobytes())


def _default_user_license(source_url: Optional[str] = None) -> LicenseRecord:
    """The default license for a local ingest: user-owned => cacheable (by-value).

    Routes through the ``license_id -> flags`` SSOT (``'user-owned'``), so the
    storage mode is derived, not hand-set. ``rights_verified=True`` because the
    user is asserting ownership by ingesting their own files.
    """
    lic = LicenseRecord(
        source="user",
        source_url=source_url,
        license_id="user-owned",
        acquisition_method=AcquisitionMethod.user,
        rights_verified=True,
    )
    return apply_license_flags(lic)


# ---------------------------------------------------------------------------
# ingest_one — the single-file composer
# ---------------------------------------------------------------------------


def ingest_one(
    src: "AudioSource",
    *,
    library=None,
    license: Optional[LicenseRecord] = None,
    tagger=None,
    zeroshot_tagger=None,
    captioner=None,
    do_qc: bool = True,
    min_status: QCStatus = QCStatus.warn,
    do_supervised: bool = True,
    do_zeroshot: bool = True,
    do_caption: bool = True,
    thresholds: QCThresholds = DEFAULT_QC_THRESHOLDS,
    store: bool = True,
) -> IngestResult:
    """Ingest one clip into ``library`` and return an :class:`IngestResult`.

    Pipeline: probe + decode-once -> content-address dedup -> QC gate -> embed
    (once) -> supervised + zero-shot tags -> caption -> resolve UCS -> assemble
    ``SoundRecord`` -> :meth:`SoundLibrary.add`.

    Args:
        src: A path, ``bytes``, or file-like audio source.
        library: Target :class:`~foley.index.library.SoundLibrary` (default: the
            process-wide default library).
        license: Rights record (default: a user-owned, cacheable license).
        tagger: Supervised :class:`~foley.index.protocols.Tagger` (default: PANNs
            via :func:`~foley.index.taggers.default_tagger`).
        zeroshot_tagger: Zero-shot tagger (default: CLAP via
            :func:`~foley.index.taggers.default_zeroshot_tagger`).
        captioner: Optional :class:`~foley.index.protocols.Captioner` (default:
            none — the caption stage is off unless one is injected).
        do_qc: Run the Tier-0 QC gate.
        min_status: Admission floor — a QC status worse than this is quarantined
            (default ``warn``: only ``fail`` clips are rejected).
        do_supervised / do_zeroshot / do_caption: Toggle each enrichment stage.
        thresholds: QC thresholds.
        store: If ``False``, assemble the record but do not add it to the library
            (probe/QC/enrich only).

    Returns:
        An :class:`IngestResult`; its ``record`` is ``None`` when quarantined or a
        duplicate.
    """
    from .library import default_library

    lib = library if library is not None else default_library()

    # Stage 0 — probe + decode once + archive bytes + content-addressed id.
    # The id/dedup key hashes the CANONICAL decoded PCM (reproducible across
    # environments), NOT the FLAC archive whose vendor string varies by libFLAC
    # version. The archive bytes are the stored blob (keyed separately by
    # store_sound as content_sha256).
    probe = _probe(src)
    work = to_working(probe.wav, probe.native_sr)
    archive = encode(probe.wav, probe.native_sr)  # FLAC bytes
    sound_id = _audio_identity(probe.wav)
    if store and sound_id in lib:
        return IngestResult(id=sound_id, status="skipped_dup")

    # Stage 1 — QC gate (report 08 §3)
    qc_report = run_qc(work, WORKING_SAMPLE_RATE, thresholds=thresholds) if do_qc else None
    if qc_report is not None and _below(qc_report.status, min_status):
        return IngestResult(
            id=sound_id,
            status="quarantined",
            qc=qc_report.to_dict(),
            notes=list(qc_report.notes),
        )

    notes: list = []

    # Stage 5a — embed once (the retrieval vector; reused for zero-shot tagging)
    audio_vec = lib.embedder.embed_audio(work, WORKING_SAMPLE_RATE)

    # Stage 2 — supervised AudioSet tags (optional, graceful)
    audioset_labels: list = []
    if do_supervised:
        audioset_labels = _run_supervised(tagger, probe, notes)

    # Stage 3 — zero-shot tags (optional; reuses audio_vec, no second CLAP pass).
    # The default tagger is bound to the LIBRARY's embedder so the audio vector
    # and the label prompts live in the same joint space.
    zeroshot_tags: list = []
    if do_zeroshot:
        zeroshot_tags = _run_zeroshot(
            zeroshot_tagger, probe, audio_vec, notes, embedder=lib.embedder
        )

    # Stage 4 — caption (optional; only when a captioner is injected)
    caption: Optional[str] = None
    if do_caption and captioner is not None:
        try:
            caption = captioner.caption(probe.wav, probe.native_sr)
        except Exception as exc:  # graceful: a captioner failure never aborts
            notes.append(f"captioning skipped: {exc!r}")

    # taxonomy resolve (tags + caption + audioset + filename -> UCS CatID)
    resolution = resolve_catid(
        tags=zeroshot_tags,
        caption=caption,
        audioset_labels=audioset_labels,
        filename=_src_name(src),
    )

    ref_uri = _reference_uri(src)
    lic = license if license is not None else _default_user_license(ref_uri)
    # `format` is the DELIVERED format (what library.audio() serves): the FLAC
    # archive when cached by-value, else the untouched source container.
    delivered_format = ARCHIVE_FORMAT if lic.cache_bytes_ok else probe.format

    record = SoundRecord(
        id=sound_id,
        uri=ref_uri,  # a fetchable ref for by-reference; overwritten by the content
        license=lic,  #   key when store_sound caches by-value
        caption=caption,
        tags=sorted(set(audioset_labels) | set(zeroshot_tags)),
        audioset_labels=audioset_labels,
        ucs_category=resolution.catid,
        ucs_subcategory=resolution.subcategory,
        duration_s=(qc_report.duration_s if qc_report else len(work) / WORKING_SAMPLE_RATE),
        sample_rate=WORKING_SAMPLE_RATE,
        channels=probe.channels,
        format=delivered_format,
        archive_format=ARCHIVE_FORMAT,
        source_sample_rate=probe.native_sr,
        source_bit_depth=probe.bit_depth,
        loudness_lufs=(qc_report.loudness_lufs if qc_report else None),
        qc=(qc_report.to_dict() if qc_report else None),
    )

    if store:
        lib.add(record, data=archive, vector=audio_vec)

    status = qc_report.status.value if qc_report else "pass"
    return IngestResult(
        id=sound_id, status=status, record=record, qc=record.qc, notes=notes
    )


def _run_supervised(tagger, probe: _Probe, notes: list) -> list:
    from .taggers import default_tagger

    tg = tagger if tagger is not None else default_tagger()
    try:
        return [label for label, _ in tg.tag(probe.wav, probe.native_sr)]
    except ImportError:
        notes.append("supervised tagging skipped: foley[tag] (panns-inference) not installed")
    except Exception as exc:
        notes.append(f"supervised tagging failed: {exc!r}")
    return []


def _run_zeroshot(
    zeroshot_tagger, probe: _Probe, audio_vec, notes: list, *, embedder
) -> list:
    from .taggers import default_zeroshot_tagger

    zs = (
        zeroshot_tagger
        if zeroshot_tagger is not None
        else default_zeroshot_tagger(embedder)
    )
    try:
        # reuse the already-computed audio vector when the tagger supports it
        if hasattr(zs, "tag_vector"):
            return [label for label, _ in zs.tag_vector(audio_vec)]
        return [label for label, _ in zs.tag(probe.wav, probe.native_sr)]
    except Exception as exc:
        notes.append(f"zero-shot tagging skipped: {exc!r}")
        return []


# ---------------------------------------------------------------------------
# ingest_folder — the folder facade
# ---------------------------------------------------------------------------


def _iter_audio_files(
    path, *, recursive: bool, exts: tuple[str, ...]
) -> "Iterator[Path]":
    p = Path(path).expanduser()
    if p.is_file():
        yield p
        return
    walker = p.rglob("*") if recursive else p.glob("*")
    for fp in sorted(walker):
        if fp.is_file() and fp.suffix.lower() in exts:
            yield fp


def ingest_folder(
    path,
    *,
    library=None,
    recursive: bool = True,
    exts: tuple[str, ...] = AUDIO_EXTS,
    on_error: str = "collect",
    **ingest_one_kw,
) -> IngestReport:
    """Ingest every audio file under ``path`` and return an :class:`IngestReport`.

    Args:
        path: A folder (walked) or a single audio file.
        library: Target library (default: the process-wide default).
        recursive: Recurse into sub-folders.
        exts: Audio extensions to ingest.
        on_error: ``'collect'`` records per-file errors and continues;
            ``'raise'`` re-raises the first error.
        **ingest_one_kw: Forwarded to :func:`ingest_one` (license, taggers, QC
            flags, …).

    Returns:
        An :class:`IngestReport` (with ``.summary()`` counts and per-file results).
    """
    from .library import default_library

    lib = library if library is not None else default_library()
    report = IngestReport(root=str(path))
    for fp in _iter_audio_files(path, recursive=recursive, exts=exts):
        try:
            report.record(ingest_one(str(fp), library=lib, **ingest_one_kw))
        except Exception as exc:
            if on_error == "raise":
                raise
            report.error(fp, exc)
    return report
