"""The system under test. OCR text in, a validated Receipt out.

This is the thing the harness measures, so it sits behind one narrow interface. Right now it
calls the Anthropic API in process. Pointing it at an HTTP service instead should not require
touching anything else in the harness, as long as the replacement still reports what an
Extraction carries.

It does not import langfuse on purpose. Tracing is the caller's job. What this module owes the
caller is the evidence: the exact prompt, the raw text that came back, tokens, latency, and any
validation failure.
"""

import re
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError, WithJsonSchema, field_validator

# bump when anything in this module changes what the target does: the prompt, the schema, or the
# validation rules. it rides on every trace and every result row, so a run says what produced it
# instead of you keeping a notebook that maps run ids to code.
#
# v2 accepts a currency prefix on total. under v1 that rejected 33 of 150 outputs, all of which
# matched ground truth once the symbol came off.
TARGET_VERSION = "v2"

PROMPT = "Extract the fields from this receipt:\n\n{text}"

MAX_TOKENS = 1024


def build_prompt(text: str) -> str:
    """The exact string this target sends for a given receipt.

    Split out so a caller can record what is about to be sent before sending it. If the call
    then dies on a rate limit, the trace still says what we tried.
    """
    return PROMPT.format(text=text)


class Receipt(BaseModel):
    """What a successful extraction looks like.

    The two rules below are field validators rather than Field(gt=...) constraints, for two
    reasons. json_schema cannot express them, and the ones pydantic does emit for a Decimal get
    rejected by the API. More usefully: a rule enforced here fails after the call, which makes
    it a recorded failure mode we can count, instead of a request that never went out.
    """

    model_config = {"extra": "forbid"}

    company: str
    address: str
    # a money value belongs on the wire as a string, and pydantic's own Decimal schema uses a
    # lookahead regex the API's regex engine rejects. the ground truth stores totals the same
    # way, so both sides of a comparison start as strings.
    total: Annotated[Decimal, WithJsonSchema({"type": "string"})]
    date: date

    @field_validator("total", mode="before")
    @classmethod
    def strip_currency(cls, value: Any) -> Any:
        """Accept a total written the way the receipt writes it.

        Receipts in this set print totals as "RM 60.30" or "$8.20", and the models copy that
        faithfully. Without this the extractor rejects a correct answer over formatting, and it
        rejects the whole document with it, so three fields it got right go down with the one
        it rendered differently. The symbol is not thrown away, raw_output still has it.
        """
        if isinstance(value, str):
            return re.sub(r"^(RM|\$)\s*", "", value.strip(), flags=re.IGNORECASE)
        return value

    @field_validator("total")
    @classmethod
    def total_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError(f"total {value} is not positive")
        return value

    @field_validator("date")
    @classmethod
    def date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError(f"{value} is later than today")
        return value


RESPONSE_SCHEMA = Receipt.model_json_schema()


@dataclass
class Extraction:
    """One call to the target: what we sent, what came back, and what it cost.

    receipt is None when the model returned something Receipt rejected, and error carries the
    reason. That is a result worth scoring, not a crash, which is why raw_output is kept either
    way. A failure you cannot read is a failure you cannot categorise.
    """

    prompt: str
    model: str
    raw_output: str
    stop_reason: str | None
    receipt: Receipt | None
    error: str | None
    input_tokens: int
    output_tokens: int
    latency_s: float


def extract(text: str, client: Anthropic, model: str) -> Extraction:
    """Run one receipt through the target.

    Transport failures (rate limits, 5xx, timeouts) are left to propagate. They say nothing
    about extraction quality, so the caller isolates them per call rather than scoring them.
    """
    prompt = build_prompt(text)

    start = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        # pinned, not omitted. sonnet and opus run adaptive thinking when this is left off,
        # which means the model decides per call whether to think. that moves cost, latency and
        # sometimes the answer with nothing in the harness having changed, and a regression gate
        # cannot tell that apart from a real regression.
        thinking={"type": "disabled"},
        output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    latency_s = time.perf_counter() - start

    # not messages.parse(). that helper validates for you and raises on failure, which throws
    # away the response, and the response is exactly what you want to read when validation
    # fails. so we hold the text and validate it ourselves.
    raw_output = next((b.text for b in response.content if b.type == "text"), "")

    receipt: Receipt | None = None
    error: str | None = None
    try:
        receipt = Receipt.model_validate_json(raw_output)
    except ValidationError as e:
        error = "; ".join(f"{'.'.join(str(p) for p in d['loc'])}: {d['msg']}" for d in e.errors())

    return Extraction(
        prompt=prompt,
        model=model,
        raw_output=raw_output,
        stop_reason=response.stop_reason,
        receipt=receipt,
        error=error,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_s=latency_s,
    )
