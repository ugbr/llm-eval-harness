# CLAUDE.md

Eval harness for an LLM document extraction pipeline. Traces every model call, scores outputs
against a labeled set with both code-based checks and a validated LLM judge, and gates CI on
regression.

## Status

Early. One traced call works end to end: a receipt goes to the model, the call lands in Langfuse
with tokens, latency and cost. Nothing is scored yet. This file grows as the repo does, so if
something is missing here it does not exist yet rather than being undocumented.

## Commands

- `uv sync` to install
- `uv run ruff check .` to lint
- `uv run python scripts/trace_one_call.py` to send one receipt and print its trace URL

## Layout

- `src/evalharness/`: the harness itself.
- `scripts/`: one-off runnable entry points, not library code.
- `results/`: generated eval runs and trace exports. Gitignored, regenerate rather than commit.

Copy `.env.example` to `.env` and fill it before running anything.

## Conventions

- Python via uv. `uv add <pkg>` to add a dependency, `uv sync` after editing deps by hand. The
  lockfile is committed.
- Dependencies get added at the point they are actually needed, not up front.
- src layout, tests in `tests/`.
- Keep lint and tests green before committing.
- Never commit `.env`. It holds the Anthropic API key and the Langfuse keys.
- Eval outputs are generated artifacts. Do not commit them, and do not hand-edit a scored result
  to make a number look better.
