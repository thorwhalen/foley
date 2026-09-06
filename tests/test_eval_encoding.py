"""The eval/bootstrap JSON fixtures are UTF-8 on read AND write, not locale-flavoured.

``foley`` writes its golden seed / corpus manifest / baseline as UTF-8 (``json``
defaults, ``Path.write_text(..., encoding="utf-8")``) and the ingest-side readers
are already explicit about it (see ``foley/sources/clotho.py`` for the rationale).
The eval loaders must match: a bare ``Path(...).read_text()`` decodes with the
*process locale*, so the same committed fixture reads as UTF-8 on macOS/Linux and
as cp1252 on a stock Windows console — silently mojibaking a non-ASCII caption, or
raising ``UnicodeDecodeError`` under an ASCII locale.

Two layers, both out-of-process because both need interpreter *start-up* flags:

1. a lint-level probe (``PYTHONWARNDEFAULTENCODING=1``) asserting no
   ``EncodingWarning`` is raised from inside the ``foley`` package;
2. a behavioural probe under a forced non-UTF-8 locale asserting a non-ASCII
   caption round-trips byte-exactly.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")

#: ``tests/`` — the child processes import ``conftest.FakeEmbedder`` from here.
_TESTS_DIR = Path(__file__).resolve().parent

#: A caption that is valid UTF-8 and undecodable as ASCII (and mojibake in cp1252).
NON_ASCII_CAPTION = "café ambience, naïve doorbell"


def _fixture_payloads() -> "dict[str, str]":
    """The JSON texts the child writes as UTF-8 before reading them back.

    Returns:
        ``{"seed": ..., "corpus": ...}`` — one golden item and one corpus clip,
        both carrying :data:`NON_ASCII_CAPTION`.
    """
    seed = [
        {
            "id": "gld-encoding-1",
            "context": NON_ASCII_CAPTION,
            "expected_events": [{"query": "ambience", "clip_id": "ring0:cafe"}],
            "answer_clip_ids": {"ambience": ["ring0:cafe"]},
            "grade": {"ring0:cafe": 3},
        }
    ]
    corpus = [
        {
            "file": "cafe.wav",
            "caption": NON_ASCII_CAPTION,
            "tags": ["cafe", "ambience"],
            "ucs_catid": "AMBIance",
        }
    ]

    # ensure_ascii=False so the bytes on disk are genuinely UTF-8 (not \uXXXX
    # escapes, which would decode identically under any ASCII-superset locale
    # and so could not expose the bug).
    def dump(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    return {"seed": dump(seed), "corpus": dump(corpus)}


def _run_child(script: str, *, tmp_path, env_overrides, extra_args=()) -> tuple:
    """Write the UTF-8 fixtures into ``tmp_path`` and run ``script`` out-of-process.

    Args:
        script: The ``python -c`` body.
        tmp_path: Directory the fixtures are written into (also ``argv[1]``).
        env_overrides: Environment entries layered onto the parent's; a ``None``
            value *unsets* the variable (an empty string is not portable).
        extra_args: Interpreter flags inserted before ``-c``.

    Returns:
        The finished :class:`subprocess.CompletedProcess`-style ``(rc, out, err)``.
    """
    payloads = _fixture_payloads()
    (tmp_path / "seed.json").write_text(payloads["seed"], encoding="utf-8")
    (tmp_path / "corpus.json").write_text(payloads["corpus"], encoding="utf-8")
    env = {**os.environ, **env_overrides}
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
    proc = subprocess.run(
        [sys.executable, *extra_args, "-c", script, str(tmp_path), str(_TESTS_DIR)],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# 1. no implicit-locale decode anywhere in the package (the lint-level probe)
# ---------------------------------------------------------------------------

_WARN_PROBE = r"""
import json, sys, warnings
from pathlib import Path
from types import SimpleNamespace

tmp, tests_dir = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, tests_dir)

import foley
from foley.bootstrap import demo
from foley.eval.baseline import load_baseline, write_baseline
from foley.eval.golden import build_eval_library, load_golden

foley_dir = str(Path(foley.__file__).resolve().parent)
seed, corpus = tmp / "seed.json", tmp / "corpus.json"
baseline = tmp / "baseline.json"

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    items = load_golden(seed)
    build_eval_library(manifest_path=corpus)
    write_baseline(
        SimpleNamespace(mean={"ndcg@10": 0.5}),
        path=baseline,
        seed_path=seed,
        manifest_path=corpus,
        updated_at="2026-01-01T00:00:00Z",
        n_items=len(items),
    )
    load_baseline(baseline)
    from conftest import FakeEmbedder
    from foley.bootstrap import _fresh_memory_library

    demo(library=_fresh_memory_library(embedder=FakeEmbedder()), query="rain window", k=3)

offenders = [
    "{}:{} {}".format(w.filename, w.lineno, w.message)
    for w in caught
    if issubclass(w.category, EncodingWarning) and w.filename.startswith(foley_dir)
]
print("\n".join(offenders))
sys.exit(1 if offenders else 0)
"""


def test_no_implicit_locale_encoding_inside_foley(tmp_path):
    """Every text read/write the eval + bootstrap paths make declares an encoding."""
    pytest.importorskip("soundfile")
    rc, out, err = _run_child(
        _WARN_PROBE,
        tmp_path=tmp_path,
        env_overrides={"PYTHONWARNDEFAULTENCODING": "1"},
    )
    assert rc == 0, f"EncodingWarning(s) raised inside foley:\n{out}\n{err}"


# ---------------------------------------------------------------------------
# 2. a non-ASCII caption survives a non-UTF-8 locale (the behavioural probe)
# ---------------------------------------------------------------------------

# NOTE: this source is handed to the child as a `-c` argument, which the child decodes
# with its (deliberately non-UTF-8) locale — so the probe must stay pure ASCII. The
# caption is therefore spliced in backslash-escaped rather than written out literally.
_LOCALE_PROBE = r"""
import locale, sys
from pathlib import Path

if locale.getpreferredencoding(False).lower().replace("-", "").replace("_", "") == "utf8":
    print("SKIP")
    sys.exit(0)

tmp = Path(sys.argv[1])
expected = "__CAPTION__"

from foley.eval.golden import build_eval_library, load_golden

item = load_golden(tmp / "seed.json")[0]
assert item.context == expected, "golden context mojibaked: " + ascii(item.context)
lib = build_eval_library(manifest_path=tmp / "corpus.json")
caption = lib.get("ring0:cafe").caption
assert caption == expected, "corpus caption mojibaked: " + ascii(caption)
print("OK")
""".replace(
    "__CAPTION__", NON_ASCII_CAPTION.encode("ascii", "backslashreplace").decode()
)


def test_non_ascii_fixtures_round_trip_under_non_utf8_locale(tmp_path):
    """A UTF-8 fixture read under a cp1252/ASCII locale must not mojibake or raise."""
    rc, out, err = _run_child(
        _LOCALE_PROBE,
        tmp_path=tmp_path,
        env_overrides={
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONUTF8": "0",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONWARNDEFAULTENCODING": None,
        },
        extra_args=("-X", "utf8=0"),
    )
    if "SKIP" in out:
        pytest.skip("could not force a non-UTF-8 locale on this platform")
    assert rc == 0, f"non-ASCII fixture did not survive the locale:\n{out}\n{err}"
