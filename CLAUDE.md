# CLAUDE.md

Eval harness for an LLM document extraction pipeline. Traces every model call, scores outputs
against a labeled set with both code-based checks and a validated LLM judge, and gates CI on
regression.

## Status

Early. A full run works: every receipt in the eval set against every model, each call traced,
one row per call written to `results/`. On top of that there is a review surface for reading
those calls by hand and writing a note on each. Nothing is scored yet, so there is no accuracy
number here and no CI gate. This file grows as the repo does, so if something is missing here it
does not exist yet rather than being undocumented.

## Commands

- `uv sync` to install
- `uv run ruff check .` to lint
- `uv run pytest` to run the tests
- `uv run python scripts/trace_one_call.py` to send one receipt and print its trace URL
- `uv run python scripts/run_eval.py` for a full run. `--limit N` and `--models <id>...` cut it
  down, which is how to check a change without paying for the whole set.
- `uv run python scripts/review.py` to read a run's calls one at a time and note each one.
  Resumable, and filterable with `--models`, `--status`, `--receipts` and `--limit`.

## Layout

- `src/evalharness/`: the harness itself.
- `data/`: the eval set, committed so runs are reproducible. See `data/README.md`.
- `scripts/`: one-off runnable entry points, not library code.
- `tests/`: pytest suite.
- `results/`: generated eval runs and trace exports. Gitignored, regenerate rather than commit.
- `notes/`: hand-written notes on individual calls. Committed, unlike `results/`, because
  nothing regenerates them. See `notes/README.md`.

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
- `target.py` does not import langfuse. Tracing is the caller's job and lives in `tracing.py`,
  so the thing being measured stays independent of the thing measuring it.
- One model call is one trace. The trace is the unit you filter, score and annotate, and
  receipts are independent, so there is no sequence worth nesting. A run groups its traces by
  `run_id`, carried as the Langfuse session.
- A result row's `status` separates `invalid_output` (the model returned something the schema
  rejected, which is a result worth scoring) from `call_failed` (a rate limit or a 5xx, which
  says nothing about extraction quality). Do not collapse those two, it puts infrastructure
  noise into the failure counts.
- Notes on calls are free text, with no category or severity field. Failure categories are
  supposed to come out of reading the notes; a category field would mean fixing them before the
  reading, which finds only the failure modes you already expected.
- The comparison shown while reviewing is raw string equality, not normalised, and there is a
  test pinning that. Normalising encodes decisions about what counts as the same value, and
  while reading calls those decisions are the thing being discovered. Normalise when scoring.
- Reading order is receipt then model, so any prefix is balanced across models. The runner
  submits model by model, so file order would hand you one model's failure modes and nothing
  would say the others were missing.
- Never commit `.env`. It holds the Anthropic API key and the Langfuse keys.
- Eval outputs are generated artifacts. Do not commit them, and do not hand-edit a scored result
  to make a number look better.
