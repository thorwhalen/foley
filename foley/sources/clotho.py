"""Clotho-eval — a captioned Ring-0 corpus that doubles as a retrieval fixture.

Clotho (report 11 §1.2 / §2.1) is an audio-captioning benchmark built from a
Freesound subset; its *evaluation* split is a Ring-0 seed corpus and a retrieval
fixture. Audio must be downloaded locally; this adapter only enumerates, licenses
and (optionally) captions it.

Rights are **per clip and per asset** (#68, report 14 §3.11):

* **Audio** keeps each file's own Freesound licence, read from the ``license``
  column of ``clotho_metadata_*.csv`` with its CC version (CC0, CC BY 3.0,
  CC BY-NC 3.0, Sampling+ in the eval split). A clip absent from the metadata, or
  under an unrecognised licence, fails closed (``unknown``, unverified). So no
  non-commercial clip passes :func:`foley.keep` under commercial intent.
* **Captions** are licensed by Tampere University for **non-commercial use only**
  (not CC-BY 4.0, as report 11 said). They are therefore **not** put into the
  library's keyword index by default: an index is not intent-aware at query time,
  and foley's default intent is commercial. A non-commercial / eval-only library can
  opt in: ``register_corpus(dataclasses.replace(CLOTHO, include_captions=True))``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..base import LicenseRecord
from .base import (
    ClipSpec,
    UniformCorpus,
    license_from_clip_meta,
    per_clip_license_meta,
    register_corpus,
)

#: Filename column + the first caption column in a Clotho captions CSV.
_FILE_COL = "file_name"
_CAPTION_COLS = ("caption_1", "caption_2", "caption_3", "caption_4", "caption_5")

#: The per-file licence / provenance columns of ``clotho_metadata_*.csv``.
_LICENSE_COL = "license"
_LINK_COL = "sound_link"
_CREATOR_COL = "manufacturer"

#: What the caption text is licensed under (not a LICENSE_FLAGS row: it is never a
#: sound's licence, only the reason captions stay out of a commercial index).
CAPTION_LICENSE = "Tampere-University-Clotho-captions (non-commercial only)"


def _read_csv_rows(path: Path) -> "Iterator[dict]":
    """Rows of a Clotho CSV, tolerant of a BOM and of a non-UTF-8 export."""
    # utf-8-sig strips a BOM (else the first header cell reads as "\ufefffile_name"
    # and every lookup misses); errors="replace" keeps a non-UTF-8 export
    # (Excel/cp1252) from raising UnicodeDecodeError and aborting the ingest.
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        yield from csv.DictReader(fh)


def _load_metadata(root: Path) -> "dict[str, dict]":
    """Map ``file_name -> metadata row`` from any ``*metadata*.csv`` under ``root``.

    A missing or malformed CSV yields no rows, so the clips it would have described
    fail closed (``unknown`` licence) rather than inheriting a guessed one.
    """
    rows: "dict[str, dict]" = {}
    for csv_path in sorted(root.rglob("*metadata*.csv")):
        try:
            for row in _read_csv_rows(csv_path):
                name = row.get(_FILE_COL)
                if name:
                    rows.setdefault(name, row)
        except (OSError, csv.Error):
            continue
    return rows


def _load_captions(root: Path) -> "dict[str, str]":
    """Map ``file_name -> first caption`` from any ``*caption*.csv`` under ``root``.

    Best-effort: captions are an enrichment, not a rights input, so a missing or
    malformed CSV degrades to "no captions" rather than raising.
    """
    captions: "dict[str, str]" = {}
    for csv_path in sorted(root.rglob("*caption*.csv")):
        try:
            for row in _read_csv_rows(csv_path):
                name = row.get(_FILE_COL)
                if not name:
                    continue
                caption = next((row[c] for c in _CAPTION_COLS if row.get(c)), None)
                if caption:
                    captions.setdefault(name, caption)
        except (OSError, csv.Error):
            continue
    return captions


@dataclass
class ClothoEvalCorpus(UniformCorpus):
    """Ring-0 Clotho-eval adapter: per-clip Freesound licences; captions opt-in (NC)."""

    #: Put the (non-commercial) human captions into the keyword index. Off by default.
    include_captions: bool = False

    def iter_clips(self, root: str) -> Iterator[ClipSpec]:
        """Yield clips carrying their per-file licence (and caption, when opted in)."""
        root_path = Path(root).expanduser()
        metadata = _load_metadata(root_path)
        captions = _load_captions(root_path) if self.include_captions else {}
        for spec in super().iter_clips(root):
            name = Path(spec.path).name
            row = metadata.get(name, {})
            spec.meta.update(
                per_clip_license_meta(
                    row.get(_LICENSE_COL) or None,
                    creator_name=row.get(_CREATOR_COL) or None,
                    source_url=row.get(_LINK_COL) or None,
                )
            )
            caption = captions.get(name)
            if caption:
                spec.meta["caption"] = caption
                spec.meta["caption_license"] = CAPTION_LICENSE
            yield spec

    def resolve_license(self, spec: ClipSpec) -> LicenseRecord:
        """The clip's own licence from its metadata row (``unknown`` when absent)."""
        return license_from_clip_meta(self.source, spec)


#: The Clotho-eval Ring-0 adapter (audio licensed per clip; captions excluded).
CLOTHO = register_corpus(
    ClothoEvalCorpus(
        name="clotho",
        ring=0,
        default_license_id="CC-BY-4.0",  # the compilation; each clip overrides it
        source="clotho",
        rights_verified=True,
    )
)
