"""dol-backed storage for foley: content-addressed bytes + a metadata store.

This module provides the two persistence surfaces the whole façade stands on and
the single gate that decides whether a sound is held *by value* or *by reference*:

    * a **content-addressed byte store** — ``Mapping[content_key -> bytes]``,
      keyed by the sha256 hex digest of the bytes (dedup + immutability),
    * a **metadata store** — ``Mapping[sound_id -> SoundRecord]`` (JSON on disk),
    * :func:`store_sound` — the by-value vs by-reference gate, driven by
      ``LicenseRecord.cache_bytes_ok``.

Both stores are plain ``MutableMapping`` objects built from ``dol``. Local disk is
the default (``dol.Files`` / ``dol.JsonFiles``); moving to the cloud is a **store
injection** — pass any ``dol`` Mapping (e.g. an S3-backed store) for ``sounds``
and an S3/Postgres Mapping for ``meta`` — never a change to business logic.
Content keys make local↔cloud copies idempotent and dedup-safe. Foundation does
NOT implement the S3 store (a later ``dol``-plugin concern); it only guarantees
the interface is a plain ``MutableMapping``.

Storage layout follows app-data-lifecycle: data lives under
``~/.local/share/foley`` (overridable via ``$FOLEY_DATA_DIR``), never inside the
package.

Invariants wired here (see the skill):
    #1 ``LicenseRecord`` is the SSOT for the storage mode — ``store_sound`` reads
       ``record.license.cache_bytes_ok`` to choose by-value vs by-reference.
    #2 ``cache_bytes_ok`` (TOS/operational) is DISTINCT from
       ``redistribute_standalone_ok`` (copyright): a Freesound CC0 item is
       legally redistributable yet ``cache_bytes_ok=False``, so it is stored
       by-reference (URI + provenance only, NO bytes cached).
"""

import hashlib
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Optional, Union

from dol import Files, JsonFiles, mk_dirs_if_missing, wrap_kvs

from .base import SoundRecord, StorageMode

#: Hash algorithm used for content addressing (matches ``SoundRecord.hash_algo``).
HASH_ALGO = "sha256"

#: Suffix given to on-disk metadata files (keys stay the bare ``sound_id``).
META_FILE_SUFFIX = ".json"

#: Default data root (app-data-lifecycle: data under ``~/.local/share``, never in
#: the package). Override with ``$FOLEY_DATA_DIR``.
FOLEY_DATA_DIR = Path(
    os.environ.get("FOLEY_DATA_DIR", Path.home() / ".local" / "share" / "foley")
)
DEFAULT_AUDIO_DIR = FOLEY_DATA_DIR / "audio"
DEFAULT_META_DIR = FOLEY_DATA_DIR / "meta"

#: A filesystem location (path or path-like string) for a local store root.
Rootdir = Union[str, "os.PathLike[str]"]


def content_key(data: bytes, *, algo: str = HASH_ALGO) -> str:
    """Return the content-address key for ``data`` — its hex digest.

    Using the hash as the key gives free deduplication (identical bytes map to
    the same key) and immutability (a key always names the exact same bytes).

    Args:
        data: The raw bytes to address (e.g. a FLAC archive blob).
        algo: A ``hashlib`` algorithm name (defaults to :data:`HASH_ALGO`).

    Returns:
        The lowercase hex digest of ``data`` under ``algo``.
    """
    return hashlib.new(algo, data).hexdigest()


def make_byte_store(rootdir: Rootdir = DEFAULT_AUDIO_DIR) -> MutableMapping[str, bytes]:
    """Build the content-addressable blob store: ``Mapping[content_key -> bytes]``.

    The local default is ``dol.Files`` (bytes values on disk). For cloud storage,
    build the equivalent store from any ``dol`` Mapping (e.g. an S3 store) and pass
    it directly to :func:`store_sound` instead of calling this factory — the
    ``store_sound`` gate treats ``sounds`` as an opaque ``MutableMapping``.

    Args:
        rootdir: Directory that holds the blobs (created if missing).

    Returns:
        A ``MutableMapping[str, bytes]`` keyed by :func:`content_key`.
    """
    return mk_dirs_if_missing(Files(str(rootdir)))


def make_meta_store(
    rootdir: Rootdir = DEFAULT_META_DIR,
) -> MutableMapping[str, SoundRecord]:
    """Build the metadata store: ``Mapping[sound_id -> SoundRecord]`` (JSON files).

    ``SoundRecord`` values are (de)serialized transparently via the
    ``SerializableMixin`` (``to_dict`` / ``from_dict``); each record is written as
    a ``{sound_id}.json`` file while the store's keys stay the bare ``sound_id``.

    Args:
        rootdir: Directory that holds the metadata JSON files (created if missing).

    Returns:
        A ``MutableMapping[str, SoundRecord]`` keyed by ``sound_id``.
    """
    json_store = mk_dirs_if_missing(JsonFiles(str(rootdir)))  # values are dict
    return wrap_kvs(
        json_store,
        obj_of_data=SoundRecord.from_dict,  # dict -> SoundRecord on read
        data_of_obj=lambda rec: rec.to_dict(),  # SoundRecord -> dict on write
        # dol applies id_of_key to reach the underlying store and key_of_id when
        # listing, so id_of_key adds the file suffix and key_of_id strips it —
        # exposing bare sound_id keys over {sound_id}.json files on disk.
        id_of_key=lambda k: f"{k}{META_FILE_SUFFIX}",  # sound_id -> filename
        key_of_id=lambda k: (
            k[: -len(META_FILE_SUFFIX)] if k.endswith(META_FILE_SUFFIX) else k
        ),  # filename -> sound_id
    )


def store_sound(
    record: SoundRecord,
    data: Optional[bytes] = None,
    *,
    sounds: MutableMapping[str, bytes],
    meta: MutableMapping[str, SoundRecord],
    cache_bytes_ok: Optional[bool] = None,
) -> SoundRecord:
    """Persist a sound, choosing by-value vs by-reference from ``cache_bytes_ok``.

    The choice is driven by the sound's own license (invariant #1): unless
    ``cache_bytes_ok`` is passed explicitly, it is read from
    ``record.license.cache_bytes_ok``. A sound whose bytes may NOT be cached
    (e.g. Freesound CC0, whose TOS forbids caching even though the file is legally
    redistributable — invariant #2) is stored **by reference**: no bytes are
    written, only its fetchable ``uri`` plus provenance.

    Args:
        record: The ``SoundRecord`` to persist; its nested ``license`` is the SSOT
            for the storage mode. Mutated in place with the resolved
            ``storage_mode`` / ``uri`` / ``content_sha256`` and written into
            ``meta``.
        data: The canonical archive bytes (FLAC). Required for by-value storage;
            for by-reference it is optional — if given, its hash is recorded in
            ``content_sha256`` for provenance but the bytes are NOT stored.
        sounds: The content-addressed byte store (see :func:`make_byte_store`).
        meta: The metadata store (see :func:`make_meta_store`).
        cache_bytes_ok: Optional override. ``None`` (the default) means "use
            ``record.license.cache_bytes_ok``".

    Returns:
        The same (mutated) ``record``, after it has been written into ``meta``.

    Raises:
        ValueError: If the sound resolves to by-reference storage but ``record.uri``
            is empty (a by-reference sound must name a fetchable source URL).

    Note:
        The blob is written BEFORE the record so a crash can never leave a
        metadata reference dangling against a missing blob.
    """
    allow = record.license.cache_bytes_ok if cache_bytes_ok is None else cache_bytes_ok
    if allow and data is not None:
        key = content_key(data)
        sounds[key] = data  # blob first
        record.content_sha256 = key
        record.uri = key
        record.storage_mode = StorageMode.by_value
    else:
        # Validate before any mutation so the raising path leaves record untouched.
        if not record.uri:
            raise ValueError(
                "by-reference sound requires record.uri (a fetchable source URL)"
            )
        if data is not None:
            record.content_sha256 = content_key(data)  # provenance only, no store
        record.storage_mode = StorageMode.by_reference
    meta[record.id] = record  # record last
    return record
