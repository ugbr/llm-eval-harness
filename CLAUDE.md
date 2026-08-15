# CLAUDE.md

Eval harness for an LLM document extraction pipeline. Traces every model call, scores outputs
against a labeled set with both code-based checks and a validated LLM judge, and gates CI on
regression.

## Status

Early. A full run works: every receipt in the eval set against every model, each call traced,
one row per call written to `results/`. On top of that there are two review surfaces, a terminal
one and a local web one, for reading those calls by hand and writing a note on each. Nothing is
scored automatically yet and there is no CI gate. There are accuracy numbers, but they live in
`docs/failure-taxonomy.md` and were derived by hand from one model's calls. This file grows as
the repo does, so if something is missing here it does not exist yet rather than being
undocumented.

## Commands

- `uv sync` to install
- `uv run ruff check .` to lint
- `uv run pytest` to run the tests
- `uv run python scripts/trace_one_call.py` to send one receipt and print its trace URL
- `uv run python scripts/run_eval.py` for a full run. `--limit N` and `--models <id>...` cut it
  down, which is how to check a change without paying for the whole set.
- `uv run python scripts/review.py` to read a run's calls one at a time and note each one.
  Resumable, and filterable with `--models`, `--status`, `--receipts` and `--limit`.
- `uv run python scripts/review_web.py` for the same thing in a browser, on
  http://127.0.0.1:8765. Same filters, same notes file. Easier on a long receipt, because the
  input and the field comparison sit side by side and the text is selectable.

## Layout

- `src/evalharness/`: the harness itself.
- `data/`: the eval set, committed so runs are reproducible. See `data/README.md`.
- `scripts/`: one-off runnable entry points, not library code.
- `tests/`: pytest suite.
- `results/`: generated eval runs and trace exports. Gitignored, regenerate rather than commit.
- `notes/`: hand-written notes on individual calls. Committed, unlike `results/`, because
  nothing regenerates them. See `notes/README.md`.
- `docs/`: findings written up from the runs. Currently the failure taxonomy, which is what the
  scoring work is built against.

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
- The artifact/real/ceiling grouping in `docs/failure-taxonomy.md` is the normalisation spec, not
  commentary. Which group a mode sits in decides whether the normaliser erases it, and that moved
  the pass rate by 14 points on one mode alone. Change a grouping and you have changed the
  accuracy number, so change it deliberately and say why.
- The two review surfaces are views over `review.py` and `notes.py` and hold no state of their
  own. Adding a third should mean one new module and no changes to those two. If that stops
  being true, the seam has moved and it is worth asking why before working around it.
- Both surfaces write the same fixed sentence for a call that matches on all four fields, and
  a test pins the string. They feed one notes file that gets read and clustered by hand, so two
  spellings of the same observation would silently split a count in half.
- That shortcut currently cannot fire, and that is expected rather than broken. The comparison
  is unnormalised, so a date always differs in format and no call matches on all four fields.
  It becomes reachable again if normalisation ever moves into the reading surface, which is a
  decision, not a cleanup.
- Reading order is receipt then model, so any prefix is balanced across models. The runner
  submits model by model, so file order would hand you one model's failure modes and nothing
  would say the others were missing.
- Never commit `.env`. It holds the Anthropic API key and the Langfuse keys.
- Eval outputs are generated artifacts. Do not commit them, and do not hand-edit a scored result
  to make a number look better.
