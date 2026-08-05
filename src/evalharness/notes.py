"""Store one free-text note per call, append only.

Notes are the one artifact in this repo that cannot be regenerated. Everything in results/ comes
back by paying for another run; a note is somebody having read a receipt and written down what
they saw. So notes are committed, and writing is append only: changing your mind about a call
adds a line rather than replacing one, and the earlier read stays on the record. Reads take the
last line for a key, so the current view is the latest opinion without losing how it got there.

Notes are free text on purpose. No category field, no severity, no tags. Categories come out of
reading the notes afterwards, and a category field on this file would mean deciding the
categories before doing the reading, which is backwards.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

NOTES_DIR = Path(__file__).parents[2] / "notes"


@dataclass(frozen=True)
class Note:
    """One reading of one call."""

    run_id: str
    receipt_id: str
    model: str
    text: str
    noted_at: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.run_id, self.receipt_id, self.model)


def notes_path(run_id: str, notes_dir: Path = NOTES_DIR) -> Path:
    """One file per run.

    Keyed by run rather than pooled, because a note is about a specific call: the same receipt
    and model in a later run is a different output and deserves its own reading.
    """
    return notes_dir / f"notes-{run_id}.jsonl"


def write(
    *,
    run_id: str,
    receipt_id: str,
    model: str,
    text: str,
    notes_dir: Path = NOTES_DIR,
) -> Note:
    """Append one note and return it."""
    note = Note(
        run_id=run_id,
        receipt_id=receipt_id,
        model=model,
        text=text,
        noted_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    path = notes_path(run_id, notes_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(note)) + "\n")
    return note


def load_all(run_id: str, notes_dir: Path = NOTES_DIR) -> list[Note]:
    """Every note ever written for a run, in the order they were written."""
    path = notes_path(run_id, notes_dir)
    if not path.exists():
        return []
    with path.open() as f:
        return [Note(**json.loads(line)) for line in f if line.strip()]


def current(run_id: str, notes_dir: Path = NOTES_DIR) -> dict[tuple[str, str, str], Note]:
    """The latest note per call, keyed by run + receipt + model.

    Last line wins. This is what the review loop reads to know what it has already covered, so
    re-noting a call marks it done with the new text while the old one stays in the file.
    """
    return {note.key: note for note in load_all(run_id, notes_dir)}
