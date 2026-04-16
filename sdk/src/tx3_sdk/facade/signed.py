"""Signed transaction model and submit step."""

from __future__ import annotations

from dataclasses import dataclass

from tx3_sdk.facade.errors import SubmitHashMismatchError
from tx3_sdk.facade.submitted import SubmittedTx
from tx3_sdk.signer.witness import WitnessInfo
from tx3_sdk.trp.client import TrpClient
from tx3_sdk.trp.spec import SubmitParams


@dataclass(frozen=True)
class SignedTx:
    """Output of `ResolvedTx.sign`, ready for submission."""

    trp: TrpClient
    hash: str
    submit_params: SubmitParams
    witness_info: list[WitnessInfo]

    async def submit(self) -> SubmittedTx:
        """Submits a signed transaction to TRP."""
        response = await self.trp.submit(self.submit_params)
        if response.hash != self.hash:
            raise SubmitHashMismatchError(expected=self.hash, received=response.hash)
        return SubmittedTx(trp=self.trp, hash=response.hash)

    def witnesses(self) -> list[WitnessInfo]:
        """Returns witness diagnostics for the signing step."""
        return list(self.witness_info)
