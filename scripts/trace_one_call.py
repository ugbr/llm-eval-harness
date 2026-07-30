"""One receipt, one model call, one trace in Langfuse.

The smallest end to end version of what the harness does. It exists to prove the pipe works and
to give us a real trace record to read, so it deliberately skips everything the real runner
does: no concurrency, no failure isolation, no metadata schema.

Run: uv run python scripts/trace_one_call.py
"""

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import Langfuse

from evalharness import dataset

RECEIPT_ID = "000"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024


def main() -> None:
    load_dotenv()

    langfuse = Langfuse()
    if not langfuse.auth_check():
        raise SystemExit("langfuse auth failed, check LANGFUSE_* in .env")

    anthropic = Anthropic()
    ocr_text = dataset.load_ocr_text(RECEIPT_ID)
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
