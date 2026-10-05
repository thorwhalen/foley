"""offline() never downloads model weights (#86).

Each test fails without the fix: the load would reach for the network (tripping the
suite's socket guard, which fails the test) or the library's own downloader.
"""

import sys
import types

import pytest

import foley
import foley.runtime as _runtime

# The base class exists without #86's fix too, so these tests fail on BEHAVIOUR (a
# download attempt trips the socket guard), not on an import error.
ModelNotCached = getattr(_runtime, "ModelNotCached", _runtime.EgressBlocked)

NOT_CACHED = "foley-test/definitely-not-a-cached-model"


def test_clap_does_not_download_under_offline():
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    from foley.index.embedders import ClapEmbedder

    with foley.offline():
        with pytest.raises(ModelNotCached, match=NOT_CACHED) as exc:
            ClapEmbedder(NOT_CACHED).embed_text("rain on a window")
    assert "huggingface-cli download" in str(exc.value)


@pytest.fixture
def fake_diffusers(monkeypatch):
    """A diffusers stand-in whose loader would 'download' unless told local-only."""
    pytest.importorskip("torch")
    calls = []

    class StableAudioPipeline:
        @staticmethod
        def from_pretrained(model_id, **kw):
            calls.append(kw)
            if kw.get("local_files_only"):
                raise OSError(f"{model_id} not found in the local cache")
            raise AssertionError("would download weights from the Hub")

    monkeypatch.setitem(sys.modules, "diffusers", types.SimpleNamespace(
        StableAudioPipeline=StableAudioPipeline))
    return calls


def test_stable_audio_does_not_download_under_offline(fake_diffusers, fake_embedder):
    from foley.index import MemoryIndex, SoundLibrary
    from foley.sources.stable_audio.adapter import StableAudioAdapter

    idx = MemoryIndex(dim=fake_embedder.dim)
    lib = SoundLibrary(sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder)
    with foley.offline():
        with pytest.raises(ModelNotCached, match="stable-audio-open-1.0"):
            foley.generate("a door creaks", backend="stable_audio",
                           adapter=StableAudioAdapter(), library=lib)
    assert fake_diffusers == [{"torch_dtype": fake_diffusers[0]["torch_dtype"],
                               "local_files_only": True}]


def test_online_loads_are_unchanged(fake_diffusers):
    from foley.sources.stable_audio.adapter import StableAudioAdapter

    with pytest.raises(AssertionError, match="would download"):
        StableAudioAdapter()._load_pipeline()  # online: a plain from_pretrained
    assert "local_files_only" not in fake_diffusers[0]


def test_panns_is_refused_before_its_wget(tmp_path, monkeypatch):
    from foley.index import taggers

    monkeypatch.setattr(taggers, "PANNS_DATA_DIR", str(tmp_path / "panns_data"))
    imported = []
    monkeypatch.setitem(sys.modules, "panns_inference", types.SimpleNamespace(
        AudioTagging=lambda **kw: imported.append(kw)))
    with foley.offline():
        with pytest.raises(ModelNotCached, match="PANNs"):
            taggers.PannsTagger()._model
    assert imported == []


def test_an_offline_ingest_without_weights_raises_once(tmp_path):
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    sf = pytest.importorskip("soundfile")
    np = pytest.importorskip("numpy")
    from foley.index import MemoryIndex, SoundLibrary
    from foley.index.embedders import ClapEmbedder

    for i in range(3):
        sf.write(tmp_path / f"c{i}.wav", np.zeros(8000, dtype=np.float32) + 0.1 * i, 16000)
    emb = ClapEmbedder(NOT_CACHED)
    lib = SoundLibrary(sounds={}, meta={}, vindex=MemoryIndex(dim=512),
                       kindex=MemoryIndex(dim=512), embedder=emb)
    with foley.offline():
        with pytest.raises(ModelNotCached):
            foley.ingest(tmp_path, library=lib, do_supervised=False, do_zeroshot=False,
                         qc=False)
