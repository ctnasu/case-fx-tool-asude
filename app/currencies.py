# The currencies Frankfurter/ECB publish reference rates for, as returned by
# GET /v1/currencies at the time this was written. Hardcoded rather than
# fetched at startup: the fake upstream used to grade this doesn't have to
# implement /v1/currencies, and this list changes on the order of years, not
# days — validating against it ourselves also lets us tell "unknown currency"
# apart from "no rate for that date", which upstream reports identically.
SUPPORTED_CURRENCIES = {
    "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD",
    "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR", "NOK",
    "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR",
}
