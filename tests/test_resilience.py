"""#12 graceful degradation — throttle / backoff / circuit-break (hermetic: fake clock/sleep)."""

import pytest

from foley.sources.resilience import (
    BreakerPolicy,
    RetryPolicy,
    SourceUnavailable,
    resilient,
)


class _Resp:
    def __init__(self, code, headers=None):
        self.status_code = code
        self.content = b""
        self._headers = headers or {}

    @property
    def headers(self):
        return self._headers

    def json(self):
        return {}


def _ok_transport(*a, **k):
    return _Resp(200)


def test_passthrough_on_success():
    w = resilient(_ok_transport, clock=lambda: 0.0, sleep=lambda s: None)
    assert w("GET", "u").status_code == 200


def test_throttle_spaces_calls_by_min_interval():
    sleeps = []
    # per_min=2 -> 30s min interval; a non-advancing clock keeps demanding the full wait
    w = resilient(
        _ok_transport, rate={"per_min": 2}, clock=lambda: 0.0, sleep=sleeps.append
    )
    w("GET", "u")  # first call: no wait
    w("GET", "u")  # second: throttled
    assert sleeps and sleeps[-1] == pytest.approx(30.0)


def test_backoff_honors_retry_after_then_succeeds():
    sleeps = []
    calls = {"n": 0}

    def transport(*a, **k):
        calls["n"] += 1
        return _Resp(200) if calls["n"] > 1 else _Resp(429, {"Retry-After": "2"})

    w = resilient(
        transport,
        retry=RetryPolicy(max_attempts=3),
        clock=lambda: 0.0,
        sleep=sleeps.append,
    )
    assert w("GET", "u").status_code == 200
    assert 2.0 in sleeps  # honored the Retry-After header, not the default backoff


def test_exponential_backoff_without_retry_after():
    sleeps = []
    calls = {"n": 0}

    def transport(*a, **k):
        calls["n"] += 1
        return _Resp(200) if calls["n"] > 2 else _Resp(503)

    w = resilient(
        transport,
        retry=RetryPolicy(max_attempts=4, base_delay_s=1.0),
        clock=lambda: 0.0,
        sleep=sleeps.append,
    )
    assert w("GET", "u").status_code == 200
    assert sleeps[:2] == [1.0, 2.0]  # 1*2^0, 1*2^1


def test_circuit_breaker_opens_and_fast_fails():
    n = {"calls": 0}

    def always_500(*a, **k):
        n["calls"] += 1
        return _Resp(500)

    w = resilient(
        always_500,
        retry=RetryPolicy(max_attempts=4, base_delay_s=0.0),
        breaker=BreakerPolicy(fail_threshold=3, reset_timeout_s=999),
        clock=lambda: 0.0,
        sleep=lambda s: None,
    )
    # first call: 4 failed attempts push the breaker open
    with pytest.raises(SourceUnavailable):
        w("GET", "u")
    opened_at = n["calls"]
    # subsequent call fast-fails WITHOUT touching the transport (that is the whole point)
    with pytest.raises(SourceUnavailable) as exc:
        w("GET", "u")
    assert n["calls"] == opened_at  # 0 transport invocations on the fast-fail
    assert "cooling down" in str(exc.value)  # the breaker path, not retry-exhaustion


def test_breaker_half_open_after_reset_timeout():
    t = {"now": 0.0}
    calls = {"n": 0}

    def transport(*a, **k):
        calls["n"] += 1
        # first burst fails; after the reset window a retry succeeds
        return _Resp(200) if t["now"] > 100 else _Resp(500)

    w = resilient(
        transport,
        retry=RetryPolicy(max_attempts=3, base_delay_s=0.0),
        breaker=BreakerPolicy(fail_threshold=2, reset_timeout_s=50),
        clock=lambda: t["now"],
        sleep=lambda s: None,
    )
    with pytest.raises(SourceUnavailable):
        w("GET", "u")  # opens the breaker
    t["now"] = (
        200  # past the reset window -> half-open trial allowed, transport now 200
    )
    assert w("GET", "u").status_code == 200


def test_daily_cap_raises():
    w = resilient(
        _ok_transport, rate={"per_day": 1}, clock=lambda: 0.0, sleep=lambda s: None
    )
    w("GET", "u")
    with pytest.raises(SourceUnavailable):
        w("GET", "u")


# --- #3 auto-wiring into the registry (post-v1) ----------------------------


def test_resilient_transport_wraps_external_only(monkeypatch):
    from foley.runtime import RuntimeConfig
    from foley.sources.registry import _resilient_transport

    ext = {"data_egress": "external", "rate": {"per_min": 60}}
    wrapped = _resilient_transport(ext)
    assert wrapped is not None and hasattr(wrapped, "reset")  # resilient wrapper
    assert _resilient_transport({"data_egress": "local"}) is None  # local -> untouched
    # http_resilience off -> not wrapped even for an external source
    monkeypatch.setattr(
        "foley.runtime.current_runtime", lambda: RuntimeConfig(http_resilience=False)
    )
    assert _resilient_transport(ext) is None


def test_load_adapter_auto_wraps_external_source_transport():
    from foley.sources.freesound.config import SOURCE_CONFIG
    from foley.sources.registry import _load_adapter

    adapter = _load_adapter("freesound", SOURCE_CONFIG)  # external live source
    # the adapter's transport is the throttle/backoff/breaker wrapper, not the bare default
    assert hasattr(adapter._http, "reset")
