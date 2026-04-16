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


class InvalidParamTypeError(TiiError):
    """Raised when a parameter type cannot be mapped to supported types."""


class MissingParamsError(TiiError):
    """Raised when invocation is missing required parameters."""

    def __init__(self, params: list[str]) -> None:
        super().__init__(f"missing required params: {params}")
        self.params = params
