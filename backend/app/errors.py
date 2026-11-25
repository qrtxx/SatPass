"""Domain errors raised by the services and turned into JSON responses in main.py."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.headers = headers


class Unauthorized(DomainError):
    """Not logged in, or the token is bad. HTTP requires 401 responses to say which scheme to use."""

    status_code = 401

    def __init__(self, code: str, message: str):
        super().__init__(code, message, headers={"WWW-Authenticate": "Bearer"})


class Forbidden(DomainError):
    """Logged in, but not allowed to do this."""

    status_code = 403


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
