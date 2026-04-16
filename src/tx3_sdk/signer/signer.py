"""Signer interface definition."""

from __future__ import annotations

from typing import Protocol

from tx3_sdk.signer.witness import TxWitness


class Signer(Protocol):
    """Represents a signer capable of producing a witness for a tx hash."""

    def address(self) -> str:
        """Returns the address bound to this signer."""

    def sign(self, tx_hash_hex: str) -> TxWitness:
        """Signs the given hex-encoded tx hash and returns a witness."""
