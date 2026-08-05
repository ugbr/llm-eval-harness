"""The review surface. Mostly a join, but two of its choices are load bearing."""

import json

import pytest

from evalharness import review


def _row(**overrides):
    row = {
        "run_id": "run-test",
        "receipt_id": "000",
        "model": "claude-haiku-4-5",
        "trace_id": "abc123",
        "target_version": "v2",
        "status": "ok",
        "error": None,
        "prediction": {
            "company": "BOOK TA .K (TAMAN DAYA) SDN BHD",
            "address": "NO.53 55,57 & 59, JALAN SAGU 18, TAMAN DAYA, 81100 JOHOR BAHRU, JOHOR.",
            "total": "9.00",
            "date": "2018-12-25",
        },
        "raw_output": "{}",
        "stop_reason": "end_turn",
        "input_tokens": 638,
        "output_tokens": 100,
        "latency_s": 2.467,
    }
    return row | overrides


def _item(**overrides):
    from evalharness import dataset

    row = _row(**overrides)
    return review.ReviewItem(
        row=row,
        truth=dataset.load_ground_truth()[row["receipt_id"]],
        ocr_text=dataset.load_ocr_text(row["receipt_id"]),
    )


def _write_run(tmp_path, rows, name="run-20260101T000000Z.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_comparison_is_raw_string_equality_not_normalised():
    """Pinned on purpose.

    The label writes 25/12/2018 and the target returns 2018-12-25. Both are the same day, and a
    normaliser would report a match. While reading traces that is the wrong answer: normalising
    encodes decisions about what counts as the same, and those decisions are what the reading is
    supposed to surface. Score with a normaliser later, read without one.
    """
    fields = dict((f, (t, p, ok)) for f, t, p, ok in review.compare(_item()))
    truth, predicted, ok = fields["date"]
    assert (truth, predicted) == ("25/12/2018", "2018-12-25")
    assert ok is False
    # and the field that genuinely does match still matches, so the check has teeth
    assert fields["total"][2] is True


def test_rejected_output_still_compares_every_field():
    """No prediction is not the same as no fields. All four still render, as misses."""
    result = review.compare(_item(status="invalid_output", prediction=None, error="total: boom"))
    assert len(result) == len(review.FIELDS)
    assert all(predicted is None and not ok for _, _, predicted, ok in result)


def test_reading_order_is_balanced_across_models(tmp_path):
    """The sampling guard.

    The runner submits model by model, so file order is three solid blocks. Reading the first N
    in that order gives one tier's failure modes and nothing says the others are missing. Any
    prefix of this order has to be balanced instead.
    """
    rows = [
        _row(receipt_id=r, model=m)
        for m in ("claude-opus-5", "claude-haiku-4-5", "claude-sonnet-5")
        for r in ("000", "001")
    ]
    items = review.load_items(_write_run(tmp_path, rows))

    assert [i.receipt_id for i in items] == ["000", "000", "000", "001", "001", "001"]
    # cheapest tier first inside a receipt, matching how the runner declares them
    assert [i.model for i in items[:3]] == list(review.runner.MODELS)


def test_trace_url_degrades_to_the_bare_id(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "https://jp.cloud.langfuse.com")
    monkeypatch.delenv("LANGFUSE_PROJECT_ID", raising=False)
    assert review.trace_url("abc123") == "abc123"

    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "proj1")
    assert review.trace_url("abc123").endswith("/project/proj1/traces/abc123")


def test_latest_results_file_picks_the_newest_run(tmp_path):
    _write_run(tmp_path, [_row()], name="run-20260101T000000Z.jsonl")
    newest = _write_run(tmp_path, [_row()], name="run-20260202T000000Z.jsonl")
    assert review.latest_results_file(tmp_path) == newest


def test_no_results_file_is_a_clear_exit(tmp_path):
    with pytest.raises(SystemExit):
        review.latest_results_file(tmp_path)
