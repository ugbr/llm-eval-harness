"""Run the eval set through every model and write one row per call.

A run is the unit of work everything downstream hangs off. It gets an id, that id rides on every
trace as the session, and the rows written here carry it too, so a scored number can always be
traced back to the exact calls that produced it.

Rows are written as they finish rather than collected and dumped at the end. A run costs money
and takes minutes, and losing 140 completed calls to a crash on the 141st is not a tradeoff
worth making for a sorted file.
"""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from langfuse import Langfuse

from evalharness import dataset, target, tracing

MODELS = ("claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5")

# same cap the extraction side settled on. these calls are almost entirely network wait, so
# threads are the right tool and 8 stays well clear of the rate limits.
MAX_WORKERS = 8

RESULTS_DIR = Path(__file__).parents[2] / "results"


@dataclass(frozen=True)
class Call:
    """One unit of work: one receipt against one model."""

    receipt_id: str
    model: str


def new_run_id() -> str:
    """A sortable id for one invocation.

    Second resolution is plenty, since a run takes minutes. The point of the id is that it is
    explicit: five runs of the same 50 receipts against the same 3 models are otherwise
    indistinguishable, and telling them apart is the whole of the variance question.
    """
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _row(call: Call, run_id: str, traced: tracing.TracedExtraction) -> dict[str, Any]:
    e = traced.extraction
    return {
        "run_id": run_id,
        "receipt_id": call.receipt_id,
        "model": call.model,
        "trace_id": traced.trace_id,
        "target_version": target.TARGET_VERSION,
        # ok means the model returned something Receipt accepted. it says nothing yet about
        # whether the values are right, which is what scoring is for.
        "status": "invalid_output" if e.error else "ok",
        "error": e.error,
        "prediction": e.receipt.model_dump(mode="json") if e.receipt else None,
        "raw_output": e.raw_output,
        "stop_reason": e.stop_reason,
        "input_tokens": e.input_tokens,
        "output_tokens": e.output_tokens,
        "latency_s": round(e.latency_s, 3),
    }


def _failed_row(call: Call, run_id: str, exc: Exception) -> dict[str, Any]:
    """A call that never produced an output.

    Kept deliberately distinct from invalid_output. A rate limit or a 5xx says nothing about
    extraction quality, and folding the two together would put infrastructure noise straight
    into the failure counts.

    It still gets a trace_id where there is one. These are the rows you most want to open, so
    leaving them unable to point at their own trace was backwards.
    """
    return {
        "run_id": run_id,
        "receipt_id": call.receipt_id,
        "model": call.model,
        "trace_id": exc.trace_id if isinstance(exc, tracing.TracedCallFailed) else None,
        "target_version": target.TARGET_VERSION,
        "status": "call_failed",
        "error": f"{type(exc).__name__}: {exc}",
        "prediction": None,
        "raw_output": None,
        "stop_reason": None,
        "input_tokens": None,
        "output_tokens": None,
        "latency_s": None,
    }


def run(
    *,
    client: Anthropic,
    langfuse: Langfuse,
    run_id: str,
    models: tuple[str, ...] = MODELS,
    receipt_ids: list[str] | None = None,
    out_dir: Path = RESULTS_DIR,
) -> Path:
    """Every receipt against every model. Returns the path of the written file."""
    receipt_ids = receipt_ids if receipt_ids is not None else dataset.receipt_ids()
    calls = [Call(receipt_id=r, model=m) for m in models for r in receipt_ids]

    out_path = out_dir / f"{run_id}.jsonl"
    if out_path.exists():
        raise SystemExit(f"{out_path} already exists, refusing to overwrite a completed run")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{run_id}: {len(calls)} calls, {len(receipt_ids)} receipts x {len(models)} models")
    counts: Counter[str] = Counter()

    with out_path.open("w") as out, ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                tracing.traced_extract,
                text=dataset.load_ocr_text(call.receipt_id),
                client=client,
                model=call.model,
                receipt_id=call.receipt_id,
                run_id=run_id,
                langfuse=langfuse,
            ): call
            for call in calls
        }

        for done, future in enumerate(as_completed(futures), start=1):
            call = futures[future]
            try:
                row = _row(call, run_id, future.result())
            except Exception as exc:
                # isolation per call. one receipt going down must not cost us the other 149.
                row = _failed_row(call, run_id, exc)

            counts[row["status"]] += 1
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"  {done:>3}/{len(calls)} {call.model:<18} {call.receipt_id} {row['status']}")

    # the sdk ships spans in the background, so a script that exits here loses the tail of them
    langfuse.flush()

    print(f"\n{dict(counts)}\nwrote {out_path}")
    return out_path
