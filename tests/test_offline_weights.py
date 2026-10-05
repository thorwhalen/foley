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
                raise OSError(
                    f"We couldn't connect to 'https://huggingface.co' to load the files, "
                    f"and couldn't find them in the cached files for {model_id}."
                )
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


def _downloading_loader(calls):
    """A loader that, like AudioSeal / whisperX, fetches its weights over the network."""
    import socket

    def load(*a, **k):
        calls.append(a)
        try:
            socket.create_connection(("192.0.2.10", 443), timeout=0.01)
        except OSError as exc:
            raise RuntimeError(f"download failed: {exc}") from exc
        return object()

    return load


def test_audioseal_does_not_download_under_offline(monkeypatch):
    pytest.importorskip("torch")
    from foley.provenance import disclosure

    calls = []
    fake = types.SimpleNamespace(AudioSeal=types.SimpleNamespace(
        load_generator=_downloading_loader(calls)))
    monkeypatch.setitem(sys.modules, "audioseal", fake)
    wm = disclosure.AudioSealWatermarker.__new__(disclosure.AudioSealWatermarker)
    with foley.offline():
        with pytest.raises(ModelNotCached, match="AudioSeal"):
            wm._generator
    assert calls  # the loader ran, but its connection never left the machine


def test_whisperx_does_not_download_under_offline(monkeypatch):
    np = pytest.importorskip("numpy")
    from foley.weave import align

    calls = []
    fake = types.SimpleNamespace(load_model=_downloading_loader(calls),
                                 load_align_model=_downloading_loader(calls))
    monkeypatch.setitem(sys.modules, "whisperx", fake)
    aligner = align.WhisperXAligner(model_size="base", device="cpu", batch_size=1)
    with foley.offline():
        with pytest.raises(ModelNotCached, match="whisperX"):
            aligner.word_timeline(np.zeros(16000, dtype=np.float32), 16000, transcript="hi")


def test_mcp_tools_run_under_the_servers_offline_posture():
    from foley.agent import mcp
    from foley.runtime import RuntimeConfig, current_runtime

    seen = []

    def probe():
        seen.append(current_runtime().offline)

    old = mcp._STATE["runtime"]
    mcp._STATE["runtime"] = RuntimeConfig.offline_local()
    try:
        mcp._under_bound_runtime(probe)()
    finally:
        mcp._STATE["runtime"] = old
    assert seen == [True]


def test_find_warns_when_generation_weights_are_missing_offline(fake_diffusers, fake_embedder):
    from foley.index import MemoryIndex, SoundLibrary

    idx = MemoryIndex(dim=fake_embedder.dim)
    empty = SoundLibrary(sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder)
    foley.obs.configure(run_store={})
    try:
        with foley.offline(), pytest.warns(UserWarning, match="not in the local cache"):
            foley.find("The heavy oak door creaked.", library=empty)
    finally:
        foley.obs.reset()


def test_a_non_cache_error_is_not_relabelled_as_a_missing_model():
    from foley.runtime import load_pretrained

    def bad_dtype(model_id, **kw):
        raise ValueError("unsupported torch_dtype 'float8'")

    with foley.offline():
        with pytest.raises(ValueError, match="torch_dtype"):
            load_pretrained(bad_dtype, "x/y")


def test_a_corrupt_cached_model_is_not_reported_as_missing(monkeypatch):
    from foley import runtime
    from foley.runtime import load_pretrained

    monkeypatch.setattr(runtime, "_repo_in_hf_cache", lambda model_id: True)  # it IS cached

    def corrupt(model_id, **kw):
        raise OSError("Unable to load weights from pytorch checkpoint file for 'x/y'")

    with foley.offline():
        with pytest.raises(OSError, match="Unable to load weights") as exc:
            load_pretrained(corrupt, "x/y")
    assert not isinstance(exc.value, ModelNotCached)


def test_a_truncated_panns_checkpoint_counts_as_missing(tmp_path, monkeypatch):
    from foley.index import taggers

    data = tmp_path / "panns_data"
    data.mkdir()
    (data / "Cnn14_mAP=0.431.pth").write_bytes(b"partial")
    (data / "class_labels_indices.csv").write_text("index,mid,display_name\n")
    monkeypatch.setattr(taggers, "PANNS_DATA_DIR", str(data))
    with foley.offline():
        with pytest.raises(ModelNotCached, match="PANNs"):
            taggers._require_panns_files()
