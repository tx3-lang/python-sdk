"""Error types for TRP client operations."""

from __future__ import annotations

from tx3_sdk.errors import TrpError


class NetworkError(TrpError):
    """Raised when a request cannot reach the TRP endpoint."""


class HttpError(TrpError):
    """Raised when TRP responds with non-200 HTTP status."""

    def __init__(self, status: int, status_text: str, body: str) -> None:
        super().__init__(f"TRP HTTP error {status} {status_text}: {body}")
        self.status = status
        self.status_text = status_text
        self.body = body


class DeserializationError(TrpError):
    """Raised when JSON payload parsing fails."""


class MalformedResponseError(TrpError):
    """Raised when JSON-RPC response lacks required fields."""


class GenericRpcError(TrpError):
    """Raised for unclassified JSON-RPC error responses."""

    def __init__(self, code: int, message: str, data: object | None = None) -> None:
        super().__init__(f"TRP RPC error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class MissingTxArgError(TrpError):
    """Raised when TRP reports a missing transaction arg."""

    def __init__(self, key: str, arg_type: str | None = None) -> None:
        detail = f"missing tx arg {key!r}"
        if arg_type:
            detail += f" (type {arg_type})"
        super().__init__(detail)
        self.key = key
        self.arg_type = arg_type
