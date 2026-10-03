# foley.cli

The `foley` command-line interface (stdlib `argparse`, zero new deps).

Subcommands:

```default
foley demo                       # offline ingest->search over the bundled fixture
foley bootstrap [--rings 0,1] [--corpora fsd50k,foleyset] [--data-dir DIR]
                [--accept-ai-restricted] [--no-commercial-filter]
foley ingest PATH [--license ID] [--min-status warn|pass|fail] [--no-qc]
foley search QUERY [-k N] [--commercial-ok]
```

Wired as the `foley` console entry point (`[project.scripts]`). Every command
is a thin call into the library facade ([`foley.bootstrap()`](foley.md#foley.bootstrap), [`foley.demo()`](foley.md#foley.demo),
[`foley.ingest()`](foley.md#foley.ingest), [`foley.search()`](foley.md#foley.search)); the CLI only parses args and prints.

### Functions

| [`build_parser`](#foley.cli.build_parser)()   | Build the `foley` argument parser.          |
|-------------------------------------------------------------------|---------------------------------------------|
| [`main`](#foley.cli.main)([argv])     | Entry point for the `foley` console script. |

### foley.cli.build_parser()

Build the `foley` argument parser.

* **Return type:**
  [`ArgumentParser`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser)

### foley.cli.main(argv=None)

Entry point for the `foley` console script.

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)
