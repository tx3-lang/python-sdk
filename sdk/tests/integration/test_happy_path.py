import os

import pytest

from tx3_sdk import CardanoSigner, Party, PollConfig, Protocol, TrpClient, Tx3Client


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} not set, skipping integration test")
    return value


@pytest.mark.asyncio
@pytest.mark.integration
async def test_integration_happy_path() -> None:
    endpoint = _require_env("TRP_ENDPOINT_PREPROD")
    api_key = os.getenv("TRP_API_KEY_PREPROD", "")
    party_a_address = _require_env("TEST_PARTY_A_ADDRESS")
    party_a_mnemonic = _require_env("TEST_PARTY_A_MNEMONIC")

    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    headers = {"dmtr-api-key": api_key} if api_key else {}
    trp = TrpClient(endpoint=endpoint, headers=headers)
    signer = CardanoSigner.from_mnemonic(address=party_a_address, phrase=party_a_mnemonic)

    party_b_address = os.getenv("TEST_PARTY_B_ADDRESS", party_a_address)
    _party_b_mnemonic = os.getenv("TEST_PARTY_B_MNEMONIC", party_a_mnemonic)

    client = (
        Tx3Client(protocol, trp)
        .with_profile("preprod")
        .with_party("sender", Party.signer(signer))
        .with_party("receiver", Party.address(party_b_address))
        .with_party("middleman", Party.address(party_b_address))
    )

    submitted = await (
        await (
            await client.tx("transfer").arg("quantity", 10_000_000).resolve()
        ).sign()
    ).submit()

    status = await submitted.wait_for_confirmed(PollConfig.default())
    assert status.stage.value in {"confirmed", "finalized"}

    await trp.close()
