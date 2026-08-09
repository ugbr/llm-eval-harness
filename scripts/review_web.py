"""Read a run's calls in a browser and write a note on each.

Same job as scripts/review.py and the same notes file, so the two are interchangeable and you can
switch mid-run. This one is easier on a long receipt, because the OCR text and the field
comparison sit side by side instead of stacked, and the text is selectable.

Run:            uv run python scripts/review_web.py
One tier:       uv run python scripts/review_web.py --models claude-haiku-4-5
Only rejects:   uv run python scripts/review_web.py --status invalid_output call_failed

Binds to localhost. There is no auth and none is wanted, so leave it there.
"""

import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from evalharness import review, webapp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, help="results file, defaults to the latest run")
    parser.add_argument("--models", nargs="+", help="only these models")
    parser.add_argument("--status", nargs="+", help="only these statuses")
    parser.add_argument("--receipts", nargs="+", help="only these receipt ids")
    parser.add_argument("--limit", type=int, help="only the first N calls")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    # only for LANGFUSE_HOST and the optional LANGFUSE_PROJECT_ID, which turn a trace id into a
    # clickable link. nothing here calls an api.
    load_dotenv()

    results_path = args.results or review.latest_results_file()
    app = webapp.create_app(
        results_path,
        models=args.models,
        statuses=args.status,
        receipts=args.receipts,
        limit=args.limit,
    )

    print(f"{results_path.name} on http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
