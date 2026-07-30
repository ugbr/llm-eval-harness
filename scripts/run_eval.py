"""Run the eval set and write the results file.

This is the part that costs money, so it is kept separate from anything that reads the results.
Scoring is free and repeatable, and should never require paying for the calls again.

Run: uv run python scripts/run_eval.py
Cheap check first: uv run python scripts/run_eval.py --limit 2 --models claude-haiku-4-5
"""

import argparse

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

from evalharness import dataset, runner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(runner.MODELS))
    parser.add_argument("--limit", type=int, help="first N receipts only, for a cheap check")
    parser.add_argument("--run-id", help="defaults to a timestamp")
    args = parser.parse_args()

    load_dotenv()

    langfuse = Langfuse()
    if not langfuse.auth_check():
        raise SystemExit("langfuse auth failed, check LANGFUSE_* in .env")

    # the sdk already retries 429s and 5xx twice with backoff. a 150 call batch is long enough
    # that two is not always enough, and a call lost to a transient 529 is a hole in the
    # denominator rather than a result. it still gives up eventually, and when it does the row
    # says call_failed rather than quietly not existing.
    runner.run(
        client=Anthropic(max_retries=5),
        langfuse=langfuse,
        run_id=args.run_id or runner.new_run_id(),
        models=tuple(args.models),
        receipt_ids=dataset.receipt_ids()[: args.limit] if args.limit else None,
    )


if __name__ == "__main__":
    main()
