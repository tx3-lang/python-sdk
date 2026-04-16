"""Facade-layer error types."""

from __future__ import annotations

from tx3_sdk.errors import PollingError, ResolutionError, SubmissionError


class UnknownPartyError(ResolutionError):
    """Raised when a configured party is absent from protocol parties."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown party: {name}")
        self.name = name


class UnknownArgError(ResolutionError):
    """Raised when an arg key is not declared in protocol params."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown argument: {name}")
        self.name = name


class MissingParamsError(ResolutionError):
    """Raised when required args are not provided before resolve."""

    def __init__(self, params: list[str]) -> None:
        super().__init__(f"missing required params: {params}")
        self.params = params


class SubmitHashMismatchError(SubmissionError):
    """Raised when `trp.submit` hash differs from resolve hash."""

    def __init__(self, expected: str, received: str) -> None:
        super().__init__(f"submit hash mismatch: expected {expected}, got {received}")
        self.expected = expected
        self.received = received


class FinalizedFailedError(PollingError):
    """Raised when wait loop reaches terminal failure stage."""

    def __init__(self, tx_hash: str, stage: str) -> None:
        super().__init__(f"tx {tx_hash} failed with stage {stage}")
        self.tx_hash = tx_hash
        self.stage = stage


class FinalizedTimeoutError(PollingError):
    """Raised when wait loop exhausts all polling attempts."""

    def __init__(self, tx_hash: str, attempts: int, delay_seconds: float) -> None:
        super().__init__(
            f"tx {tx_hash} not confirmed after {attempts} attempts (delay {delay_seconds}s)"
        )
        self.tx_hash = tx_hash
        self.attempts = attempts
        self.delay_seconds = delay_seconds
