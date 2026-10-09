"""One error type for the API: a machine-readable code, a plain-English message and an HTTP status."""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra or {}

    def body(self) -> dict:
        return {"error": self.code, "message": self.message, **self.extra}
