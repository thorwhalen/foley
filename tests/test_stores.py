"""Tests for foley's dol-backed storage layer (``foley.stores``).

These tests need only ``dol`` (a core dependency, always installed) — no audio
libraries. They use ``tmp_path`` for isolated on-disk stores (no cloud). Covers:

    * content addressing: determinism, dedup (identical bytes -> identical key),
      and collision-freedom (different bytes -> different key),
    * the byte store and metadata store behaving as ``MutableMapping``, with the
      metadata store round-tripping a ``SoundRecord`` and exposing bare
      ``sound_id`` keys over ``{sound_id}.json`` files,
    * the CRUCIAL by-value vs by-reference gate in ``store_sound``:
        - ``cache_bytes_ok=True``  -> bytes cached, uri = content key,
        - ``cache_bytes_ok=False`` -> NO bytes stored, uri preserved,
      driven either by an explicit override or (invariant #1) by the record's own
      ``license.cache_bytes_ok``.
"""

import hashlib

import pytest

from foley.base import LicenseRecord, SoundRecord, StorageMode
from foley.stores import (
    HASH_ALGO,
    _meta_filename,
    content_key,
    make_byte_store,
    make_meta_store,
    store_sound,
)

FAKE_FLAC = b"FAKEFLAC-bytes-\x00\x01\x02"
OTHER_BYTES = b"a-different-blob"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _record(*, cache_bytes_ok: bool, uri=None, sound_id: str = "s1") -> SoundRecord:
    """A SoundRecord whose nested license carries the given cache_bytes_ok flag."""
    lic = LicenseRecord(source="test", cache_bytes_ok=cache_bytes_ok)
    return SoundRecord(id=sound_id, uri=uri, license=lic)


def _stores(tmp_path):
    """A fresh (byte store, meta store) pair rooted under tmp_path."""
    sounds = make_byte_store(tmp_path / "audio")
    meta = make_meta_store(tmp_path / "meta")
    return sounds, meta


# ---------------------------------------------------------------------------
# content addressing
# ---------------------------------------------------------------------------


def test_content_key_matches_hashlib_and_is_deterministic():
    expected = hashlib.new(HASH_ALGO, FAKE_FLAC).hexdigest()
    assert content_key(FAKE_FLAC) == expected
    # deterministic across calls
    assert content_key(FAKE_FLAC) == content_key(FAKE_FLAC)


def test_content_key_dedups_identical_bytes():
    # identical bytes -> identical key (the basis for dedup)
    assert content_key(FAKE_FLAC) == content_key(b"FAKEFLAC-bytes-\x00\x01\x02")


def test_content_key_distinguishes_different_bytes():
    assert content_key(FAKE_FLAC) != content_key(OTHER_BYTES)


# ---------------------------------------------------------------------------
# stores behave as MutableMapping
# ---------------------------------------------------------------------------


def test_byte_store_is_mutable_mapping(tmp_path):
    sounds, _ = _stores(tmp_path)
    assert len(sounds) == 0
    key = content_key(FAKE_FLAC)
    sounds[key] = FAKE_FLAC
    assert sounds[key] == FAKE_FLAC
    assert key in sounds
    assert list(sounds) == [key]
    assert len(sounds) == 1
    del sounds[key]
    assert len(sounds) == 0


def test_meta_store_roundtrips_sound_record(tmp_path):
    _, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=True, sound_id="sound-42")
    rec.caption = "a wooden door creak"
    rec.tags = ["door", "creak"]
    meta[rec.id] = rec
    read_back = meta[rec.id]
    assert isinstance(read_back, SoundRecord)
    assert read_back == rec


def test_meta_store_exposes_bare_ids_over_json_files(tmp_path):
    _, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=True, sound_id="sound-42")
    meta[rec.id] = rec
    # keys are the bare sound_id, not the on-disk filename
    assert list(meta) == ["sound-42"]
    assert "sound-42" in meta
    # ...but the backing file carries the .json suffix
    files = sorted(p.name for p in (tmp_path / "meta").iterdir())
    assert files == ["sound-42.json"]


# ---------------------------------------------------------------------------
# store_sound — the by-value vs by-reference gate
# ---------------------------------------------------------------------------


def test_store_sound_by_value_caches_bytes(tmp_path):
    sounds, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=True)
    returned = store_sound(rec, FAKE_FLAC, sounds=sounds, meta=meta)

    assert returned is rec  # mutated in place
    assert rec.storage_mode == StorageMode.by_value
    assert rec.uri == content_key(FAKE_FLAC)
    assert rec.content_sha256 == rec.uri
    # bytes actually landed in the content-addressed store
    assert sounds[rec.uri] == FAKE_FLAC
    assert len(sounds) == 1
    # and the record was persisted to meta
    assert meta[rec.id] == rec


def test_store_sound_by_reference_stores_no_bytes(tmp_path):
    sounds, meta = _stores(tmp_path)
    src_url = "https://freesound.org/s/1/"
    rec = _record(cache_bytes_ok=False, uri=src_url)
    store_sound(rec, FAKE_FLAC, sounds=sounds, meta=meta)

    assert rec.storage_mode == StorageMode.by_reference
    # CRUCIAL: absolutely no bytes were cached
    assert len(sounds) == 0
    # the fetchable uri is preserved untouched
    assert rec.uri == src_url
    # the hash is still recorded, for provenance only
    assert rec.content_sha256 == content_key(FAKE_FLAC)
    # metadata is persisted regardless of storage mode
    assert meta[rec.id] == rec


def test_store_sound_by_reference_without_uri_raises(tmp_path):
    sounds, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=False, uri=None)
    with pytest.raises(ValueError):
        store_sound(rec, FAKE_FLAC, sounds=sounds, meta=meta)
    # nothing was written on the failure path
    assert len(sounds) == 0
    assert len(meta) == 0


def test_store_sound_by_reference_without_data_still_needs_uri(tmp_path):
    sounds, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=False, uri="s3://bucket/key")
    store_sound(rec, None, sounds=sounds, meta=meta)
    assert rec.storage_mode == StorageMode.by_reference
    assert rec.uri == "s3://bucket/key"
    # no data given -> no provenance hash, no bytes
    assert rec.content_sha256 is None
    assert len(sounds) == 0


def test_store_sound_by_value_requires_data_falls_through_to_reference(tmp_path):
    # cache allowed but no bytes provided => cannot store by value; falls through
    # to the by-reference branch (which then requires a uri).
    sounds, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=True, uri="https://example.com/x.flac")
    store_sound(rec, None, sounds=sounds, meta=meta)
    assert rec.storage_mode == StorageMode.by_reference
    assert len(sounds) == 0


# ---------------------------------------------------------------------------
# the gate is driven by the license (invariant #1) unless overridden
# ---------------------------------------------------------------------------


def test_gate_reads_license_cache_bytes_ok_when_override_none(tmp_path):
    # Prove invariant #1: with cache_bytes_ok left as None, the SAME call routes
    # to by-value or by-reference purely from the record's own license flag.
    sounds, meta = _stores(tmp_path)

    by_value_rec = _record(cache_bytes_ok=True, sound_id="v")
    store_sound(by_value_rec, FAKE_FLAC, sounds=sounds, meta=meta)
    assert by_value_rec.storage_mode == StorageMode.by_value

    by_ref_rec = _record(cache_bytes_ok=False, uri="https://x/y", sound_id="r")
    store_sound(by_ref_rec, FAKE_FLAC, sounds=sounds, meta=meta)
    assert by_ref_rec.storage_mode == StorageMode.by_reference

    # only the by-value blob is present
    assert len(sounds) == 1
    assert sounds[content_key(FAKE_FLAC)] == FAKE_FLAC


# ---------------------------------------------------------------------------
# id safety at the storage boundary (invariant #3) — once SOURCE adapters mint
# external-derived ids, an id with os.sep / .. / a drive letter / NUL must NOT
# escape the meta dir, collide, or vanish from iteration.
# ---------------------------------------------------------------------------

# ids that would escape / spawn a subdir / shadow a dotfile if written naively
HOSTILE_IDS = [
    "../evil",  # parent-dir escape
    "../../etc/passwd",  # deep escape
    "a/b",  # subdirectory
    "..",  # bare parent ref (encodes to a leading-dot filename)
    ".",  # bare current ref (leading-dot filename)
    "/abs/path",  # absolute path
    "C:\\Windows\\sys",  # windows drive + backslash separators
    ".hidden",  # leading dot -> dol skips dotfiles on iteration
    "a\x00b",  # embedded NUL (C-string truncation)
]

# realistic external ids a source adapter would mint (must round-trip verbatim)
EXTERNAL_IDS = [
    "freesound:12345",
    "https://freesound.org/s/1/",
    "elevenlabs/sfx-2024-01",
    "uníçodé-🎧",
    "50%off-sale",
]


def test_meta_store_hostile_ids_do_not_escape_root(tmp_path):
    meta_root = tmp_path / "meta"
    _, meta = _stores(tmp_path)
    for i, sid in enumerate(HOSTILE_IDS):
        rec = _record(cache_bytes_ok=True, sound_id=sid)
        rec.caption = f"payload-{i}"
        meta[sid] = rec

    # NOTHING was written outside the meta dir (no parent-dir escape).
    stray = [p.name for p in tmp_path.iterdir() if p.name not in {"meta", "audio"}]
    assert stray == []
    # every backing file is a single component directly under the meta root
    # (no subdirectories spawned by an id containing os.sep).
    assert [p for p in meta_root.iterdir() if p.is_dir()] == []
    # and no file is a dotfile (which dol would omit from iteration).
    assert all(not p.name.startswith(".") for p in meta_root.iterdir())


def test_meta_store_hostile_ids_roundtrip_and_iterate(tmp_path):
    _, meta = _stores(tmp_path)
    for i, sid in enumerate(HOSTILE_IDS):
        rec = _record(cache_bytes_ok=True, sound_id=sid)
        rec.caption = f"payload-{i}"
        meta[sid] = rec

    # keys come back as the ORIGINAL ids (reversible encoding), none dropped...
    assert set(meta) == set(HOSTILE_IDS)
    assert len(meta) == len(HOSTILE_IDS)
    # ...and each record reads back intact under its original id.
    for i, sid in enumerate(HOSTILE_IDS):
        assert sid in meta
        assert meta[sid].caption == f"payload-{i}"


def test_meta_store_external_ids_roundtrip(tmp_path):
    _, meta = _stores(tmp_path)
    for sid in EXTERNAL_IDS:
        meta[sid] = _record(cache_bytes_ok=True, sound_id=sid)
    assert set(meta) == set(EXTERNAL_IDS)
    for sid in EXTERNAL_IDS:
        assert meta[sid].id == sid


def test_meta_store_hex_content_id_is_a_noop(tmp_path):
    # Backward-compat: a hex content id must map to {hex}.json unchanged, so
    # meta files written before this fix stay readable.
    _, meta = _stores(tmp_path)
    hex_id = content_key(FAKE_FLAC)  # all url-unreserved chars
    meta[hex_id] = _record(cache_bytes_ok=True, sound_id=hex_id)
    files = sorted(p.name for p in (tmp_path / "meta").iterdir())
    assert files == [f"{hex_id}.json"]
    assert list(meta) == [hex_id]


def test_meta_filename_is_never_a_dotfile_and_is_injective():
    filenames = [_meta_filename(s) for s in HOSTILE_IDS + EXTERNAL_IDS]
    assert all(not fn.startswith(".") for fn in filenames)  # iterable by dol
    assert all(("/" not in fn and "\\" not in fn) for fn in filenames)  # no sep
    assert len(set(filenames)) == len(filenames)  # collision-free


def test_store_sound_rejects_empty_id_before_any_write(tmp_path):
    sounds, meta = _stores(tmp_path)
    rec = _record(cache_bytes_ok=True, sound_id="")
    with pytest.raises(ValueError):
        store_sound(rec, FAKE_FLAC, sounds=sounds, meta=meta)
    # fail-closed BEFORE side effects: no orphan blob, no meta entry
    assert len(sounds) == 0
    assert len(meta) == 0


def test_explicit_override_beats_license_flag(tmp_path):
    sounds, meta = _stores(tmp_path)

    # license says cache is fine, but the caller forces by-reference
    rec = _record(cache_bytes_ok=True, uri="https://x/y", sound_id="forced-ref")
    store_sound(rec, FAKE_FLAC, sounds=sounds, meta=meta, cache_bytes_ok=False)
    assert rec.storage_mode == StorageMode.by_reference
    assert len(sounds) == 0

    # license forbids caching, but the caller forces by-value
    rec2 = _record(cache_bytes_ok=False, sound_id="forced-val")
    store_sound(rec2, OTHER_BYTES, sounds=sounds, meta=meta, cache_bytes_ok=True)
    assert rec2.storage_mode == StorageMode.by_value
    assert sounds[content_key(OTHER_BYTES)] == OTHER_BYTES
