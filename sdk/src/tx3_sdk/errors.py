"""Base error hierarchy roots for the Tx3 SDK."""


class Tx3Error(Exception):
    """Base class for all SDK errors."""


class TiiError(Tx3Error):
    """Base class for protocol loading and TII errors."""


class TrpError(Tx3Error):
    """Base class for TRP transport and RPC errors."""


class SignerError(Tx3Error):
    """Base class for signer construction and signing errors."""


class ResolutionError(Tx3Error):
    """Base class for facade resolve-time errors."""


class SubmissionError(Tx3Error):
    """Base class for submit-time errors."""


class PollingError(Tx3Error):
    """Base class for wait-mode polling errors."""
