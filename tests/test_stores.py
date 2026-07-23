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
