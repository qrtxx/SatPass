"""Domain errors raised by the services and turned into JSON responses in main.py."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.headers = headers


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class RuleViolation(DomainError):
    status_code = 422


class TooManyRequests(DomainError):
    status_code = 429


class BadGateway(DomainError):
    """A service we depend on (CelesTrak) failed or answered with something unusable."""

    status_code = 502
