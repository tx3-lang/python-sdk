import pytest

from tx3_sdk import Party, PollConfig, Protocol, Tx3Client
from tx3_sdk.core.bytes import BytesEnvelope
from tx3_sdk.facade import (
    FinalizedFailedError,
    FinalizedTimeoutError,
    MissingParamsError,
    SubmitHashMismatchError,
    UnknownArgError,
    UnknownPartyError,
)
from tx3_sdk.trp.spec import (
    CheckStatusResponse,
    SubmitResponse,
    TxEnvelope,
    TxStage,
    TxStatus,
)


class MockSigner:
    def __init__(self, addr: str) -> None:
        self._address = addr

    def address(self) -> str:
        return self._address

    def sign(self, _request):
        from tx3_sdk.trp.spec import TxWitness

        return TxWitness(
            key=BytesEnvelope.hex("aabb"),
            signature=BytesEnvelope.hex("ccdd"),
            type="vkey",
        )


class MockTrpClient:
    def __init__(self) -> None:
        self.resolve_args = None
        self.status_stage = TxStage.CONFIRMED
        self.submit_hash = "abc"

    async def resolve(self, params):
        self.resolve_args = params.args
        return TxEnvelope(hash="abc", tx="deadbeef")

    async def submit(self, params):
        return SubmitResponse(hash=self.submit_hash)

    async def check_status(self, hashes):
        return CheckStatusResponse(
            statuses={
                hashes[0]: TxStatus(
                    stage=self.status_stage,
                    confirmations=1,
                    non_confirmations=0,
                )
            }
        )


@pytest.mark.asyncio
async def test_party_injection_and_full_chain() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    client = (
        Tx3Client(protocol, trp)
        .with_profile("preprod")
        .with_party("sender", Party.signer(MockSigner("addr_sender")))
        .with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
    )

    submitted = await (await (await client.tx("transfer").arg("quantity", 100).resolve()).sign()).submit()
    status = await submitted.wait_for_confirmed(PollConfig.default())

    assert trp.resolve_args["sender"] == "addr_sender"
    assert trp.resolve_args["receiver"] == "addr_receiver"
    assert status.stage == TxStage.CONFIRMED


@pytest.mark.asyncio
async def test_unknown_party_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    client = Tx3Client(protocol, trp).with_party("ghost", Party.address("addr"))

    with pytest.raises(UnknownPartyError):
        await client.tx("transfer").arg("quantity", 1).resolve()


@pytest.mark.asyncio
async def test_unknown_arg_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    client = Tx3Client(protocol, trp)

    with pytest.raises(UnknownArgError):
        await client.tx("transfer").arg("not_a_param", 1).resolve()


@pytest.mark.asyncio
async def test_missing_params_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    client = Tx3Client(protocol, trp)

    with pytest.raises(MissingParamsError):
        await client.tx("transfer").resolve()


@pytest.mark.asyncio
async def test_submit_hash_mismatch_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    trp.submit_hash = "other"
    client = (
        Tx3Client(protocol, trp)
        .with_party("sender", Party.signer(MockSigner("addr_sender")))
        .with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
    )

    resolved = await client.tx("transfer").arg("quantity", 1).resolve()
    signed = await resolved.sign()
    with pytest.raises(SubmitHashMismatchError):
        await signed.submit()


@pytest.mark.asyncio
async def test_wait_for_terminal_failure_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    trp.status_stage = TxStage.DROPPED
    client = (
        Tx3Client(protocol, trp)
        .with_party("sender", Party.signer(MockSigner("addr_sender")))
        .with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
    )

    submitted = await (await (await client.tx("transfer").arg("quantity", 1).resolve()).sign()).submit()
    with pytest.raises(FinalizedFailedError):
        await submitted.wait_for_confirmed(PollConfig(attempts=1, delay_seconds=0))


@pytest.mark.asyncio
async def test_wait_timeout_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    trp = MockTrpClient()
    trp.status_stage = TxStage.PENDING
    client = (
        Tx3Client(protocol, trp)
        .with_party("sender", Party.signer(MockSigner("addr_sender")))
        .with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
    )

    submitted = await (await (await client.tx("transfer").arg("quantity", 1).resolve()).sign()).submit()
    with pytest.raises(FinalizedTimeoutError):
        await submitted.wait_for_confirmed(PollConfig(attempts=1, delay_seconds=0))
