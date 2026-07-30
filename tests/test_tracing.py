"""No API calls and no network. Fakes stand in for both clients.

What this pins down is our own contract, not Langfuse's: a rejected extraction has to reach the
trace as ERROR with the reason attached, because a failure you cannot filter for is a failure
nobody finds. Whether the SDK then ships that correctly is what scripts/trace_one_call.py is
for, and its trace has been read back off the API by hand.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from evalharness import tracing

GOOD = '{"company": "ACME LTD", "address": "12 High St", "date": "2019-02-01", "total": "4.50"}'
BAD = '{"company": "ACME LTD", "address": "12 High St", "date": "2019-02-01", "total": "0.00"}'


class FakeGeneration:
    """Records what the tracer decided to write."""

    trace_id = "trace-abc"

    def __init__(self):
        self.updates = {}

    def update(self, **kwargs):
        self.updates.update(kwargs)


class FakeLangfuse:
    def __init__(self):
        self.generation = FakeGeneration()
        self.opened_with = None

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        self.opened_with = kwargs
        yield self.generation


def fake_anthropic(raw_output: str, *, stop_reason: str = "end_turn"):
    """Just enough of the client for target.extract to run against."""
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=raw_output)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=11, output_tokens=22),
    )
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def run(raw_output: str) -> tuple[tracing.TracedExtraction, FakeLangfuse]:
    langfuse = FakeLangfuse()
    traced = tracing.traced_extract(
        text="SOME OCR TEXT",
        client=fake_anthropic(raw_output),
        model="claude-haiku-4-5",
        receipt_id="000",
        run_id="run-1",
        langfuse=langfuse,
    )
    return traced, langfuse


def test_a_good_extraction_is_not_flagged():
    traced, langfuse = run(GOOD)

    assert traced.extraction.receipt is not None
    assert traced.trace_id == "trace-abc"
    assert langfuse.generation.updates["level"] == "DEFAULT"
    assert langfuse.generation.updates["status_message"] is None


def test_a_rejected_extraction_lands_on_the_trace_as_an_error():
    traced, langfuse = run(BAD)

    # the call itself succeeded, so this is a result to score, not an exception to swallow
    assert traced.extraction.receipt is None
    assert langfuse.generation.updates["level"] == "ERROR"
    assert "not positive" in langfuse.generation.updates["status_message"]
    # and the raw text survives either way, or there is nothing to read at error analysis
    assert langfuse.generation.updates["output"] == BAD


def test_the_prompt_goes_on_before_the_call_not_after():
    """A transport failure has to leave a trace that says what we tried to send."""
    _, langfuse = run(GOOD)

    assert "SOME OCR TEXT" in langfuse.opened_with["input"]
    assert langfuse.opened_with["model"] == "claude-haiku-4-5"
    assert langfuse.opened_with["model_parameters"]["thinking"] == "disabled"


def test_tokens_are_reported_from_the_response():
    _, langfuse = run(GOOD)

    assert langfuse.generation.updates["usage_details"] == {"input": 11, "output": 22}
    # cost is deliberately absent. langfuse derives it from the model string, and sending our
    # own would mean two price tables that can disagree.
    assert "cost_details" not in langfuse.generation.updates


@pytest.mark.parametrize("stop_reason", ["end_turn", "max_tokens"])
def test_stop_reason_reaches_the_trace(stop_reason):
    """Truncation is its own failure mode, and it is invisible unless this is recorded."""
    langfuse = FakeLangfuse()
    tracing.traced_extract(
        text="SOME OCR TEXT",
        client=fake_anthropic(GOOD, stop_reason=stop_reason),
        model="claude-haiku-4-5",
        receipt_id="000",
        run_id="run-1",
        langfuse=langfuse,
    )

    assert langfuse.generation.updates["metadata"]["stop_reason"] == stop_reason
