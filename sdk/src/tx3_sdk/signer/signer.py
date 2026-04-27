"""Signer interface definition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tx3_sdk.signer.witness import TxWitness


@dataclass(frozen=True)
class SignRequest:
    """Inputs passed to a `Signer` for each sign call.

    Carries both the bound tx hash and the full hex-encoded tx CBOR.
    Hash-based signers (CardanoSigner, Ed25519Signer) read `tx_hash_hex`;
    tx-based signers (e.g. wallet adapters that need the full tx body) read
    `tx_cbor_hex`. The SDK always populates both fields.
    """

    tx_hash_hex: str
    tx_cbor_hex: str


class Signer(Protocol):
    """Represents a signer capable of producing a witness for a `SignRequest`."""

    def address(self) -> str:
        """Returns the address bound to this signer."""

    def sign(self, request: SignRequest) -> TxWitness:
        """Signs the transaction described by `request` and returns a witness."""
