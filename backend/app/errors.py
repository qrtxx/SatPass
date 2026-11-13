"""Domain errors raised by the services and turned into JSON responses in main.py."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class RuleViolation(DomainError):
    status_code = 422
