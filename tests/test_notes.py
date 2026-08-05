"""Notes are the one thing here that cannot be regenerated, so the storage rules get pinned."""

from evalharness import notes


def _write(tmp_path, receipt_id, model, text, run_id="run-test"):
    return notes.write(
        run_id=run_id, receipt_id=receipt_id, model=model, text=text, notes_dir=tmp_path
    )


def test_note_round_trips(tmp_path):
    _write(tmp_path, "000", "claude-haiku-4-5", "copied BND straight from the ocr")
    (note,) = notes.load_all("run-test", tmp_path)
    assert note.key == ("run-test", "000", "claude-haiku-4-5")
    assert note.text == "copied BND straight from the ocr"
    assert note.noted_at


def test_renoting_appends_and_the_last_one_wins(tmp_path):
    """Changing your mind is a second line, not an edit.

    The first read is evidence too. If a note gets revised after seeing twenty more receipts,
    that revision is itself worth being able to see later.
    """
    _write(tmp_path, "000", "claude-haiku-4-5", "wrong company")
    _write(tmp_path, "000", "claude-haiku-4-5", "not wrong, the ocr says that")

    assert len(notes.load_all("run-test", tmp_path)) == 2
    current = notes.current("run-test", tmp_path)
    assert len(current) == 1
    assert current[("run-test", "000", "claude-haiku-4-5")].text == "not wrong, the ocr says that"


def test_notes_are_keyed_by_run_receipt_and_model(tmp_path):
    """Same receipt, different model is a different call and a different note."""
    _write(tmp_path, "000", "claude-haiku-4-5", "haiku note")
    _write(tmp_path, "000", "claude-opus-5", "opus note")
    assert len(notes.current("run-test", tmp_path)) == 2


def test_runs_do_not_share_a_file(tmp_path):
    _write(tmp_path, "000", "claude-haiku-4-5", "first run", run_id="run-a")
    _write(tmp_path, "000", "claude-haiku-4-5", "second run", run_id="run-b")
    assert len(notes.current("run-a", tmp_path)) == 1
    run_b = notes.current("run-b", tmp_path)
    assert run_b[("run-b", "000", "claude-haiku-4-5")].text == "second run"


def test_a_run_with_no_notes_reads_as_empty(tmp_path):
    """What resuming depends on: nothing read yet is an empty dict, not a crash."""
    assert notes.load_all("run-never-read", tmp_path) == []
    assert notes.current("run-never-read", tmp_path) == {}
