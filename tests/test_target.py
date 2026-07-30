"""No API calls here. These cover the schema we send and the validation we run on what returns."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from evalharness.target import RESPONSE_SCHEMA, Receipt

VALID = '{"company": "ACME LTD", "address": "12 High St", "date": "2019-02-01", "total": "4.50"}'


def test_valid_output_parses_into_typed_fields():
    r = Receipt.model_validate_json(VALID)
    assert r.company == "ACME LTD"
    assert r.date == date(2019, 2, 1)
    # a total that arrives as a string has to land as Decimal, not float, or money arithmetic
    # downstream starts drifting
    assert r.total == Decimal("4.50")
    assert isinstance(r.total, Decimal)


@pytest.mark.parametrize(
    "why,bad_json",
    [
        ("zero total", '{"company":"A","address":"B","date":"2019-02-01","total":"0.00"}'),
        ("negative total", '{"company":"A","address":"B","date":"2019-02-01","total":"-1.00"}'),
        ("unknown field", '{"company":"A","address":"B","date":"2019-02-01","total":"1","x":1}'),
        ("missing field", '{"company":"A","address":"B","date":"2019-02-01"}'),
    ],
)
def test_bad_output_is_rejected(why, bad_json):
    with pytest.raises(ValidationError):
        Receipt.model_validate_json(bad_json)


def test_future_date_is_rejected():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        Receipt.model_validate_json(
            f'{{"company": "A", "address": "B", "date": "{tomorrow}", "total": "1.00"}}'
        )


def test_schema_stays_within_what_the_api_accepts():
    """The API rejects json_schema it cannot compile, and it does so at request time.

    Pydantic's own Decimal schema carries a lookahead regex that fails there, so total is
    declared as a plain string on the wire. Catch that here rather than as a 400 mid-run.
    """
    assert RESPONSE_SCHEMA["properties"]["total"] == {"title": "Total", "type": "string"}
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert set(RESPONSE_SCHEMA["required"]) == {"company", "address", "date", "total"}

    def walk(node):
        if isinstance(node, dict):
            # unsupported by structured outputs: patterns, numeric bounds, length bounds
            for unsupported in ("pattern", "minimum", "maximum", "exclusiveMinimum",
                                "exclusiveMaximum", "minLength", "maxLength", "multipleOf"):
                assert unsupported not in node, f"{unsupported} is not accepted in a json_schema"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(RESPONSE_SCHEMA)
