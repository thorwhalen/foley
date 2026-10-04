"""The one dispatch path, cost, the generations cache and loud errors (#53 #57 #59 #64).

Every test drives the public verbs (``foley.generate`` / ``find`` / ``add_from`` /
``estimate``) with injected adapters that count their calls, so "nothing was paid for"
is asserted directly.
"""

import io

import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")

import foley  # noqa: E402
from foley.agent.policy import Budget  # noqa: E402
from foley.base import Candidate, CandidateOrigin, SoundRecord  # noqa: E402
from foley.cost import BudgetExceeded, CostApprovalRequired  # noqa: E402
from foley.index import MemoryIndex, SoundLibrary  # noqa: E402
from foley.sources._dispatch import UnsupportedParameter  # noqa: E402
from foley.sources.base import (  # noqa: E402
    GeneratedClip,
    SourceConfigurationError,
    generated_license,
)
from foley.sources.registry import SOURCE_REGISTRY, register_source  # noqa: E402

SR = 16_000
DEMO = "The heavy oak door creaked as rain fell outside."


@pytest.fixture(autouse=True)
def _run_store():
    foley.obs.configure(run_store={})
    yield
    foley.obs.reset()


@pytest.fixture
def library(fake_embedder):
    idx = MemoryIndex(dim=fake_embedder.dim)
    return SoundLibrary(sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder)


def _wav(freq=440.0, *, silent=False, dur=0.6):
    t = np.linspace(0.0, dur, int(SR * dur), endpoint=False, dtype=np.float32)
    y = np.zeros_like(t) if silent else 0.5 * np.sin(2 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, y.astype(np.float32), SR, format="WAV")
    return buf.getvalue()


class CountingAdapter:
    """A generate adapter that counts calls and returns a fresh tone each time."""

    def __init__(self, config, *, silent=False):
        self.config = config
        self.name = config["name"]
        self.calls = 0
        self.silent = silent

    def generate(self, prompt, **affordances):
        self.calls += 1
        lic = generated_license(
            source=self.name,
            license_id="Stability-Community",
            generator_model="fake-1",
            generation_prompt=prompt,
        )
        rec = SoundRecord(id=f"{self.name}:pending", license=lic, caption=prompt)
        cand = Candidate(sound=rec, origin=CandidateOrigin.generated)
        audio = _wav(300 + 40 * self.calls, silent=self.silent)
        return GeneratedClip(audio_bytes=audio, candidate=cand, notes=[])


def _config(name, pricing, **extra):
    return {
        "name": name,
        "kind": "generate",
        "supported_affordances": ["prompt", "duration", "seed"],
        "on_unsupported_param": "warn",
        "native_defaults": {"duration_min_s": 0.5, "duration_max_s": 30.0},
        "data_egress": "external",
        "pricing": pricing,
        **extra,
    }


@pytest.fixture
def paid_source():
    """Register a $0.40-per-call external generator; unregister afterwards."""
    made = []

    def make(name="paidgen", *, amount=0.40, unit="per_call", silent=False):
        cfg = _config(name, {"unit": unit, "amount_usd": amount} if unit else None)
        adapter = CountingAdapter(cfg, silent=silent)
        register_source(name, cfg, adapter)
        made.append(name)
        return adapter

    yield make
    for name in made:
        SOURCE_REGISTRY.pop(name, None)


def _el_adapter(transport=None, *, plan="elevenlabs-paid-plan", api_key="k"):
    from foley.sources.elevenlabs.adapter import ElevenLabsAdapter

    def must_not_call(*a, **k):
        raise AssertionError("the ElevenLabs API must not be called")

    return ElevenLabsAdapter(api_key=api_key, http=transport or must_not_call, plan=plan)


# ---------------------------------------------------------------------------
# #53 — one dispatch path; drops are raised or visible on the result
# ---------------------------------------------------------------------------


def test_a_meaning_carrying_parameter_raises_before_any_call(library):
    """The acceptance line: seed on ElevenLabs (non-deterministic) raises."""
    with pytest.raises(UnsupportedParameter, match="seed"):
        foley.generate("a door creaks", backend="elevenlabs", adapter=_el_adapter(),
                       library=library, seed=1)


def test_under_warn_every_drop_is_on_the_returned_candidate(library, paid_source):
    paid_source("droppy", amount=0.01)
    with pytest.warns(UserWarning, match="steps"):
        cand = foley.generate("a door creaks", backend="droppy", library=library,
                              steps=12, negative_prompt="hum", on_unsupported="warn",
                              duration=99)
    joined = " | ".join(cand.notes)
    assert "steps=12" in joined and "negative_prompt='hum'" in joined
    assert "clamped to 30 s" in joined
    assert cand.cost_estimate_usd == pytest.approx(0.01)


def test_an_ordinary_drop_is_noted_without_raising(library, paid_source):
    paid_source("droppy2", amount=0.01)
    with pytest.warns(UserWarning):
        cand = foley.generate("rain", backend="droppy2", library=library, steps=8)
    assert any("steps=8" in n for n in cand.notes)


def test_add_from_notes_unsupported_search_parameters(library):
    class StubSearch:
        config = {"name": "stubsearch", "supported_affordances": ["query", "k", "license"],
                  "data_egress": "external"}

        def search(self, query, **kw):
            assert "ucs_category" not in kw  # dropped before the source sees it
            return []

    report = foley.add_from("stubsearch", query="door", library=library,
                            adapter=StubSearch(), ucs_category="DOORWood")
    assert any("ucs_category" in n for n in report.notes)


# ---------------------------------------------------------------------------
# #57 — cost model: None = unknown, cumulative cap, stop before the first paid call
# ---------------------------------------------------------------------------


def test_estimate_is_none_when_unknown_never_zero(paid_source):
    paid_source("mystery", unit=None)
    assert foley.estimate("generate", backend="mystery") is None
    assert foley.estimate("generate", backend="stable_audio") == 0.0
    assert foley.estimate("generate", backend="elevenlabs", duration=3) == pytest.approx(0.006)


def test_unknown_cost_needs_approval(library, paid_source):
    adapter = paid_source("mystery2", unit=None)
    with pytest.raises(CostApprovalRequired):
        foley.generate("a door creaks", backend="mystery2", library=library)
    assert adapter.calls == 0
    cand = foley.generate("a door creaks", backend="mystery2", library=library,
                          budget=Budget(approve_unknown_cost=True))
    assert adapter.calls == 1 and cand.cost_estimate_usd is None


def test_a_call_over_the_default_one_dollar_cap_is_refused(library, paid_source):
    adapter = paid_source("pricey", amount=2.0)
    with pytest.raises(BudgetExceeded):
        foley.generate("a door creaks", backend="pricey", library=library)
    assert adapter.calls == 0


def test_find_stops_before_the_first_paid_call_over_budget(paid_source, fake_embedder):
    """The acceptance line: a find whose estimate exceeds the budget never pays."""
    idx = MemoryIndex(dim=fake_embedder.dim)
    empty = SoundLibrary(sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder)
    adapter = paid_source("pricey2", amount=2.0)
    hits = foley.find(DEMO, library=empty, backend="pricey2", budget=Budget(max_usd=1.0))
    assert adapter.calls == 0 and hits == []


def test_the_cap_is_cumulative_across_events(paid_source, fake_embedder):
    idx = MemoryIndex(dim=fake_embedder.dim)
    empty = SoundLibrary(sounds={}, meta={}, vindex=idx, kindex=idx, embedder=fake_embedder)
    adapter = paid_source("sixty", amount=0.60)
    budget = Budget(max_usd=1.0)
    foley.find(DEMO, library=empty, backend="sixty", budget=budget, verify="clap")
    assert adapter.calls == 1  # a second $0.60 generation would pass $1
    assert budget.spent_usd == pytest.approx(0.60)


def test_a_paid_llm_rung_needs_approval(monkeypatch, library):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with pytest.raises(CostApprovalRequired, match="LLM"):
        foley.find(DEMO, library=library, llm="anthropic")


# ---------------------------------------------------------------------------
# #59 — paid bytes are never lost and never paid for twice
# ---------------------------------------------------------------------------


def test_an_identical_paid_request_is_a_cache_hit(library, paid_source):
    adapter = paid_source("cached", amount=0.05)
    first = foley.generate("a door creaks", backend="cached", library=library, duration=2)
    second = foley.generate("a door creaks", backend="cached", library=library, duration=2)
    assert adapter.calls == 1
    assert second.sound.id == first.sound.id
    assert second.cost_actual_usd == 0.0
    assert any("generations cache" in n for n in second.notes)
    foley.generate("a door creaks", backend="cached", library=library, duration=2,
                   reuse_cached=False)
    assert adapter.calls == 2


def test_a_quarantined_generation_keeps_its_bytes(library, paid_source,
                                                  _in_memory_generations_cache):
    paid_source("silent", amount=0.05, silent=True)
    with pytest.raises(foley.GenerationError) as exc:
        foley.generate("a door creaks", backend="silent", library=library)
    assert exc.value.status == "quarantined"
    cache = _in_memory_generations_cache
    (entry,) = cache.requests.values()
    assert cache.audio[entry["content_key"]]  # the paid bytes are retrievable
    assert any(key in str(exc.value) or key in " ".join(r_n for r in exc.value.report.results
                                                         for r_n in r.notes)
               for key in cache.requests)


# ---------------------------------------------------------------------------
# #64 — the root cause reaches the caller
# ---------------------------------------------------------------------------


def test_a_missing_key_names_the_env_var_and_its_sign_up_url(library, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    adapter = _el_adapter(api_key=None)
    with pytest.raises(SourceConfigurationError) as exc:
        foley.generate("a door creaks", backend="elevenlabs", adapter=adapter, library=library)
    assert "ELEVENLABS_API_KEY" in str(exc.value)
    assert "https://elevenlabs.io/app/settings/api-keys" in str(exc.value)


def test_add_from_raises_on_a_missing_key(library, monkeypatch):
    from foley.sources.freesound.adapter import FreesoundAdapter

    monkeypatch.delenv("FREESOUND_API_KEY", raising=False)
    adapter = FreesoundAdapter(http=lambda *a, **k: pytest.fail("no HTTP without a key"))
    with pytest.raises(SourceConfigurationError) as exc:
        foley.add_from("freesound", query="door", library=library, adapter=adapter)
    assert "FREESOUND_API_KEY" in str(exc.value) and "http" in str(exc.value)


def test_a_backend_failure_is_chained_into_generation_error(library, paid_source):
    adapter = paid_source("flaky", amount=0.01)

    def boom(prompt, **kw):
        raise RuntimeError("upstream 503: try later")

    adapter.generate = boom
    with pytest.raises(foley.GenerationError, match="upstream 503") as exc:
        foley.generate("a door creaks", backend="flaky", library=library)
    assert isinstance(exc.value.__cause__, RuntimeError)
