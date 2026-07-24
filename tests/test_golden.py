"""Validate the frozen golden-eval seed fixture (``tests/golden/seed.json``).

#4 ships the seed + schema (not the scorer — that is #10a). These tests pin the
GoldenItem schema and, crucially, that every ``answer_clip_ids`` reference
resolves to a real clip in the bundled Ring-0 fixture, so #10a's metrics harness
can run end-to-end against a real (tiny) corpus with no download.
"""

import json
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden" / "seed.json"
RING0_MANIFEST = (
    Path(__file__).parent.parent / "foley" / "data" / "ring0" / "manifest.json"
)

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
