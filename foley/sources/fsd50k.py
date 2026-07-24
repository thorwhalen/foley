"""FSD50K — the labeled, commercial-safe backbone corpus (Ring 1).

FSD50K (report 11 §1.1, Zenodo 4060432) is ~51 k Freesound clips with AudioSet
labels. Its *compilation* is CC-BY-4.0, but **each clip carries its own Freesound
license** (CC0 / CC-BY / CC-BY-NC / Sampling+), so licensing is resolved
**per-clip** from the shipped metadata, not stamped uniformly. The bootstrap
Ring-1 policy then drops the non-commercial slice (CC-BY-NC / Sampling+) via the
fail-closed commercial filter, keeping the ~85 % CC0/CC-BY backbone.

Per-clip metadata lives in the FSD50K ``*_clips_info_FSD50K.json`` files
(``{fname: {title, description, tags, license, uploader, ...}}``) where ``license``
is a Creative-Commons URL. This adapter reads those, maps the URL to a foley
``license_id``, and fails closed (``license_id='unknown'``, ``rights_verified=
False``) for any clip whose license is missing or unrecognized — such clips are
then dropped by :func:`foley.keep`. The bytes are a Zenodo bulk download, so
they are cacheable (``cache_bytes_ok=True``, stored by-value) — do NOT copy #5's
Freesound-*API* ``cache_bytes_ok=False`` override.

.. note::
   The exact metadata filename/columns are per the published FSD50K layout; if a
   future release moves them, this adapter degrades to fail-closed rather than
   guessing. Verify against the real download when wiring the fetch (#4 ships the
   local-dir ingestion; auto-download is a fast-follow).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional

from ..base import LicenseRecord
from ..licensing import license_id_from_cc_url
from .base import ClipSpec, bulk_license, register_corpus

#: Glob for the FSD50K per-clip info JSONs (dev + eval).
_CLIPS_INFO_GLOB = "*clips_info*.json"

#: The CC-URL → foley ``license_id`` mapper now lives in :mod:`foley.licensing`
#: (it is license policy, shared with the Freesound API adapter). This alias keeps
#: the historical FSD50K import path (and its tests) working unchanged.
_license_id_from_url = license_id_from_cc_url


def _load_clips_info(root: Path) -> "dict[str, dict]":
    """Load ``{fname: info}`` from every ``*clips_info*.json`` under ``root``.

    Best-effort across the dev/eval split files; a malformed file is skipped so a
    partial metadata drop still licenses the clips it does describe (the rest fail
    closed).
    """
    info: "dict[str, dict]" = {}
    for path in sorted(root.rglob(_CLIPS_INFO_GLOB)):
        try:
            # utf-8-sig tolerates a BOM (else json.load raises and the whole
            # metadata file is skipped, silently failing its clips closed).
            with open(path, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for fname, clip in data.items():
                    if isinstance(clip, dict):
                        info.setdefault(str(fname), clip)
        except (OSError, ValueError):
            continue
    return info


class Fsd50kCorpus:
    """Ring-1 FSD50K adapter with per-clip Freesound license resolution."""

    name = "fsd50k"
    ring = 1
    default_license_id = "CC-BY-4.0"  # the compilation license; per-clip overrides
    source = "fsd50k"

    def corpus_dir(self, data_dir: str) -> str:
        """``data_dir/fsd50k`` — the conventional on-disk root."""
        return str(Path(data_dir) / self.name)

    def iter_clips(self, root: str) -> Iterator[ClipSpec]:
        """Yield a clip per audio file, carrying its per-clip license metadata.

        Each clip's ``meta`` gets ``{license_id, rights_verified, creator_name,
        source_url}`` resolved from the FSD50K clips-info JSON (fail-closed when a
        clip is absent from the metadata).
        """
        from ..index.ingest import iter_audio_files

        info = _load_clips_info(Path(root))
        for fp in iter_audio_files(root):
            fname = fp.stem
            clip = info.get(fname, {})
            license_id, verified = _license_id_from_url(clip.get("license"))
            yield ClipSpec(
                path=str(fp),
                source_id=fname,
                meta={
                    "license_id": license_id,
                    "rights_verified": verified,
                    "creator_name": clip.get("uploader"),
                    # FSD50K fnames ARE Freesound sound ids -> a real attribution URL
                    "source_url": f"https://freesound.org/s/{fname}/",
                },
            )

    def resolve_license(self, spec: ClipSpec) -> LicenseRecord:
        """Build the per-clip rights record from the metadata in ``spec.meta``."""
        meta = spec.meta
        return bulk_license(
            source=self.source,
            license_id=meta.get("license_id", "unknown"),
            rights_verified=bool(meta.get("rights_verified", False)),
            source_id=spec.source_id,
            source_url=meta.get("source_url"),
            creator_name=meta.get("creator_name"),
        )


#: The FSD50K Ring-1 adapter.
FSD50K = register_corpus(Fsd50kCorpus())
