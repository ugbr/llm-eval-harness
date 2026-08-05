"""Read a run's calls one at a time and write a note on each.

This is the error analysis surface. It renders one call as a screenful, waits for a note, appends
it, and moves on. Resumable: calls that already have a note are skipped, so this is meant to be
run across several sittings.

Notes are free text and stay free text. Resist writing categories here. Categories are supposed
to come out of reading these notes afterwards, and inventing them up front means you find the
failure modes you already expected.

Run:            uv run python scripts/review.py
One tier:       uv run python scripts/review.py --models claude-opus-5
Only rejects:   uv run python scripts/review.py --status invalid_output call_failed
Re-read one:    uv run python scripts/review.py --receipts 002 --redo
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from evalharness import notes, review

CLEAN = "."
SKIP = "s"
QUIT = "q"

# what the fast path writes. a fixed sentence rather than a boolean field, so the notes file
# stays one shape: free text, all the way down.
CLEAN_NOTE = "matches ground truth on all four fields"

PROMPT = f"note ({CLEAN}=clean, {SKIP}=skip, {QUIT}=quit) > "


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, help="results file, defaults to the latest run")
    parser.add_argument("--models", nargs="+", help="only these models")
    parser.add_argument("--status", nargs="+", help="only these statuses")
    parser.add_argument("--receipts", nargs="+", help="only these receipt ids")
    parser.add_argument("--limit", type=int, help="stop after N calls")
    parser.add_argument(
        "--redo",
        action="store_true",
        help="include calls that already have a note. the old note is kept, not overwritten",
    )
    args = parser.parse_args()

    # only for LANGFUSE_HOST and the optional LANGFUSE_PROJECT_ID, which turn a trace id into a
    # clickable link. nothing here calls an api.
    load_dotenv()

    results_path = args.results or review.latest_results_file()
    items = review.load_items(results_path)
    run_id = items[0].row["run_id"]

    if args.models:
        items = [i for i in items if i.model in set(args.models)]
    if args.status:
        items = [i for i in items if i.status in set(args.status)]
    if args.receipts:
        items = [i for i in items if i.receipt_id in set(args.receipts)]

    done = notes.current(run_id)
    queue = items if args.redo else [i for i in items if i.key not in done]
    if args.limit:
        queue = queue[: args.limit]

    print(f"{results_path.name}: {len(items)} calls in scope, {len(done)} already noted")
    if not queue:
        print("nothing left to read")
        return
    print(f"reading {len(queue)}. notes go to {notes.notes_path(run_id)}\n")

    for n, item in enumerate(queue, start=1):
        print(review.render(item))
        matches = all(ok for *_, ok in review.compare(item))
        print(f"\n[{n}/{len(queue)}]  {'all four fields match' if matches else ''}")

        text = _ask(matches)
        if text is None:
            print(f"\nstopped at {n - 1} of {len(queue)}. run again to pick up where you left off.")
            return

        if text:
            notes.write(run_id=run_id, receipt_id=item.receipt_id, model=item.model, text=text)
        else:
            print("  skipped, no note written")
        print()

    print(f"done. {len(notes.current(run_id))} calls noted in {notes.notes_path(run_id)}")


def _ask(matches: bool) -> str | None:
    """The note for one call. Empty string means skip, None means quit.

    A bare enter is rejected rather than treated as clean. Blank is the easiest thing to hit by
    accident and "I read this and it was fine" is a real claim about the data, so it has to be
    typed on purpose.
    """
    while True:
        try:
            answer = input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if answer == QUIT:
            return None
        if answer == SKIP:
            return ""
        if answer == CLEAN:
            # the fast path only exists for calls that are actually clean. offering it on a
            # mismatched row would let one keystroke record something the screen contradicts.
            if matches:
                return CLEAN_NOTE
            print("  not a clean call, some field disagrees. say what you see.")
            continue
        if answer:
            return answer
        print("  say something, or s to skip and q to quit.")


if __name__ == "__main__":
    main()
