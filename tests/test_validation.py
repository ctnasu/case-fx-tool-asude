from decimal import Decimal

import pytest

from app.errors import ConversionError
from app.validation import validate_amount, validate_currency


def test_validate_amount_accepts_plain_number():
    assert validate_amount("250") == Decimal("250")


def test_validate_amount_accepts_two_decimals():
    assert validate_amount("250.25") == Decimal("250.25")


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_validate_amount_rejects_missing(raw):
    with pytest.raises(ConversionError) as exc:
        validate_amount(raw)
    assert exc.value.code == "invalid_amount"


def test_validate_amount_rejects_non_numeric():
    with pytest.raises(ConversionError) as exc:
        validate_amount("abc")
    assert exc.value.code == "invalid_amount"


def test_validate_amount_rejects_zero():
    with pytest.raises(ConversionError) as exc:
        validate_amount("0")
    assert exc.value.code == "invalid_amount"


def test_validate_amount_rejects_negative():
    with pytest.raises(ConversionError) as exc:
        validate_amount("-5")
    assert exc.value.code == "invalid_amount"


def test_validate_amount_rejects_too_many_decimals():
    with pytest.raises(ConversionError) as exc:
        validate_amount("1.2345678901")
    assert exc.value.code == "invalid_amount"


def test_validate_currency_normalizes_case():
    assert validate_currency("eur", "from") == "EUR"


def test_validate_currency_rejects_unknown_code():
    with pytest.raises(ConversionError) as exc:
        validate_currency("ZZZ", "from")
    assert exc.value.code == "invalid_currency"


def test_validate_currency_rejects_missing():
    with pytest.raises(ConversionError) as exc:
        validate_currency(None, "to")
    assert exc.value.code == "invalid_currency"
