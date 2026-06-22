"""Error types for TII and protocol loading."""

from tx3_sdk.errors import TiiError


class InvalidJsonError(TiiError):
    """Raised when TII JSON is malformed."""


class UnknownTxError(TiiError):
    """Raised when a transaction name does not exist in the protocol."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown transaction: {name}")
        self.name = name


class UnknownProfileError(TiiError):
    """Raised when a profile name does not exist in the protocol."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown profile: {name}")
        self.name = name


class InvalidParamsSchemaError(TiiError):
    """Raised when params schema is malformed."""


class MissingParamsError(TiiError):
    """Raised when invocation is missing required parameters."""

    def __init__(self, params: list[str]) -> None:
        super().__init__(f"missing required params: {params}")
        self.params = params


class EncodeArgError(TiiError):
    """Raised when a complex argument value does not match its declared
    :class:`~tx3_sdk.tii.param_type.ParamType`.

    Surfaced **before** the request is sent (the SDK is authoritative for complex
    types), so a malformed complex arg fails fast at the client rather than as an
    opaque resolver error.
    """
