# notes/

One free-text note per model call, written by hand while reading the call on screen.

`notes-<run_id>.jsonl`, one file per run, one JSON object per line:

```json
{"run_id": "...", "receipt_id": "002", "model": "claude-sonnet-5", "text": "...", "noted_at": "..."}
```

Written by `scripts/review.py`. Append only, so re-reading a call adds a line instead of
replacing one and the earlier read stays on the record. Reads take the last line for a given
run + receipt + model.

Two things about this directory are deliberate.

**It is committed, unlike `results/`.** Everything in `results/` comes back by paying for another
run. A note is somebody having read a receipt and written down what they saw, and there is no
command that regenerates that.

**The notes are free text, with no category, severity or tag field.** Failure categories are
meant to fall out of reading these afterwards. A category field would mean fixing the categories
before doing the reading, which finds you the failure modes you already expected and hides the
ones you did not.
