"""AudioSet-label -> UCS-CatID overlap map (report 04 §5.3, [11 §3.1]).

The machine-label layer (PANNs/PaSST emit AudioSet labels on ingest) is bridged
to the human-facing UCS browse tree by a small overlap map. This is the
conceptual seed of the EnvSound-UCS "Rosetta stone"; the full table drops in as
``taxonomy/data/audioset_ucs.json`` and merges over the seed. Every target CatID
is validated against the UCS table at load time (fail-fast on a broken map).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .model import AudioSetUcsMap, UcsTable
from .seed import SEED_AUDIOSET_UCS_MAP
from .ucs import default_ucs_table

_DATA_DIR = Path(__file__).parent / "data"
_AUDIOSET_FILE = "audioset_ucs.json"


def load_audioset_ucs_map(
    *, data_dir=None, table: Optional[UcsTable] = None, include_seed: bool = True
) -> AudioSetUcsMap:
    """Build the AudioSet(name|MID) -> UCS-CatID map.

    Args:
        data_dir: Directory to look for ``audioset_ucs.json`` in (defaults to the
            package's ``taxonomy/data/``); merged over the seed when present.
        table: The UCS table every target CatID must exist in (defaults to
            :func:`~foley.index.taxonomy.ucs.default_ucs_table`).
        include_seed: Start from the in-code seed map (default ``True``).

    Returns:
        A ready :class:`~foley.index.taxonomy.model.AudioSetUcsMap`.

    Raises:
        ValueError: If any entry targets a CatID absent from ``table``.
    """
    table = table or default_ucs_table()
    by_name: dict[str, str] = {}
    by_mid: dict[str, str] = {}

    def _add(entries):
        for d in entries:
            catid = d["catid"]
            if catid not in table:
                raise ValueError(
                    f"AudioSet->UCS map targets unknown CatID {catid!r} "
                    f"(not in the UCS table): fix the map or add the CatID."
                )
            by_name[d["name"].lower()] = catid
            if d.get("mid"):
                by_mid[d["mid"]] = catid

    if include_seed:
        _add(SEED_AUDIOSET_UCS_MAP)
    search_dir = Path(data_dir) if data_dir else _DATA_DIR
    drop = search_dir / _AUDIOSET_FILE
    if drop.exists():
        _add(json.loads(drop.read_text(encoding="utf-8")))
    return AudioSetUcsMap(by_name=by_name, by_mid=by_mid)


@lru_cache(maxsize=1)
def default_audioset_ucs_map() -> AudioSetUcsMap:
    """The process-wide default AudioSet->UCS map (seed + any JSON drop)."""
    return load_audioset_ucs_map()
