"""One receipt, one model call, one trace in Langfuse.

The smallest end to end version of what the harness does, and the fastest way to check the pipe
still works after touching the target or the tracer. It runs the same traced path a full run
does, just once and with nothing around it.

Run: uv run python scripts/trace_one_call.py
"""

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

from evalharness import dataset, tracing

RECEIPT_ID = "000"
MODEL = "claude-haiku-4-5"


def main() -> None:
    load_dotenv()

    langfuse = Langfuse()
    if not langfuse.auth_check():
        raise SystemExit("langfuse auth failed, check LANGFUSE_* in .env")

    traced = tracing.traced_extract(
        text=dataset.load_ocr_text(RECEIPT_ID),
        client=Anthropic(),
        model=MODEL,
        receipt_id=RECEIPT_ID,
        run_id="smoke",
        langfuse=langfuse,
    )

    print(traced.extraction.raw_output)
    if traced.extraction.error:
        print(f"\nrejected: {traced.extraction.error}")

    # the sdk batches spans over otel and ships them in the background. without flush a short
    # script exits before anything is sent.
    langfuse.flush()
    print(f"\ntrace: {langfuse.get_trace_url(trace_id=traced.trace_id)}")


if __name__ == "__main__":
    main()
