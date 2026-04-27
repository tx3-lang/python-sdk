"""Unit tests for ResolvedTx.add_witness."""

from __future__ import annotations

import pytest

from tx3_sdk import Party, Protocol, Tx3Client
from tx3_sdk.core.bytes import BytesEnvelope
from tx3_sdk.signer.witness import vkey_witness
from tx3_sdk.trp.spec import (
    CheckStatusResponse,
    SubmitResponse,
    TxEnvelope,
    TxStage,
    TxStatus,
    TxWitness,
)


class _RecordingTrp:
    """Mock TRP client that captures the last SubmitParams."""

    def __init__(self) -> None:
        self.captured = None

    async def resolve(self, _params):
        return TxEnvelope(hash="abc", tx="84a40081")

    async def submit(self, params):
        self.captured = params
        return SubmitResponse(hash="abc")

    async def check_status(self, hashes):
        return CheckStatusResponse(
            statuses={
                hashes[0]: TxStatus(
                    stage=TxStage.CONFIRMED, confirmations=1, non_confirmations=0
                )
            }
        )


class _StubSigner:
    def __init__(self, addr: str, witness: TxWitness) -> None:
        self._address = addr
        self._witness = witness

    def address(self) -> str:
        return self._address

    def sign(self, _request) -> TxWitness:
        return self._witness


def _client(trp: _RecordingTrp, *, with_signer: bool = False) -> Tx3Client:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    client = Tx3Client(protocol, trp)
    if with_signer:
        registered = vkey_witness("11", "22")
        client = client.with_party("sender", Party.signer(_StubSigner("addr_sender", registered)))
    else:
        client = client.with_party("sender", Party.address("addr_sender"))
    return (
        client.with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
    )


@pytest.mark.asyncio
async def test_add_witness_only_no_signers() -> None:
    trp = _RecordingTrp()
    client = _client(trp)

    resolved = await client.tx("transfer").arg("quantity", 100).resolve()
    signed = await resolved.add_witness(vkey_witness("aa", "bb")).sign()
    await signed.submit()

    assert len(trp.captured.witnesses) == 1
    assert trp.captured.witnesses[0].key.content == "aa"
    assert trp.captured.witnesses[0].signature.content == "bb"


@pytest.mark.asyncio
async def test_add_witness_mixed_with_registered_signer() -> None:
    trp = _RecordingTrp()
    client = _client(trp, with_signer=True)

    resolved = await client.tx("transfer").arg("quantity", 100).resolve()
    signed = await resolved.add_witness(vkey_witness("aa", "bb")).sign()
    await signed.submit()

    keys = [w.key.content for w in trp.captured.witnesses]
    assert keys == ["11", "aa"]


@pytest.mark.asyncio
async def test_add_witness_preserves_attach_order() -> None:
    trp = _RecordingTrp()
    client = _client(trp)

    resolved = await client.tx("transfer").arg("quantity", 100).resolve()
    chained = (
        resolved.add_witness(vkey_witness("01", "10"))
        .add_witness(vkey_witness("02", "20"))
        .add_witness(vkey_witness("03", "30"))
    )
    signed = await chained.sign()
    await signed.submit()

    keys = [w.key.content for w in trp.captured.witnesses]
    assert keys == ["01", "02", "03"]


@pytest.mark.asyncio
async def test_add_witness_returns_new_instance_immutable() -> None:
    """Frozen dataclass: each add_witness returns a new ResolvedTx; the original is unchanged."""
    trp = _RecordingTrp()
    client = _client(trp)

    original = await client.tx("transfer").arg("quantity", 100).resolve()
    derived = original.add_witness(vkey_witness("aa", "bb"))

    assert derived is not original
    assert len(original.manual_witnesses) == 0
    assert len(derived.manual_witnesses) == 1
    assert derived.manual_witnesses[0].key == BytesEnvelope.hex("aa")
