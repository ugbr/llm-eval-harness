"""Read the vendored eval set off disk.

See data/README.md for where the files came from and what is deliberately not there.

Labels come back as plain dicts. Scoring needs to normalise both sides before it compares
anything, and that belongs with the scorer rather than being decided here.
"""

import json
from functools import cache
from pathlib import Path

# src/evalharness/dataset.py, so the repo root is two parents up
DATA_DIR = Path(__file__).parents[2] / "data"
OCR_DIR = DATA_DIR / "ocr"
GROUND_TRUTH = DATA_DIR / "ground_truth.jsonl"


@cache
def load_ground_truth() -> dict[str, dict]:
    """Every verified label, keyed by receipt id."""
    with GROUND_TRUTH.open() as f:
        return {row["id"]: row for row in (json.loads(line) for line in f)}


def receipt_ids() -> list[str]:
    """The eval set, in order.

    Defined by what has a verified label, not by counting files in ocr/. An OCR file with no
    label is not an eval case, it is an unlabelled receipt.
    """
    return sorted(load_ground_truth())


def load_ocr_text(receipt_id: str) -> str:
    """The recognised text for one receipt, top to bottom.

    Each line of the source csv is eight bounding box coordinates then the text. The text can
    itself contain commas, so rejoin everything from field 8 on instead of taking parts[8].
    """
    lines = (OCR_DIR / f"{receipt_id}.csv").read_text().splitlines()
    return "\n".join(",".join(line.split(",")[8:]) for line in lines)
