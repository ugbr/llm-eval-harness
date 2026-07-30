"""The eval set is committed, so it doubles as the fixture. These check it stayed intact."""

from evalharness import dataset


def test_eval_set_is_the_labelled_receipts():
    ids = dataset.receipt_ids()
    assert len(ids) == 50
    assert ids[0] == "000"
    assert ids[-1] == "049"
    assert ids == sorted(ids)


def test_every_label_has_an_ocr_file():
    """A label with no input is not an eval case, it is a vendoring mistake."""
    for rid in dataset.receipt_ids():
        assert (dataset.OCR_DIR / f"{rid}.csv").exists(), f"{rid} has a label but no ocr text"


def test_labels_have_the_documented_shape():
    for rid, row in dataset.load_ground_truth().items():
        assert set(row) == {"id", "company", "address", "date", "total", "status", "note"}
        assert row["id"] == rid
        assert row["status"] in {"ok", "fixed"}
        # a corrected label without a note is an unexplained edit to ground truth
        if row["status"] == "fixed":
            assert row["note"], f"{rid} is marked fixed but says nothing about what changed"


def test_ocr_text_keeps_commas_inside_the_text():
    """The bug this pins: splitting on "," and taking parts[8] truncates at the first comma.

    Line 4 of receipt 000 has two of them, so it comes back cut short if the rejoin regresses.
    """
    lines = dataset.load_ocr_text("000").splitlines()
    assert "NO.53 55,57 & 59, JALAN SAGU 18," in lines


def test_ocr_text_keeps_every_line():
    raw = (dataset.OCR_DIR / "000.csv").read_text().splitlines()
    assert len(dataset.load_ocr_text("000").splitlines()) == len(raw)
