from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from .cache import RateCache
from .errors import ConversionError
from .upstream import fetch_rate, get_upstream_base
from .validation import validate_amount, validate_currency, validate_date

SOURCE = "ECB via frankfurter.dev"
TWO_PLACES = Decimal("0.01")

_cache = RateCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(base_url=get_upstream_base(), timeout=5.0)
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(title="fx-tool", lifespan=lifespan)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


@app.exception_handler(ConversionError)
async def conversion_error_handler(request: Request, exc: ConversionError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "message": exc.message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "something went wrong handling this request."},
    )


def _money(value: Decimal) -> float:
    return float(value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


@app.get("/tools/convert")
async def convert(
    amount: Optional[str] = None,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    date: Optional[str] = None,
    client: httpx.AsyncClient = Depends(get_http_client),
):
    parsed_amount = validate_amount(amount)
    base = validate_currency(from_, "from")
    target = validate_currency(to, "to")
    today = datetime.now(timezone.utc).date()
    asked_date = validate_date(date, today)

    if base == target:
        return {
            "amount": float(parsed_amount),
            "from": base,
            "to": target,
            "rate": 1.0,
            "result": _money(parsed_amount),
            "rate_date": asked_date.isoformat(),
            "asked_date": asked_date.isoformat(),
            "source": SOURCE,
        }

    async def do_fetch():
        return await fetch_rate(client, base, target, asked_date)

    rate, rate_date = await _cache.get_or_fetch(base, target, asked_date, today, do_fetch)

    return {
        "amount": float(parsed_amount),
        "from": base,
        "to": target,
        "rate": float(rate),
        "result": _money(parsed_amount * rate),
        "rate_date": rate_date.isoformat(),
        "asked_date": asked_date.isoformat(),
        "source": SOURCE,
    }
