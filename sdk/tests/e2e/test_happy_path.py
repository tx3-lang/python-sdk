import os

import pytest

from tx3_sdk import CardanoSigner, Party, PollConfig, Protocol


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} not set, skipping e2e test")
    return value


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_e2e_happy_path() -> None:
    endpoint = _require_env("TRP_ENDPOINT_PREPROD")
    api_key = os.getenv("TRP_API_KEY_PREPROD", "")
    party_a_address = _require_env("TEST_PARTY_A_ADDRESS")
    party_a_mnemonic = _require_env("TEST_PARTY_A_MNEMONIC")

    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    signer = CardanoSigner.from_mnemonic(address=party_a_address, phrase=party_a_mnemonic)

    party_b_address = os.getenv("TEST_PARTY_B_ADDRESS", party_a_address)
    _party_b_mnemonic = os.getenv("TEST_PARTY_B_MNEMONIC", party_a_mnemonic)

    builder = (
        protocol.client()
        .trp_endpoint(endpoint)
        .with_profile("preprod")
    )

    if api_key:
        builder = builder.with_header("dmtr-api-key", api_key)

    client = (
        builder.with_party("sender", Party.signer(signer))
        .with_party("receiver", Party.address(party_b_address))
        .with_party("middleman", Party.address(party_b_address))
        .build()
    )

    submitted = await (
        await (
            await client.tx("transfer").arg("quantity", 10_000_000).resolve()
        ).sign()
    ).submit()

    status = await submitted.wait_for_confirmed(PollConfig.default())
    assert status.stage.value in {"confirmed", "finalized"}
