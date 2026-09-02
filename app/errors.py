class ConversionError(Exception):
    """Carries a machine-readable code and a human message to the API boundary.

    Every rejection the endpoint can produce — a bad query param, a date the
    ECB has no rate for, an unreachable upstream — raises this. main.py's
    exception handler is the only place that turns it into an HTTP response,
    so the response shape ({"error", "message"}) stays consistent everywhere.
    """

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
