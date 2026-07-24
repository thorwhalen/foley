"""The ``foley`` command-line interface (stdlib ``argparse``, zero new deps).

Subcommands::

    foley demo                       # offline ingest->search over the bundled fixture
    foley bootstrap [--rings 0,1] [--corpora fsd50k,foleyset] [--data-dir DIR]
                    [--accept-ai-restricted] [--no-commercial-filter]
    foley ingest PATH [--license ID] [--min-status warn|pass|fail] [--no-qc]
    foley search QUERY [-k N] [--commercial-ok]

Wired as the ``foley`` console entry point (``[project.scripts]``). Every command
is a thin call into the library facade (:func:`foley.bootstrap`, :func:`foley.demo`,
:func:`foley.ingest`, :func:`foley.search`); the CLI only parses args and prints.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def _int_csv(value: str) -> "tuple[int, ...]":
    """Parse ``"0,1"`` -> ``(0, 1)``."""
    return tuple(int(x) for x in value.split(",") if x.strip() != "")


def _str_csv(value: str) -> "list[str]":
    """Parse ``"fsd50k,foleyset"`` -> ``["fsd50k", "foleyset"]``."""
    return [x.strip() for x in value.split(",") if x.strip() != ""]


def _cmd_demo(args) -> int:
    from . import demo

    result = demo(query=args.query, k=args.k)
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cmd_bootstrap(args) -> int:
    from . import bootstrap
    from .sources.base import CORPUS_REGISTRY

    corpora = _str_csv(args.corpora) if args.corpora else None
    rings = _int_csv(args.rings) if args.rings else (0, 1)

    if args.accept_ai_restricted:
        restricted = sorted(
            n
            for n, a in CORPUS_REGISTRY.items()
            if a.ring == 2 and (corpora is None or n in corpora)
        )
        print(
            "CONSENT: --accept-ai-restricted admits AI-training-restricted corpora "
            f"({', '.join(restricted) or 'none selected'}); their licenses forbid "
            "using the audio to train models. Proceeding with recorded consent.",
            file=sys.stderr,
        )

    commercial_only = False if args.no_commercial_filter else None
    reports = bootstrap(
        rings=rings,
        corpora=corpora,
        data_dir=args.data_dir,
        accept_ai_restricted=args.accept_ai_restricted,
        commercial_only=commercial_only,
    )
    for name, report in reports.items():
        print(f"{name}: {json.dumps(report.summary())}")
    return 0


def _cmd_ingest(args) -> int:
    from . import ingest
    from .base import LicenseRecord
    from .licensing import apply_license_flags
    from .qc import QCStatus

    license_record = None
    if args.license:
        license_record = apply_license_flags(
            LicenseRecord(source="cli", license_id=args.license, rights_verified=True)
        )
    report = ingest(
        args.path,
        license=license_record,
        qc=not args.no_qc,  # the facade maps qc -> ingest_one's do_qc
        min_status=QCStatus(args.min_status),
    )
    print(json.dumps(report.summary(), indent=2))
    return 0


def _cmd_search(args) -> int:
    from . import search

    hits = search(args.query, k=args.k, commercial_ok=args.commercial_ok or None)
    for hit in hits:
        rec = hit.sound
        print(f"{rec.id[:12]}  {rec.caption or '(no caption)'}  [{rec.license.license_id}]")
    if not hits:
        print("(no hits)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the ``foley`` argument parser."""
    parser = argparse.ArgumentParser(prog="foley", description="foley — sound-effects retrieval facade")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="offline ingest->search over the bundled fixture")
    p_demo.add_argument("--query", default="rain on a window")
    p_demo.add_argument("-k", type=int, default=3)
    p_demo.set_defaults(func=_cmd_demo)

    p_boot = sub.add_parser("bootstrap", help="seed the library from bulk corpora")
    p_boot.add_argument("--rings", help="comma-separated rings (default 0,1)")
    p_boot.add_argument("--corpora", help="comma-separated corpus names (overrides --rings)")
    p_boot.add_argument("--data-dir", help="root holding downloaded corpora (data_dir/<name>)")
    p_boot.add_argument(
        "--accept-ai-restricted",
        action="store_true",
        help="consent to admit Ring-2 AI-training-restricted corpora (Sonniss, BBC RemArc)",
    )
    p_boot.add_argument(
        "--no-commercial-filter",
        action="store_true",
        help="do not drop non-commercial clips (personal-use ingest)",
    )
    p_boot.set_defaults(func=_cmd_bootstrap)

    p_ing = sub.add_parser("ingest", help="ingest a local folder or file")
    p_ing.add_argument("path")
    p_ing.add_argument("--license", help="license_id to stamp (default: user-owned)")
    p_ing.add_argument("--min-status", default="warn", choices=["fail", "warn", "pass"])
    p_ing.add_argument("--no-qc", action="store_true")
    p_ing.set_defaults(func=_cmd_ingest)

    p_search = sub.add_parser("search", help="hybrid search of the default library")
    p_search.add_argument("query")
    p_search.add_argument("-k", type=int, default=10)
    p_search.add_argument("--commercial-ok", action="store_true", help="keep only commercially-usable sounds")
    p_search.set_defaults(func=_cmd_search)

    return parser


#: Map an optional dependency's import name to the ``foley[extra]`` that ships it.
_MODULE_TO_EXTRA = {
    "numpy": "audio",
    "soundfile": "audio",
    "soxr": "audio",
    "librosa": "audio",
    "pyloudnorm": "audio",
    "torch": "clap",
    "transformers": "clap",
    "torchaudio": "caption",
    "lancedb": "index",
    "sqlite_vec": "index-sqlite",
    "panns_inference": "tag",
}


def _missing_dep_hint(exc: ImportError) -> str:
    """A check_requirements-style install hint for a missing optional dependency."""
    module = (getattr(exc, "name", "") or "").split(".")[0]
    extra = _MODULE_TO_EXTRA.get(module)
    if extra:
        return (
            f"foley needs the optional dependency {module!r} for this command. "
            f"Install it with:  pip install 'foley[{extra}]'  "
            "(the CLAP model downloads on first use)."
        )
    return (
        f"foley could not import {module or 'a required module'!r}. "
        "Install the relevant extra, e.g. pip install 'foley[audio,clap]'."
    )


def main(argv: "Optional[list[str]]" = None) -> int:
    """Entry point for the ``foley`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ImportError as exc:  # heavy optional dep not installed — guide, don't dump
        print(_missing_dep_hint(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
