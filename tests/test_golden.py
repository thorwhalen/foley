"""Validate the frozen golden-eval seed fixture (``foley/data/golden/seed.json``).

The seed + schema ship as package data; these tests pin the GoldenItem schema
and, crucially, that every ``answer_clip_ids`` reference resolves to a real clip
in the bundled Ring-0 fixture, so the metrics harness runs end-to-end against a
real (tiny) corpus with no download.
"""

import json
from pathlib import Path

from foley.eval.golden import DEFAULT_GOLDEN_PATH, RING0_MANIFEST_PATH

GOLDEN = DEFAULT_GOLDEN_PATH
RING0_MANIFEST = RING0_MANIFEST_PATH

_REQUIRED_ITEM_KEYS = {
    "id",
    "context",
    "expected_events",
    "negatives",
    "answer_clip_ids",
    "grade",
    "labeler",
    "schema_version",
}
_REQUIRED_EVENT_KEYS = {"query", "ucs_catid", "layer", "diegetic", "salience"}


def _load(path):
    return json.loads(Path(path).read_text())


def test_golden_seed_schema_is_well_formed():
    items = _load(GOLDEN)
    assert isinstance(items, list) and len(items) >= 3
    ids = [it["id"] for it in items]
    assert len(set(ids)) == len(ids)  # unique ids
    for it in items:
        assert _REQUIRED_ITEM_KEYS <= set(it), it["id"]
        assert it["schema_version"] == 1
        assert it["expected_events"], it["id"]
        for ev in it["expected_events"]:
            assert _REQUIRED_EVENT_KEYS <= set(ev), it["id"]
        # grades are on the frozen 0..2 scale (0 wrong / 1 acceptable / 2 ideal)
        for clip_id, g in it["grade"].items():
            assert g in (0, 1, 2), f"{it['id']} grade {clip_id}={g} out of 0..2"


def test_golden_answer_clips_reference_real_ring0_clips():
    manifest = _load(RING0_MANIFEST)
    ring0_stems = {Path(e["file"]).stem for e in manifest}
    for it in _load(GOLDEN):
        referenced = {
            clip_id
            for clip_ids in it["answer_clip_ids"].values()
            for clip_id in clip_ids
        }
        assert referenced, it["id"]
        for ref in referenced:
            corpus, _, stem = ref.partition(":")
            assert corpus == "ring0", ref
            assert stem in ring0_stems, f"{ref} not in Ring-0 fixture"
        # every graded clip is also an answer clip
        assert set(it["grade"]) <= referenced, it["id"]
