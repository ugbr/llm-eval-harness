# CLAUDE.md

Eval harness for an LLM document extraction pipeline. Traces every model call, scores outputs
against a labeled set with both code-based checks and a validated LLM judge, and gates CI on
regression.

## Status

Early. The eval set is vendored, the extraction target runs against it, and one traced call
works end to end with tokens, latency and cost. Nothing is scored yet, and the full run is not
wired up. This file grows as the repo does, so if something is missing here it does not exist
yet rather than being undocumented.

## Commands

- `uv sync` to install
- `uv run ruff check .` to lint
- `uv run pytest` to run the tests
- `uv run python scripts/trace_one_call.py` to send one receipt and print its trace URL

## Layout

- `src/evalharness/`: the harness itself.
- `data/`: the eval set, committed so runs are reproducible. See `data/README.md`.
- `scripts/`: one-off runnable entry points, not library code.
- `tests/`: pytest suite.
- `results/`: generated eval runs and trace exports. Gitignored, regenerate rather than commit.

Copy `.env.example` to `.env` and fill it before running anything.

## Conventions

- Python via uv. `uv add <pkg>` to add a dependency, `uv sync` after editing deps by hand. The
  lockfile is committed.
- Dependencies get added at the point they are actually needed, not up front.
- src layout, tests in `tests/`.
- Keep lint and tests green before committing.
- The system under test lives behind one interface in `target.py`. It reports the exact prompt
  and the raw output, including when validation fails, because a failure you cannot read is a
  failure you cannot categorise. Keep that contract if you swap the implementation.
- Never commit `.env`. It holds the Anthropic API key and the Langfuse keys.
- Eval outputs are generated artifacts. Do not commit them, and do not hand-edit a scored result
  to make a number look better.
