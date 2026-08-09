"""The browser review surface.

Two surfaces write to one notes file, so most of what matters here is that this one agrees with
the terminal one about what a note is and when a call counts as clean.
"""

import json

import pytest
from fastapi.testclient import TestClient

from evalharness import dataset, notes, webapp

MODEL = "claude-haiku-4-5"


def _row(receipt_id, prediction, **overrides):
    row = {
        "run_id": "run-test",
        "receipt_id": receipt_id,
        "model": MODEL,
        "trace_id": "abc123",
        "target_version": "v2",
        "status": "ok",
        "error": None,
        "prediction": prediction,
        "raw_output": "{}",
        "stop_reason": "end_turn",
        "input_tokens": 638,
        "output_tokens": 100,
        "latency_s": 2.467,
    }
    return row | overrides


def _clean_row(receipt_id):
    """A call that matches its label on all four fields, built from the label itself."""
    truth = dataset.load_ground_truth()[receipt_id]
    return _row(receipt_id, {f: str(truth[f]) for f in ("company", "address", "date", "total")})


def _messy_row(receipt_id):
    """A call that disagrees on at least one field."""
    return _row(receipt_id, {"company": "WRONG", "address": "WRONG", "date": "x", "total": "0.00"})


@pytest.fixture
def client(tmp_path):
    rows = [_messy_row("000"), _clean_row("001")]
    results = tmp_path / "run-20260101T000000Z.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in rows))
    app = webapp.create_app(results, notes_dir=tmp_path / "notes")
    client = TestClient(app, follow_redirects=False)
    client.notes_dir = tmp_path / "notes"
    return client


def test_list_shows_every_call_in_scope(client):
    body = client.get("/").text
    assert "000" in body
    assert "001" in body
    assert "0 of 2 read" in body
    assert "not read" in body


def test_detail_shows_the_input_and_both_sides_of_every_field(client):
    body = client.get(f"/call/000/{MODEL}").text
    # the OCR text is the evidence for input error, so it has to be on the page rather than a
    # link away. this is the line the label silently corrected to BHD.
    assert "SDN BND" in body
    assert "WRONG" in body
    assert dataset.load_ground_truth()["000"]["company"] in body


def test_a_note_lands_in_the_same_file_the_terminal_surface_writes(client):
    client.post(f"/call/000/{MODEL}", data={"text": "copied BND straight from the OCR"})

    written = notes.load_all("run-test", client.notes_dir)
    assert len(written) == 1
    assert written[0].key == ("run-test", "000", MODEL)
    assert written[0].text == "copied BND straight from the OCR"


def test_the_clean_shortcut_is_refused_when_a_field_disagrees(client):
    """Pinned, and the terminal surface has the same guard.

    The button is one click and the fixed sentence is a real claim about the data. Letting it
    through on a call the page shows as mismatched would put a note in the file that the screen
    directly contradicts.
    """
    response = client.post(f"/call/000/{MODEL}", data={"clean": "1"})

    assert response.headers["location"].endswith("?err=notclean")
    assert notes.load_all("run-test", client.notes_dir) == []


def test_the_clean_shortcut_writes_the_terminal_surfaces_exact_sentence(client):
    """Both surfaces feed one file that gets clustered by hand at the next step.

    Two spellings of "this one was fine" would read as two different observations and quietly
    split a count in half.
    """
    client.post(f"/call/001/{MODEL}", data={"clean": "1"})

    written = notes.load_all("run-test", client.notes_dir)
    assert [n.text for n in written] == ["matches ground truth on all four fields"]


def test_an_empty_submit_writes_nothing(client):
    response = client.post(f"/call/000/{MODEL}", data={"text": "   "})

    assert response.headers["location"].endswith("?err=empty")
    assert notes.load_all("run-test", client.notes_dir) == []


def test_saving_moves_to_the_next_call_without_a_note(client):
    response = client.post(f"/call/000/{MODEL}", data={"text": "something"})
    assert response.headers["location"] == f"/call/001/{MODEL}"

    # and when nothing is left unread it stops rather than looping forever
    response = client.post(f"/call/001/{MODEL}", data={"text": "something else"})
    assert response.headers["location"] == "/"


def test_notes_are_append_only_through_this_surface_too(client):
    client.post(f"/call/000/{MODEL}", data={"text": "first read"})
    client.post(f"/call/000/{MODEL}", data={"text": "second read"})

    written = notes.load_all("run-test", client.notes_dir)
    assert [n.text for n in written] == ["first read", "second read"]
    assert notes.current("run-test", client.notes_dir)[("run-test", "000", MODEL)].text == (
        "second read"
    )


def test_filters_cut_the_run_down(tmp_path):
    rows = [_messy_row("000"), _clean_row("001")]
    results = tmp_path / "run-20260101T000000Z.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in rows))

    app = webapp.create_app(results, receipts=["001"], notes_dir=tmp_path / "notes")
    body = TestClient(app).get("/").text

    assert "0 of 1 read" in body
