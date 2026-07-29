"""One receipt, one model call, one trace in Langfuse.

The smallest end to end version of what the harness does. Nothing here is reusable on purpose:
it exists to prove the pipe works and to give us a real trace record to read.

Run: uv run python scripts/trace_one_call.py
"""

from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

# the receipts live in the extractor project next door. this repo should vendor its own copy so
# it can be cloned and run standalone, but that is not worth doing for a single call.
SROIE_DIR = Path.home() / "Projects/Personal/structured-data-extractor/data/documents/sroie"

RECEIPT_ID = "000"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024


def load_ocr_text(receipt_id: str) -> str:
    """Read box/<id>.csv and return just the recognized text, top to bottom.

    Each line is 8 bounding box coords, then the text. The text itself can contain commas,
    so rejoin everything from field 8 onward instead of taking parts[8].
    """
    path = SROIE_DIR / "box" / f"{receipt_id}.csv"
    lines = path.read_text().splitlines()
    return "\n".join(",".join(line.split(",")[8:]) for line in lines)


def main() -> None:
    load_dotenv()

    langfuse = Langfuse()
    if not langfuse.auth_check():
        raise SystemExit("langfuse auth failed, check LANGFUSE_* in .env")

    anthropic = Anthropic()
    ocr_text = load_ocr_text(RECEIPT_ID)
    prompt = f"Extract the company, address, date and total from this receipt:\n\n{ocr_text}"

    # a "generation" is langfuse's observation type for a model call. a plain "span" would
    # record timing and io but has nowhere to put model, tokens or cost.
    with langfuse.start_as_current_observation(
        name="extract-receipt",
        as_type="generation",
        input=prompt,
        model=MODEL,
        model_parameters={"max_tokens": MAX_TOKENS},
        metadata={"receipt_id": RECEIPT_ID, "source": "sroie"},
    ) as generation:
        response = anthropic.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text

        # usage has to be set after the call, it does not exist before
        generation.update(
            output=text,
            usage_details={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        )
        trace_url = langfuse.get_trace_url()

    print(text)
    print()
    # the sdk batches spans over otel and ships them in the background. without flush a short
    # script exits before anything is sent.
    langfuse.flush()
    print(f"trace: {trace_url}")


if __name__ == "__main__":
    main()
