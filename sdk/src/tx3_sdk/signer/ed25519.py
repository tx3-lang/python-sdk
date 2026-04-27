"""Generic Ed25519 signer implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from nacl.signing import SigningKey

from tx3_sdk.signer.errors import InvalidHashError, InvalidMnemonicError, InvalidPrivateKeyError
from tx3_sdk.signer.signer import SignRequest
from tx3_sdk.signer.witness import vkey_witness
from tx3_sdk.trp.spec import TxWitness


@dataclass(frozen=True)
class Ed25519Signer:
    """A raw-key Ed25519 signer using a 32-byte private key seed."""

    _address: str
    _signing_key: SigningKey

    @classmethod
    def from_private_key(cls, address: str, private_key: bytes) -> "Ed25519Signer":
        """Creates a signer from a 32-byte private key seed."""
        if len(private_key) != 32:
            raise InvalidPrivateKeyError(f"invalid private key: expected 32 bytes, got {len(private_key)}")
        return cls(_address=address, _signing_key=SigningKey(private_key))

    @classmethod
    def from_hex(cls, address: str, private_key_hex: str) -> "Ed25519Signer":
        """Creates a signer from a hex-encoded private key seed."""
        try:
            key_bytes = bytes.fromhex(private_key_hex)
        except ValueError as exc:
            raise InvalidPrivateKeyError("invalid private key: hex decode failed") from exc
        return cls.from_private_key(address=address, private_key=key_bytes)

    @classmethod
    def from_mnemonic(cls, address: str, phrase: str) -> "Ed25519Signer":
        """Creates a signer from a mnemonic by deriving a deterministic 32-byte seed."""
        words = [part for part in phrase.strip().split(" ") if part]
        if len(words) < 12:
            raise InvalidMnemonicError("invalid mnemonic: expected at least 12 words")
        seed = hashlib.sha512(phrase.encode("utf-8")).digest()[:32]
        return cls.from_private_key(address=address, private_key=seed)

    def address(self) -> str:
        """Returns the signer address."""
        return self._address

    def sign(self, request: SignRequest) -> TxWitness:
        """Signs the request's tx hash and returns a `vkey` witness."""
        try:
            tx_hash = bytes.fromhex(request.tx_hash_hex)
        except ValueError as exc:
            raise InvalidHashError("invalid hash: hex decode failed") from exc
        if len(tx_hash) != 32:
            raise InvalidHashError(f"invalid hash: expected 32 bytes, got {len(tx_hash)}")

        signed = self._signing_key.sign(tx_hash)
        signature = signed.signature
        public_key = bytes(self._signing_key.verify_key)
        return vkey_witness(public_key.hex(), signature.hex())
