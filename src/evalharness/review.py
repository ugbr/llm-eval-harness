"""Put one call on screen: what the model saw, what it answered, what the answer was.

A results row on its own is not readable. It has the prediction and the trace id but not the
label and not the input, and judging an extraction without those two is guesswork. This joins the
three and renders them as one screenful.

Comparison here is raw string equality, deliberately not normalised. A normaliser encodes
decisions someone already made about what counts as the same value, and while you are reading
traces those decisions are exactly what you are trying to discover. So every date shows as a
mismatch (25/12/2018 vs 2018-12-25) and that is correct: it is a real difference, and whether it
matters is a call to be made later and written down when it is.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evalharness import dataset, runner

RESULTS_DIR = Path(__file__).parents[2] / "results"

FIELDS = ("company", "address", "date", "total")


@dataclass(frozen=True)
class ReviewItem:
    """One call, with everything needed to judge it.

    truth and prediction are plain dicts of field to string. prediction is None when the model
    returned something the schema rejected, or when the call never came back at all, which is
    why raw_output and error are carried alongside rather than folded in.
    """

    row: dict[str, Any]
    truth: dict[str, Any]
    ocr_text: str

    @property
    def receipt_id(self) -> str:
        return self.row["receipt_id"]

    @property
    def model(self) -> str:
        return self.row["model"]

    @property
    def status(self) -> str:
        return self.row["status"]

    @property
    def key(self) -> tuple[str, str, str]:
        """What identifies this call across runs and files: run, receipt, model."""
        return (self.row["run_id"], self.receipt_id, self.model)


def latest_results_file(results_dir: Path = RESULTS_DIR) -> Path:
    """The most recent run. Run ids sort chronologically, which is what they were built for."""
    files = sorted(results_dir.glob("run-*.jsonl"))
    if not files:
        raise SystemExit(f"no run-*.jsonl in {results_dir}, run scripts/run_eval.py first")
    return files[-1]


def load_items(results_path: Path) -> list[ReviewItem]:
    """Every call in a run, joined to its label and its input.

    Sorted by receipt then model, and that ordering is a sampling decision, not cosmetics. The
    runner submits model by model, so a run's rows arrive in three blocks and the first 50 of
    anything in submission order are one model's. Read those and you get one tier's failure
    modes with nothing to tell you the other two are missing. Sorted this way, any prefix you
    stop at is balanced across all three.
    """
    truth = dataset.load_ground_truth()
    with results_path.open() as f:
        rows = [json.loads(line) for line in f if line.strip()]

    items = [
        ReviewItem(
            row=row,
            truth=truth[row["receipt_id"]],
            ocr_text=dataset.load_ocr_text(row["receipt_id"]),
        )
        for row in rows
    ]
    return sorted(items, key=lambda i: (i.receipt_id, _model_order(i.model)))


def _model_order(model: str) -> tuple[int, str]:
    """Cheapest tier first, matching the order the runner declares them.

    Falls back to alphabetical for a model not in that list, so an ad hoc run of something else
    still sorts stably instead of blowing up.
    """
    known = list(runner.MODELS)
    return (known.index(model), "") if model in known else (len(known), model)


def compare(item: ReviewItem) -> list[tuple[str, str, str | None, bool]]:
    """Field by field: name, truth, prediction, whether they are the same string.

    Returns prediction None for every field when there is no prediction at all, so a rejected
    output still renders as four rows rather than vanishing.
    """
    pred = item.row.get("prediction") or {}
    out = []
    for field in FIELDS:
        truth = str(item.truth.get(field, ""))
        predicted = pred.get(field)
        predicted = None if predicted is None else str(predicted)
        out.append((field, truth, predicted, predicted == truth))
    return out


def trace_url(trace_id: str | None) -> str:
    """A clickable link when the project id is known, the bare id otherwise.

    The id alone is enough to find a trace by hand, so a missing LANGFUSE_PROJECT_ID degrades
    rather than blocking the whole review.
    """
    if not trace_id:
        return "(no trace)"
    host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
    project = os.environ.get("LANGFUSE_PROJECT_ID", "")
    if host and project:
        return f"{host}/project/{project}/traces/{trace_id}"
    return trace_id


def render(item: ReviewItem, *, width: int = 88) -> str:
    """One call as a screenful, in reading order: input, then answer vs truth, then the call."""
    rule = "-" * width
    lines = [
        rule,
        f"receipt {item.receipt_id}   {item.model}   {item.status}   {item.row['run_id']}",
        rule,
        "",
        "OCR INPUT",
        *(f"  {line}" for line in item.ocr_text.splitlines()),
        "",
        "FIELDS",
    ]

    for field, truth, predicted, ok in compare(item):
        if ok:
            lines.append(f"  {field:<8} =  {truth}")
        else:
            lines.append(f"  {field:<8} !  truth      {truth}")
            lines.append(f"  {'':<8}    predicted  {'(none)' if predicted is None else predicted}")

    if item.row.get("error"):
        lines += ["", "ERROR", f"  {item.row['error']}"]
    # the raw text is the evidence for anything the schema rejected, so it only earns screen
    # space when there is no parsed prediction to look at instead.
    if item.row.get("prediction") is None and item.row.get("raw_output"):
        lines += ["", "RAW OUTPUT", f"  {item.row['raw_output']}"]

    lines += ["", f"trace  {trace_url(item.row.get('trace_id'))}"]
    return "\n".join(lines)
