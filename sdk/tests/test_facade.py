import pytest

from tx3_sdk import (
    Party,
    PollConfig,
    Profile,
    Protocol,
    Tx3Client,
    Tx3ClientBuilder,
)
from tx3_sdk.core.bytes import BytesEnvelope, TirEnvelope
from tx3_sdk.facade import (
    BuilderError,
    FinalizedFailedError,
    FinalizedTimeoutError,
    MissingTrpEndpointError,
    SubmitHashMismatchError,
    UnknownPartyError,
)
from tx3_sdk.tii.errors import UnknownProfileError, UnknownTxError
from tx3_sdk.trp.client import ClientOptions
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


def _load_protocol() -> Protocol:
    return Protocol.from_file("tests/fixtures/transfer.tii")


def _make_builder(trp: MockTrpClient) -> Tx3ClientBuilder:
    return (
        _load_protocol()
        .client()
        ._trp_client(trp)
        .with_profile("preprod")
    )


def _build_client(trp: MockTrpClient) -> Tx3Client:
    return (
        _make_builder(trp)
        .with_party("sender", Party.signer(MockSigner("addr_sender")))
        .with_party("receiver", Party.address("addr_receiver"))
        .with_party("middleman", Party.address("addr_middleman"))
        .build()
    )


def test_protocol_client_returns_builder() -> None:
    assert isinstance(_load_protocol().client(), Tx3ClientBuilder)


def test_build_requires_trp_endpoint() -> None:
    with pytest.raises(MissingTrpEndpointError):
        _load_protocol().client().build()


def test_build_rejects_empty_endpoint() -> None:
    with pytest.raises(MissingTrpEndpointError):
        _load_protocol().client().trp_endpoint("").build()


def test_build_rejects_unknown_profile() -> None:
    with pytest.raises(UnknownProfileError):
        (
            _load_protocol()
            .client()
            .trp_endpoint("http://localhost:9999")
            .with_profile("not-a-profile")
            .build()
        )


def test_build_rejects_unknown_party() -> None:
    with pytest.raises(UnknownPartyError):
        (
            _make_builder(MockTrpClient())
            .with_party("stranger", Party.address("addr_stranger"))
            .build()
        )


def test_with_party_unchecked_bypasses_validation() -> None:
    client = (
        _make_builder(MockTrpClient())
        .with_party_unchecked("stranger", Party.address("addr_stranger"))
        .build()
    )
    assert isinstance(client, Tx3Client)


def test_built_client_has_no_with_profile() -> None:
    client = _build_client(MockTrpClient())
    assert not hasattr(client, "with_profile")


def test_built_client_with_party_validates() -> None:
    client = _build_client(MockTrpClient())
    with pytest.raises(UnknownPartyError):
        client.with_party("ghost", Party.address("addr_ghost"))


def test_missing_trp_endpoint_is_builder_error() -> None:
    err = MissingTrpEndpointError()
    assert isinstance(err, BuilderError)


@pytest.mark.asyncio
async def test_full_chain_party_injection() -> None:
    trp = MockTrpClient()
    client = _build_client(trp)

    submitted = await (
        await (await client.tx("transfer").arg("quantity", 100).resolve()).sign()
    ).submit()
    status = await submitted.wait_for_confirmed(PollConfig.default())

    assert trp.resolve_args["sender"] == "addr_sender"
    assert trp.resolve_args["receiver"] == "addr_receiver"
    assert status.stage == TxStage.CONFIRMED


@pytest.mark.asyncio
async def test_with_env_value_overrides_profile_env() -> None:
    trp = MockTrpClient()
    client = (
        _make_builder(trp)
        .with_party_unchecked("sender", Party.address("addr_sender"))
        .with_party_unchecked("receiver", Party.address("addr_receiver"))
        .with_party_unchecked("middleman", Party.address("addr_middleman"))
        .with_env_value("tax", 999)
        .build()
    )

    await client.tx("transfer").arg("quantity", 100).resolve()
    assert trp.resolve_args["tax"] == 999


@pytest.mark.asyncio
async def test_tx_unknown_raises() -> None:
    client = _build_client(MockTrpClient())
    with pytest.raises(UnknownTxError):
        client.tx("not-a-tx")


@pytest.mark.asyncio
async def test_from_parts_codegen_flow() -> None:
    trp = MockTrpClient()
    protocol = _load_protocol()
    transactions: dict[str, TirEnvelope] = {
        name: TirEnvelope(
            content=str(tx["tir"]["content"]),
            encoding=str(tx["tir"]["encoding"]),
            version=str(tx["tir"]["version"]),
        )
        for name, tx in protocol.transactions.items()
    }

    client = (
        Tx3ClientBuilder.from_parts(transactions, {}, [])
        ._trp_client(trp)
        .with_party_unchecked("sender", Party.address("addr_sender"))
        .with_party_unchecked("receiver", Party.address("addr_receiver"))
        .with_party_unchecked("middleman", Party.address("addr_middleman"))
        .build()
    )

    resolved = await client.tx("transfer").arg("quantity", 100).resolve()
    assert resolved.hash == "abc"


@pytest.mark.asyncio
async def test_submit_hash_mismatch_raises() -> None:
    trp = MockTrpClient()
    trp.submit_hash = "other"
    client = _build_client(trp)

    resolved = await client.tx("transfer").arg("quantity", 1).resolve()
    signed = await resolved.sign()
    with pytest.raises(SubmitHashMismatchError):
        await signed.submit()


@pytest.mark.asyncio
async def test_wait_for_terminal_failure_raises() -> None:
    trp = MockTrpClient()
    trp.status_stage = TxStage.DROPPED
    client = _build_client(trp)

    submitted = await (
        await (await client.tx("transfer").arg("quantity", 1).resolve()).sign()
    ).submit()
    with pytest.raises(FinalizedFailedError):
        await submitted.wait_for_confirmed(PollConfig(attempts=1, delay_seconds=0))


@pytest.mark.asyncio
async def test_wait_timeout_raises() -> None:
    trp = MockTrpClient()
    trp.status_stage = TxStage.PENDING
    client = _build_client(trp)

    submitted = await (
        await (await client.tx("transfer").arg("quantity", 1).resolve()).sign()
    ).submit()
    with pytest.raises(FinalizedTimeoutError):
        await submitted.wait_for_confirmed(PollConfig(attempts=1, delay_seconds=0))


def test_top_level_reexports_include_builder() -> None:
    import tx3_sdk

    assert tx3_sdk.Tx3ClientBuilder is Tx3ClientBuilder
    assert tx3_sdk.Profile is Profile
    assert tx3_sdk.MissingTrpEndpointError is MissingTrpEndpointError
    assert tx3_sdk.BuilderError is BuilderError
