"""Tests for the generation source adapters + the generate facade (#6).

Hermetic, mirroring ``tests/test_freesound.py``: NO network, NO ``requests``, NO
``torch`` / ``diffusers`` on the primary paths.

* **ElevenLabs** (hosted) — HTTP is dependency-injected, so a POST-aware
  :class:`FakeTransport` returns canned (soundfile-decodable) audio bytes.
* **Stable Audio Open** (local) — the pipeline is dependency-injected, so a
  :class:`FakePipeline` returns a canned stereo tone with no ML stack. Only the
  seeded-determinism test needs ``torch`` (``importorskip``-guarded).

The load-bearing assertions: both generators build an AI-generated
:class:`~foley.base.LicenseRecord` (``is_ai_generated`` + provenance, flags DERIVED
from ``license_id``); the facade stores BY-VALUE with a content-hash id (the
flywheel); the ``ai_training_ok=False`` gate is operator-consented (embed+persist
only, the flag never flips); the unified affordances map to RESOLVED native params
(``guidance_scale`` not ``cfg_scale``); and ``import foley`` / discovery stay
dol-only.
"""

import subprocess
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("soundfile")  # the facade decodes/encodes real audio bytes

from foley.audio import encode  # noqa: E402
from foley.base import (  # noqa: E402
    AcquisitionMethod,
    Candidate,
    CandidateOrigin,
    IntendedUse,
    SoundRecord,
    StorageMode,
)
from foley.index import MemoryIndex, SoundLibrary  # noqa: E402
from foley.index.ingest import ingest_one  # noqa: E402
from foley.licensing import keep  # noqa: E402
from foley.provenance.credits import attribution_line  # noqa: E402
from foley.sources import candidate_of, generate as generate_backend  # noqa: E402
from foley.sources.base import (  # noqa: E402
    GenerateAdapter,
    GeneratedClip,
    SourceAdapter,
    generated_license,
)
from foley.sources.elevenlabs import SOURCE_CONFIG as EL_CONFIG  # noqa: E402
from foley.sources.elevenlabs.adapter import ElevenLabsAdapter  # noqa: E402
from foley.sources.stable_audio import SOURCE_CONFIG as SA_CONFIG  # noqa: E402
from foley.sources.stable_audio.adapter import StableAudioAdapter  # noqa: E402

import foley  # noqa: E402

SR = 44_100


# ---------------------------------------------------------------------------
# audio + backend test doubles (no requests, no torch, no network)
# ---------------------------------------------------------------------------


def _mono_tone(freq=440.0, seconds=1.0, amp=0.4):
    t = np.arange(int(SR * seconds), dtype=np.float32) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _stereo_tone(freq=440.0, seconds=1.0, amp=0.4):
    """Channel-FIRST ``(2, N)`` — the Stable Audio Open output layout."""
    mono = _mono_tone(freq, seconds, amp)
    return np.stack([mono, mono])


def _flac(samples):
    return encode(samples, SR)


@dataclass
class FakeResponse:
    """A structural :class:`foley.sources.http.Response` (no requests)."""

    status_code: int = 200
    _payload: Any = None
    content: bytes = b""

    def json(self):
        if self._payload is None:
            raise ValueError("response has no JSON body")
        return self._payload


class FakeTransport:
    """Records each call (incl. the POST ``json`` body); returns a canned response."""

    def __init__(self, response=None):
        self._response = response
        self.calls = []

    def __call__(self, method, url, *, params=None, headers=None, json=None):
        self.calls.append(
            SimpleNamespace(
                method=method,
                url=url,
                params=params or {},
                headers=headers or {},
                json=json or {},
            )
        )
        if self._response is not None:
            return self._response
        return FakeResponse(200, None, _flac(_mono_tone()))


class FakePipeline:
    """A stand-in for ``diffusers.StableAudioPipeline`` — records call kwargs."""

    def __init__(self, *, sr=SR):
        self.vae = SimpleNamespace(sampling_rate=sr)
        self.device = "cpu"
        self.calls = []
        self._audio = _stereo_tone()

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(audios=[self._audio])


@pytest.fixture
def library(fake_embedder):
    """A fresh in-memory FakeEmbedder-backed library (no CLAP, no disk)."""
    idx = MemoryIndex(dim=fake_embedder.dim)
    return SoundLibrary(
        sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder
    )


def _el_adapter(transport=None, *, api_key="test-key"):
    return ElevenLabsAdapter(api_key=api_key, http=transport or FakeTransport())


def _sa_adapter(pipeline=None):
    return StableAudioAdapter(pipeline=pipeline or FakePipeline())


# ---------------------------------------------------------------------------
# (a) ElevenLabs generate() builds a valid GeneratedClip
# ---------------------------------------------------------------------------


def test_elevenlabs_generate_builds_clip():
    clip = _el_adapter().generate("distant thunder", duration=4.0)
    assert isinstance(clip, GeneratedClip)
    cand = clip.candidate
    assert cand.origin == CandidateOrigin.generated
    lic = cand.sound.license
    assert lic.license_id == "ElevenLabs-SFX"
    assert lic.is_ai_generated is True
    assert lic.generator_model == "eleven_text_to_sound_v2"
    assert lic.generation_seed is None  # non-deterministic backend
    assert lic.generation_prompt == "distant thunder"
    assert lic.acquisition_method == AcquisitionMethod.generated
    assert lic.cache_bytes_ok is True and lic.ai_training_ok is False
    assert lic.rights_verified is True and lic.disclosure_recommended is True
    assert cand.sound.caption == "distant thunder"
    assert len(clip.audio_bytes) > 0


# ---------------------------------------------------------------------------
# (b) ElevenLabs request shape (endpoint, query vs body, auth)
# ---------------------------------------------------------------------------


def test_elevenlabs_request_shape():
    transport = FakeTransport()
    _el_adapter(transport).generate("rain", duration=3.0, prompt_influence=0.7, loop=True)
    call = transport.calls[0]
    assert call.method == "POST"
    assert call.url.endswith("/v1/sound-generation")
    # output_format is a QUERY param, never in the JSON body
    assert "output_format" in call.params
    assert "output_format" not in call.json
    # body carries text / model_id / prompt_influence / loop / duration_seconds
    assert call.json["text"] == "rain"
    assert call.json["model_id"] == "eleven_text_to_sound_v2"
    assert call.json["prompt_influence"] == 0.7
    assert call.json["loop"] is True
    assert call.json["duration_seconds"] == 3.0
    assert call.headers["xi-api-key"] == "test-key"


def test_elevenlabs_omits_duration_when_none():
    transport = FakeTransport()
    _el_adapter(transport).generate("rain")  # no duration -> model auto
    assert "duration_seconds" not in transport.calls[0].json


# ---------------------------------------------------------------------------
# (c) ElevenLabs output_format token -> native enum translation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token,native",
    [
        ("mp3", "mp3_44100_128"),
        ("opus", "opus_48000_128"),
        ("wav", "mp3_44100_128"),  # no lossless container; fall back to mp3
    ],
)
def test_elevenlabs_output_format_translation(token, native):
    transport = FakeTransport()
    clip = _el_adapter(transport).generate("rain", output_format=token)
    assert transport.calls[0].params["output_format"] == native
    if token == "wav":  # a fallback note is recorded
        assert any("WAV" in n or "lossless" in n for n in clip.notes)


# ---------------------------------------------------------------------------
# (d) ElevenLabs unsupported affordances warn + are never sent
# ---------------------------------------------------------------------------


def test_elevenlabs_unsupported_affordances_warn():
    transport = FakeTransport()
    clip = _el_adapter(transport).generate(
        "rain", negative_prompt="hiss", steps=50, seed=7
    )
    body = transport.calls[0].json
    for k in ("negative_prompt", "steps", "seed"):
        assert k not in body
        assert any(k in n for n in clip.notes)
    assert clip.candidate.sound.license.generation_seed is None


# ---------------------------------------------------------------------------
# (e) ElevenLabs duration clamp to the native window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("given,expected", [(100.0, 30.0), (0.1, 0.5), (12.0, 12.0)])
def test_elevenlabs_duration_clamp(given, expected):
    transport = FakeTransport()
    _el_adapter(transport).generate("rain", duration=given)
    assert transport.calls[0].json["duration_seconds"] == expected


# ---------------------------------------------------------------------------
# (f) Stable Audio Open unified -> resolved native param mapping
# ---------------------------------------------------------------------------


def test_stable_audio_param_mapping():
    pipe = FakePipeline()
    _sa_adapter(pipe).generate("a wooden door creak")  # defaults
    kw = pipe.calls[0]
    assert kw["guidance_scale"] == pytest.approx(1.0 + 0.3 * (15.0 - 1.0))  # 5.2
    assert kw["audio_end_in_s"] == 10.0  # NOT the 47.55 max
    assert kw["audio_start_in_s"] == 0.0
    assert kw["num_inference_steps"] == 200
    assert kw["output_type"] == "np"


def test_stable_audio_generation_params_record_native_names():
    clip = _sa_adapter().generate("creak", prompt_influence=0.5, steps=80)
    gp = clip.candidate.sound.license.generation_params
    # RESOLVED native names, never the unified affordance names (the cfg_scale guard)
    assert "guidance_scale" in gp and "cfg_scale" not in gp
    assert "audio_end_in_s" in gp and "duration" not in gp
    assert gp["num_inference_steps"] == 80
    assert gp["guidance_scale"] == pytest.approx(1.0 + 0.5 * (15.0 - 1.0))


# ---------------------------------------------------------------------------
# (g) Stable Audio Open duration passthrough + hard cap at the model max
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("given,expected", [(3.0, 3.0), (100.0, 47.55)])
def test_stable_audio_duration_cap(given, expected):
    pipe = FakePipeline()
    _sa_adapter(pipe).generate("creak", duration=given)
    assert pipe.calls[0]["audio_end_in_s"] == expected


# ---------------------------------------------------------------------------
# (h) Stable Audio Open provenance (license + derived revenue cap)
# ---------------------------------------------------------------------------


def test_stable_audio_provenance():
    lic = _sa_adapter().generate("creak").candidate.sound.license
    assert lic.license_id == "Stability-Community"
    assert lic.is_ai_generated is True
    assert lic.generator_model == "stable-audio-open-1.0"
    assert lic.revenue_cap_usd == 1_000_000  # DERIVED from license_id, never hand-set
    assert lic.ai_training_ok is False and lic.cache_bytes_ok is True


# ---------------------------------------------------------------------------
# (i) Stable Audio Open loop / output_format have no native param -> warn, not sent
# ---------------------------------------------------------------------------


def test_stable_audio_loop_and_format_warn_no_kwarg():
    pipe = FakePipeline()
    clip = _sa_adapter(pipe).generate("creak", loop=True, output_format="mp3")
    kw = pipe.calls[0]
    assert "loop" not in kw and "output_format" not in kw  # no fabricated kwargs
    assert any("loop" in n for n in clip.notes)
    assert any("output_format" in n for n in clip.notes)


# ---------------------------------------------------------------------------
# (j) Stable Audio Open seeded determinism (needs torch)
# ---------------------------------------------------------------------------


def test_stable_audio_seed_builds_generator():
    torch = pytest.importorskip("torch")
    pipe = FakePipeline()
    clip = _sa_adapter(pipe).generate("creak", seed=42)
    assert clip.candidate.sound.license.generation_seed == 42
    assert isinstance(pipe.calls[0]["generator"], torch.Generator)


def test_stable_audio_no_seed_never_imports_torch():
    # a seed=None generation must not import torch (fake pipeline, no ML stack)
    code = "\n".join(
        [
            "import sys, numpy as np",
            "from types import SimpleNamespace",
            "import foley",
            "from foley.sources.stable_audio.adapter import StableAudioAdapter",
            "mono = (0.3 * np.sin(np.arange(44100) / 44100.0)).astype(np.float32)",
            "class P:",
            "    def __init__(s):",
            "        s.vae = SimpleNamespace(sampling_rate=44100); s.device = 'cpu'",
            "    def __call__(s, **k):",
            "        return SimpleNamespace(audios=[np.stack([mono, mono])])",
            "StableAudioAdapter(pipeline=P()).generate('creak')",
            "assert 'torch' not in sys.modules, 'torch imported for a seedless generation'",
        ]
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# (k) KEYSTONE — the facade stores generated audio BY-VALUE (the flywheel)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["elevenlabs", "stable_audio"])
def test_facade_stores_by_value(library, backend):
    adapter = _el_adapter() if backend == "elevenlabs" else _sa_adapter()
    report = generate_backend(
        "a heavy oak door creak", backend=backend, library=library, adapter=adapter
    )
    assert len(report.ingested) == 1
    rec = report.ingested[0].record

    # BY-VALUE: bytes cached, content-addressed, locally served (contrast Freesound)
    assert rec.storage_mode == StorageMode.by_value
    assert rec.content_sha256 is not None
    assert rec.content_sha256 in library.sounds
    assert rec.uri == rec.content_sha256
    assert len(library.audio(rec.id)) > 0

    lic = rec.license
    assert lic.is_ai_generated is True
    assert lic.cache_bytes_ok is True


# ---------------------------------------------------------------------------
# (l) operator-consent: ai_training_ok stays False + the consent note is stamped
# ---------------------------------------------------------------------------


def test_facade_records_operator_consent(library):
    report = generate_backend(
        "creak", backend="stable_audio", library=library, adapter=_sa_adapter()
    )
    res = report.ingested[0]
    assert res.record.license.ai_training_ok is False  # never flipped
    assert any("consent recorded" in n for n in res.notes)


# ---------------------------------------------------------------------------
# (m) fail-closed proof: WITHOUT consent, ingest_one refuses the generated sound
# ---------------------------------------------------------------------------


def test_ingest_one_blocks_generated_without_consent(library):
    lic = generated_license(
        source="stable_audio",
        license_id="Stability-Community",
        generator_model="stable-audio-open-1.0",
        generation_prompt="creak",
    )
    res = ingest_one(
        _flac(_mono_tone()),
        library=library,
        license=lic,
        allow_ai_training_forbidden=False,  # NO consent
    )
    assert res.status == "rights_blocked"
    assert len(library) == 0 and len(library.sounds) == 0


# ---------------------------------------------------------------------------
# (n) content-hash id (not the ':pending' placeholder) + caption is searchable
# ---------------------------------------------------------------------------


def test_facade_mints_content_hash_id_and_indexes_caption(library):
    report = generate_backend(
        "distant rolling thunder",
        backend="elevenlabs",
        library=library,
        adapter=_el_adapter(),
    )
    rec = report.ingested[0].record
    assert len(rec.id) == 64 and all(c in "0123456789abcdef" for c in rec.id)
    assert rec.id != "elevenlabs:pending"
    hits = library.search("rolling thunder", k=3)
    assert hits and hits[0].sound.id == rec.id  # prompt -> caption -> BM25


# ---------------------------------------------------------------------------
# (o) dedup: a byte-identical regeneration is never stored twice
# ---------------------------------------------------------------------------


def test_facade_dedups_byte_identical_regen(library):
    adapter = _sa_adapter()  # the fake pipeline emits the same tone every call
    r1 = generate_backend("creak", backend="stable_audio", library=library, adapter=adapter)
    assert r1.ingested and r1.results[0].status in ("pass", "warn")
    r2 = generate_backend("creak", backend="stable_audio", library=library, adapter=adapter)
    assert [r.status for r in r2.results] == ["skipped_dup"]
    assert len(library) == 1


# ---------------------------------------------------------------------------
# (p) public foley.generate(...) -> a REAL stored Candidate
# ---------------------------------------------------------------------------


def test_public_generate_returns_stored_candidate(library):
    cand = foley.generate(
        "a wooden door creak", backend="stable_audio", library=library, adapter=_sa_adapter()
    )
    assert isinstance(cand, Candidate)
    assert cand.origin == CandidateOrigin.generated
    assert cand.sound.storage_mode == StorageMode.by_value
    assert len(cand.sound.id) == 64  # the PCM content hash


def test_public_generate_returns_existing_on_dedup(library):
    adapter = _sa_adapter()
    c1 = foley.generate("creak", backend="stable_audio", library=library, adapter=adapter)
    c2 = foley.generate("creak", backend="stable_audio", library=library, adapter=adapter)
    assert c2.sound.id == c1.sound.id  # the already-stored sound, via lib[id]
    assert len(library) == 1


# ---------------------------------------------------------------------------
# (q) resilience: a backend failure is an inspectable report / GenerationError
# ---------------------------------------------------------------------------


class _BoomAdapter:
    name = "boom"

    def generate(self, prompt, **kw):
        raise RuntimeError("model exploded")


def test_facade_backend_failure_is_recorded_not_raised(library):
    report = generate_backend(
        "creak", backend="stable_audio", library=library, adapter=_BoomAdapter()
    )
    assert [r.status for r in report.results] == ["error"]
    assert len(library) == 0


def test_public_generate_raises_generation_error(library):
    with pytest.raises(foley.GenerationError) as exc:
        foley.generate("creak", backend="stable_audio", library=library, adapter=_BoomAdapter())
    assert exc.value.status == "error"
    assert exc.value.report is not None


def test_elevenlabs_non_200_raises_with_detail():
    transport = FakeTransport(FakeResponse(422, {"detail": "bad request"}, b""))
    with pytest.raises(RuntimeError, match="422"):
        _el_adapter(transport).generate("rain")


def test_elevenlabs_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    adapter = ElevenLabsAdapter(http=FakeTransport())  # no api_key, no env var
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        adapter.generate("rain")


# ---------------------------------------------------------------------------
# (r) serialization stays byte-free (audio_bytes never leak into a record)
# ---------------------------------------------------------------------------


def test_stored_candidate_serializes_without_bytes(library):
    report = generate_backend(
        "creak", backend="stable_audio", library=library, adapter=_sa_adapter()
    )
    cand = candidate_of(report.ingested[0])
    js = cand.to_json()  # must not raise, must not embed raw bytes
    assert isinstance(js, str)
    assert "audio_bytes" not in js


# ---------------------------------------------------------------------------
# (s) both adapters satisfy GenerateAdapter (siblings — NOT SourceAdapter)
# ---------------------------------------------------------------------------


def test_adapters_satisfy_generate_protocol():
    assert isinstance(_el_adapter(), GenerateAdapter)
    assert isinstance(_sa_adapter(), GenerateAdapter)
    # they are the generate sibling — they need NOT satisfy the retrieve contract
    assert not isinstance(_el_adapter(), SourceAdapter)
    assert not isinstance(_sa_adapter(), SourceAdapter)


def test_configs_declare_generate_kind():
    assert EL_CONFIG["kind"] == "generate"
    assert SA_CONFIG["kind"] == "generate"


# ---------------------------------------------------------------------------
# (t) credits AI-disclosure line renders from the generation fields
# ---------------------------------------------------------------------------


def test_credits_render_ai_disclosure():
    lic = _sa_adapter().generate("creak").candidate.sound.license
    line = attribution_line(SoundRecord(id="x", license=lic, caption="creak"))
    assert "AI-generated with stable-audio-open-1.0" in line
    assert "disclosure recommended" in line


# ---------------------------------------------------------------------------
# (u) revenue-cap + will_train enforcement at select time (keep)
# ---------------------------------------------------------------------------


def test_keep_enforces_revenue_cap_and_will_train():
    lic = _sa_adapter().generate("creak").candidate.sound.license
    assert keep(lic, IntendedUse(commercial=True, revenue_usd=0)) is True
    assert keep(lic, IntendedUse(commercial=True, revenue_usd=2_000_000)) is False  # cap
    assert keep(lic, IntendedUse(will_train=True)) is False  # ai_training_ok=False
    el = _el_adapter().generate("rain").candidate.sound.license
    assert keep(el, IntendedUse(will_train=True)) is False


# ---------------------------------------------------------------------------
# hermeticity + discovery guards (fresh subprocess)
# ---------------------------------------------------------------------------


def test_import_foley_stays_dol_only():
    code = (
        "import foley, sys; "
        "assert 'torch' not in sys.modules, 'torch leaked'; "
        "assert 'diffusers' not in sys.modules, 'diffusers leaked'; "
        "assert 'requests' not in sys.modules, 'requests leaked'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_discovery_registers_generators_without_heavy_imports():
    code = (
        "import sys, foley; "
        "srcs = foley.list_sources(); "
        "assert 'stable_audio' in srcs and 'elevenlabs' in srcs, srcs; "
        "assert 'torch' not in sys.modules and 'diffusers' not in sys.modules, 'sa deps leaked'; "
        "assert 'requests' not in sys.modules, 'el deps leaked'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(
    "pkg,heavy",
    [
        ("foley.sources.stable_audio.config", "torch"),
        ("foley.sources.elevenlabs.config", "requests"),
    ],
)
def test_config_import_stays_light(pkg, heavy):
    code = (
        f"import importlib, sys; importlib.import_module('{pkg}'); "
        f"assert '{heavy}' not in sys.modules, '{heavy} eagerly loaded by config import'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
