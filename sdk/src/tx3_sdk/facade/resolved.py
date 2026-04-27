"""Resolved transaction model and signing step."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from tx3_sdk.facade.signed import SignedTx
from tx3_sdk.signer.signer import SignRequest
from tx3_sdk.signer.witness import WitnessInfo
from tx3_sdk.trp.client import TrpClient
from tx3_sdk.trp.spec import SubmitParams, TxWitness
from tx3_sdk.core.bytes import BytesEnvelope


@dataclass(frozen=True)
class ResolvedTx:
    """Output of `TxBuilder.resolve`, ready for signing."""

    trp: TrpClient
    hash: str
    tx_hex: str
    signers: list[tuple[str, object]]
    manual_witnesses: list[TxWitness] = field(default_factory=list)

    @property
    def signing_hash(self) -> str:
        """Returns hash that signer parties must sign."""
        return self.hash

    def add_witness(self, witness: TxWitness) -> "ResolvedTx":
        """Attaches a pre-computed witness produced outside any registered signer.

        Canonical entry point for wallet-app integrations: hand `tx_hex` (or
        `hash`) to an external wallet, get back a witness, attach it before
        calling `sign()`. The witness is appended to the TRP
        `SubmitParams.witnesses` array after any witnesses produced by
        registered signer parties, in attach order.

        Returns a new `ResolvedTx` (the dataclass is frozen). May be called any
        number of times. The SDK does not verify the witness against the tx
        hash; that binding is enforced by TRP at submit time.
        """
        return dataclasses.replace(
            self,
            manual_witnesses=[*self.manual_witnesses, witness],
        )

    async def sign(self) -> SignedTx:
        """Signs resolved tx with all configured signer parties.

        Manually attached witnesses (see `add_witness`) are appended after the
        registered-signer witnesses, in attach order. Succeeds with zero
        registered signers when at least one witness has been manually attached.
        """
        witnesses = []
        witness_info: list[WitnessInfo] = []
        request = SignRequest(tx_hash_hex=self.hash, tx_cbor_hex=self.tx_hex)
        for _, signer in self.signers:
            witness = signer.sign(request)
            witnesses.append(witness)
            witness_info.append(
                WitnessInfo(public_key=witness.key.content, address=signer.address())
            )

        for manual in self.manual_witnesses:
            witnesses.append(manual)
            witness_info.append(
                WitnessInfo(public_key=manual.key.content, address="")
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
