"""Record one call to the target as a Langfuse trace.

target.py knows nothing about tracing on purpose. This is the seam where the two meet: it calls
extract, writes down what happened, and hands back the trace id so a scored row can point at the
trace it came from.

One call is one trace, not one trace per run with 150 calls nested in it. Receipts are
independent, so there is no sequence worth nesting, and the trace has to be the unit you filter,
score and annotate one at a time.
"""

from dataclasses import dataclass

from anthropic import Anthropic
from langfuse import Langfuse, propagate_attributes

from evalharness import target
from evalharness.target import Extraction


@dataclass
class TracedExtraction:
    """An extraction plus the id of the trace that recorded it."""

    extraction: Extraction
    trace_id: str


def traced_extract(
    *,
    text: str,
    client: Anthropic,
    model: str,
    receipt_id: str,
    run_id: str,
    langfuse: Langfuse,
) -> TracedExtraction:
    """Extract one receipt and record the call.

    Transport failures still propagate. The trace survives them, carrying the prompt and an
    error status, which is the whole reason the prompt goes on before the call and not after.
    """
    # entered per call rather than once around the whole run. otel keeps its context in a thread
    # local, so attributes set on the main thread are invisible inside a thread pool worker. put
    # them here and the runner can be as concurrent as it likes without losing the run id.
    with (
        propagate_attributes(
            session_id=run_id,
            version=target.TARGET_VERSION,
            metadata={"receipt_id": receipt_id},
        ),
        langfuse.start_as_current_observation(
            name="extract-receipt",
            as_type="generation",
            input=target.build_prompt(text),
            model=model,
            # worth recording even though it never varies today. when it does vary, every trace
            # from before the change already says what it was.
            model_parameters={"max_tokens": target.MAX_TOKENS, "thinking": "disabled"},
        ) as generation,
    ):
        extraction = target.extract(text, client=client, model=model)

        generation.update(
            output=extraction.raw_output,
            # tokens do not exist until the response does, so this cannot go on at open time.
            # cost is not sent: langfuse derives it from the model string against its own price
            # table, which is also why a model name it does not recognise costs zero, silently.
            usage_details={
                "input": extraction.input_tokens,
                "output": extraction.output_tokens,
            },
            metadata={"stop_reason": extraction.stop_reason},
            # a rejected extraction is a result, not a crash, but it is not a success either.
            # langfuse already has a level and a status message for this, so use them instead of
            # inventing a second status concept that no ui and no filter knows about.
            level="ERROR" if extraction.error else "DEFAULT",
            status_message=extraction.error,
        )

        return TracedExtraction(extraction=extraction, trace_id=generation.trace_id)
