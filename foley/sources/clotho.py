"""Clotho-eval — a captioned Ring-0 corpus that doubles as a retrieval fixture.

Clotho (report 11 §1.2 / §2.1) is an audio-captioning benchmark built from a
redistributable Freesound subset; its *evaluation* split is a clean Ring-0 seed
corpus **and** the retrieval regression fixture #10a scores against. Each clip
ships five human captions — real descriptive text — which this adapter injects so
they flow through the normal ingest pipeline into the BM25 keyword index (no
special-casing).

Licensing is uniform ``CC-BY-4.0`` (a conservative, attributable stamp over the
redistributable-subset guarantee — if a clip is actually CC0 we merely
over-attribute, never under-attribute). Audio must be downloaded locally; this
adapter only enumerates + captions + licenses it.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from .base import ClipSpec, UniformCorpus, register_corpus

#: Filename column + the first caption column in a Clotho captions CSV.
_FILE_COL = "file_name"
_CAPTION_COLS = ("caption_1", "caption_2", "caption_3", "caption_4", "caption_5")


def _load_captions(root: Path) -> "dict[str, str]":
    """Map ``file_name -> first caption`` from any ``*caption*.csv`` under ``root``.

    Best-effort: captions are an enrichment, not a rights input, so a missing or
    malformed CSV degrades to "no captions" rather than raising.
    """
    captions: "dict[str, str]" = {}
    for csv_path in sorted(root.rglob("*caption*.csv")):
        try:
            # utf-8-sig strips a BOM (else the first header cell reads as
            # "﻿file_name" and every lookup misses); errors="replace" keeps a
            # non-UTF-8 export (Excel/cp1252) from raising UnicodeDecodeError —
            # which is a ValueError, NOT caught below — and aborting the ingest.
            with open(
                csv_path, newline="", encoding="utf-8-sig", errors="replace"
            ) as fh:
                for row in csv.DictReader(fh):
                    name = row.get(_FILE_COL)
                    if not name:
                        continue
                    caption = next((row[c] for c in _CAPTION_COLS if row.get(c)), None)
                    if caption:
                        captions.setdefault(name, caption)
        except (OSError, csv.Error):
            continue
    return captions


class ClothoEvalCorpus(UniformCorpus):
    """Ring-0 Clotho-eval adapter: uniform CC-BY + injected human captions."""

    def iter_clips(self, root: str) -> Iterator[ClipSpec]:
        """Yield clips with their human caption attached in ``meta['caption']``."""
        captions = _load_captions(Path(root))
        for spec in super().iter_clips(root):
            caption = captions.get(Path(spec.path).name)
            if caption:
                spec.meta["caption"] = caption
            yield spec


#: The Clotho-eval Ring-0 adapter.
CLOTHO = register_corpus(
    ClothoEvalCorpus(
        name="clotho",
        ring=0,
        default_license_id="CC-BY-4.0",
        source="clotho",
        rights_verified=True,
    )
)
