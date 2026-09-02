import os
from datetime import date as date_cls
from decimal import Decimal
from typing import Tuple

import httpx

from .errors import ConversionError


def get_upstream_base() -> str:
    return os.environ.get("FX_UPSTREAM_BASE", "https://api.frankfurter.dev").rstrip("/")


async def fetch_rate(
    client: httpx.AsyncClient, base: str, target: str, on_date: date_cls
) -> Tuple[Decimal, date_cls]:
    """Ask upstream for base->target on_date. Returns (rate, rate_date) — the
    date upstream says the rate actually belongs to, which for a weekend or
    holiday is the last published business day before on_date, not on_date
    itself. Never returns a rate we can't attribute to a real date: every
    failure mode raises ConversionError instead."""
    path = "/v1/{}".format(on_date.isoformat())

    try:
        response = await client.get(path, params={"base": base, "symbols": target})
    except httpx.TimeoutException:
        raise ConversionError(
            "upstream_unavailable", "the exchange rate provider timed out.", status_code=502
        )
    except httpx.HTTPError as exc:
        raise ConversionError(
            "upstream_unavailable",
            "could not reach the exchange rate provider: {}.".format(exc),
            status_code=502,
        )

    if response.status_code == 404:
        # Upstream returns this same 404 for "no data at all" and for an
        # unknown currency — but we've already validated the currency and
        # the date range ourselves, so at this point it genuinely means no
        # rate was published for this pair on this date.
        raise ConversionError(
            "no_rate_available",
            "the ECB has not published a {}->{} rate for {}.".format(base, target, on_date.isoformat()),
            status_code=404,
        )

    if response.status_code != 200:
        raise ConversionError(
            "upstream_unavailable",
            "the exchange rate provider returned status {}.".format(response.status_code),
            status_code=502,
        )

    try:
        payload = response.json()
    except ValueError:
        raise ConversionError(
            "upstream_unavailable", "the exchange rate provider returned a non-JSON response.", status_code=502
        )

    try:
        rate = Decimal(str(payload["rates"][target]))
        rate_date = date_cls.fromisoformat(payload["date"])
    except (KeyError, TypeError, ValueError):
        raise ConversionError(
            "upstream_unavailable",
            "the exchange rate provider returned an unexpected response shape.",
            status_code=502,
        )

    return rate, rate_date
