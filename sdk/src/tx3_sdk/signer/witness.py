"""Witness model for signer output."""

from __future__ import annotations

from dataclasses import dataclass

from tx3_sdk.core.bytes import BytesEnvelope
from tx3_sdk.trp.spec import TxWitness


@dataclass(frozen=True)
class WitnessInfo:
    """Debug information for a produced witness."""

    public_key: str
    address: str


def vkey_witness(public_key_hex: str, signature_hex: str) -> TxWitness:
    """Creates a `vkey` witness from hex strings."""
    return TxWitness(
        key=BytesEnvelope.hex(public_key_hex),
        signature=BytesEnvelope.hex(signature_hex),
        type="vkey",
    )
