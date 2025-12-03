"""
Custom exceptions for Zuper API Connector.
"""


class ZuperAPIError(Exception):
    """Base exception for Zuper API errors."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response

    def __str__(self):
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ZuperAuthError(ZuperAPIError):
    """Raised when authentication fails."""

    pass


class ZuperRateLimitError(ZuperAPIError):
    """Raised when rate limit is exceeded."""

    pass


class ZuperNotFoundError(ZuperAPIError):
    """Raised when a resource is not found."""

    pass
