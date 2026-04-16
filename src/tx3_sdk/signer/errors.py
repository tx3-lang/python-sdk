"""Error classes for signer construction and signing."""

from tx3_sdk.errors import SignerError


class InvalidMnemonicError(SignerError):
    """Raised when a mnemonic phrase is invalid."""


class InvalidPrivateKeyError(SignerError):
    """Raised when a signer private key has invalid encoding or length."""


class InvalidHashError(SignerError):
    """Raised when tx hash input is invalid."""


class InvalidAddressError(SignerError):
    """Raised when address parsing or decoding fails."""


class UnsupportedPaymentCredentialError(SignerError):
    """Raised when address uses unsupported payment credential format."""


class AddressMismatchError(SignerError):
    """Raised when signer key does not match configured address."""
