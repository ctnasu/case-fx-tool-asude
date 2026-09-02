from datetime import date

import pytest

from app.errors import ConversionError
from app.validation import SERIES_START, validate_date

TODAY = date(2026, 8, 28)


def test_validate_date_defaults_to_today_when_omitted():
    assert validate_date(None, TODAY) == TODAY


def test_validate_date_accepts_valid_past_date():
    assert validate_date("2026-08-01", TODAY) == date(2026, 8, 1)


def test_validate_date_accepts_today():
    assert validate_date("2026-08-28", TODAY) == TODAY


def test_validate_date_rejects_bad_format():
    with pytest.raises(ConversionError) as exc:
        validate_date("28-08-2026", TODAY)
    assert exc.value.code == "invalid_date"


def test_validate_date_rejects_future_date():
    with pytest.raises(ConversionError) as exc:
        validate_date("2026-08-29", TODAY)
    assert exc.value.code == "future_date"


def test_validate_date_rejects_before_series_start():
    with pytest.raises(ConversionError) as exc:
        validate_date("1990-01-01", TODAY)
    assert exc.value.code == "date_before_series_start"


def test_validate_date_accepts_series_start_itself():
    assert validate_date(SERIES_START.isoformat(), TODAY) == SERIES_START
