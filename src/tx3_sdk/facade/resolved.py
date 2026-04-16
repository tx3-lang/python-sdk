"""Resolved transaction model and signing step."""

from __future__ import annotations

from dataclasses import dataclass

from tx3_sdk.facade.signed import SignedTx
from tx3_sdk.signer.witness import WitnessInfo
from tx3_sdk.trp.client import TrpClient
from tx3_sdk.trp.spec import SubmitParams
from tx3_sdk.core.bytes import BytesEnvelope


@dataclass(frozen=True)
class ResolvedTx:
    """Output of `TxBuilder.resolve`, ready for signing."""

    trp: TrpClient
    hash: str
    tx_hex: str
    signers: list[tuple[str, object]]

    @property
    def signing_hash(self) -> str:
        """Returns hash that signer parties must sign."""
        return self.hash

    async def sign(self) -> SignedTx:
        """Signs resolved tx with all configured signer parties."""
        witnesses = []
        witness_info: list[WitnessInfo] = []
        for _, signer in self.signers:
            witness = signer.sign(self.hash)
            witnesses.append(witness)
            witness_info.append(
                WitnessInfo(public_key=witness.key.content, address=signer.address())
            )

        submit_params = SubmitParams(
            tx=BytesEnvelope.hex(self.tx_hex),
            witnesses=witnesses,
        )
        return SignedTx(
            trp=self.trp,
            hash=self.hash,
            submit_params=submit_params,
            witness_info=witness_info,
        )
