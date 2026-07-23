"""UCS table loading + the UCS-filename CatID parse (report 04 §5.2, §6.4).

A UCS filename is underscore-delimited with the **CatID first**::

    CatID_FXName_CreatorID_SourceID[_UserCategory_UserData].ext

Only token 0 (the CatID) carries the controlled taxonomy; it is looked up in the
table (never string-split, since the category prefix is variable-length). The
loader merges the in-code seed with an optional full-table JSON drop under
``taxonomy/data/ucs_full.json`` (JSON wins on CatID collision) — open/closed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .model import UcsRow, UcsTable
from .seed import SEED_UCS_TABLE

_DATA_DIR = Path(__file__).parent / "data"
_UCS_FULL_FILE = "ucs_full.json"


def _row_from_dict(d: dict) -> UcsRow:
    return UcsRow(
        catid=d["catid"],
        category=d["category"],
        subcategory=d["subcategory"],
        synonyms=tuple(s.lower() for s in d.get("synonyms", ())),
        confident=bool(d.get("confident", False)),
    )


def load_ucs_table(*, data_dir=None, include_seed: bool = True) -> UcsTable:
    """Build the UCS lookup: the seed rows, overridden/extended by a JSON drop.

    Args:
        data_dir: Directory to look for ``ucs_full.json`` in (defaults to the
            package's ``taxonomy/data/``). When present, its rows override the
            seed on CatID collision and add the rest of the ~750-row master.
        include_seed: Start from the in-code seed table (default ``True``).

    Returns:
        A ready :class:`~foley.index.taxonomy.model.UcsTable`.
    """
    rows: dict[str, UcsRow] = {}
    if include_seed:
        for d in SEED_UCS_TABLE:
            rows[d["catid"]] = _row_from_dict(d)
    search_dir = Path(data_dir) if data_dir else _DATA_DIR
    full = search_dir / _UCS_FULL_FILE
    if full.exists():
        for d in json.loads(full.read_text(encoding="utf-8")):
            rows[d["catid"]] = _row_from_dict(d)
    order = list(rows)
    ci_index = {c.lower(): c for c in rows}
    return UcsTable(by_catid=dict(rows), order=order, _ci_index=ci_index)


@lru_cache(maxsize=1)
def default_ucs_table() -> UcsTable:
    """The process-wide default UCS table (seed + any JSON drop), built once."""
    return load_ucs_table()


def parse_catid_token(filename) -> Optional[str]:
    """Return token 0 (the CatID candidate) of a UCS-style filename, else ``None``.

    Strips directory and extension; requires at least one ``_`` (the field
    delimiter). Does not validate the token against the table.
    """
    stem = Path(str(filename)).stem
    stem = stem.strip()
    if "_" not in stem:
        return None
    return stem.split("_", 1)[0].strip() or None


def parse_ucs_filename(
    filename, *, table: Optional[UcsTable] = None
) -> "tuple[Optional[str], Optional[str]]":
    """Parse a UCS-conformant filename to ``(ucs_category, ucs_subcategory)``.

    Fail-quiet: returns ``(None, None)`` when the name is not UCS-conformant or
    its CatID token is unknown (so a wrong subcategory is never emitted).

    Args:
        filename: A path or filename (only the basename's token 0 is used).
        table: The UCS table to resolve against (defaults to
            :func:`default_ucs_table`).
    """
    table = table or default_ucs_table()
    token = parse_catid_token(filename)
    if not token:
        return (None, None)
    row = table.get(token)
    if row is None:
        return (None, None)
    return (row.category, row.subcategory)
