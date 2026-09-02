from datetime import date as date_cls
from decimal import Decimal, InvalidOperation
from typing import Optional

from .currencies import SUPPORTED_CURRENCIES
from .errors import ConversionError

# Money is parsed as Decimal, from the raw query string, never as float:
# float(amount) would introduce binary-rounding error before we ever get to
# multiply by a rate, and the caller is quoting a price to a paying customer.
MAX_DECIMAL_PLACES = 2

# The ECB euro foreign exchange reference rate series starts on 1999-01-04
# (the first trading day of the euro), regardless of which two currencies
# are being converted — Frankfurter computes every cross rate through EUR.
SERIES_START = date_cls(1999, 1, 4)


def validate_amount(raw: Optional[str]) -> Decimal:
    if raw is None or raw.strip() == "":
        raise ConversionError("invalid_amount", "amount is required.")

    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ConversionError("invalid_amount", "amount must be a number, got {!r}.".format(raw))

    if not amount.is_finite():
        raise ConversionError("invalid_amount", "amount must be a finite number, got {!r}.".format(raw))

    if amount <= 0:
        raise ConversionError("invalid_amount", "amount must be greater than zero, got {!r}.".format(raw))

    exponent = amount.as_tuple().exponent
    decimal_places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if decimal_places > MAX_DECIMAL_PLACES:
        raise ConversionError(
            "invalid_amount",
            "amount supports at most {} decimal places, got {} in {!r}.".format(
                MAX_DECIMAL_PLACES, decimal_places, raw
            ),
        )

    return amount


def validate_currency(raw: Optional[str], field: str) -> str:
    if raw is None or raw.strip() == "":
        raise ConversionError("invalid_currency", "{} is required.".format(field))

    code = raw.strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ConversionError(
            "invalid_currency",
            "{}={!r} is not a currency the ECB publishes rates for.".format(field, raw),
        )
    return code


def validate_date(raw: Optional[str], today: date_cls) -> date_cls:
    """`today` is passed in (not read from the clock here) so callers and
    tests can pin "now" instead of the check depending on wall-clock time."""
    if raw is None or raw.strip() == "":
        return today

    try:
        parsed = date_cls.fromisoformat(raw.strip())
    except ValueError:
        raise ConversionError("invalid_date", "date={!r} is not a valid YYYY-MM-DD date.".format(raw))

    if parsed > today:
        raise ConversionError(
            "future_date",
            "date={} is in the future; the ECB has not published a rate for it yet.".format(raw),
        )

    if parsed < SERIES_START:
        raise ConversionError(
            "date_before_series_start",
            "date={} is before {}, where the ECB reference rate series begins.".format(
                raw, SERIES_START.isoformat()
            ),
        )

    return parsed
