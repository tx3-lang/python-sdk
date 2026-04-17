# tx3-sdk (Python)

[![PyPI](https://img.shields.io/pypi/v/tx3-sdk.svg)](https://pypi.org/project/tx3-sdk/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

The official Python SDK for [Tx3](https://tx3.land): a DSL and protocol suite for
defining and executing UTxO-based blockchain transactions declaratively. Load a
compiled `.tii` protocol, bind parties and signers, and drive the full
transaction lifecycle (`resolve -> sign -> submit -> wait`) through TRP.

This repository is organized as a monorepo. The publishable Python package lives in `sdk/`.

## Installation

```bash
pip install tx3-sdk
```

## Quick start

```python
import asyncio

from tx3_sdk import CardanoSigner, Party, PollConfig, Protocol, TrpClient, Tx3Client


async def main() -> None:
    # 1) Load a compiled .tii protocol
    protocol = Protocol.from_file("examples/transfer.tii")

    # 2) Create a low-level TRP client
    trp = TrpClient(endpoint="https://preprod.trp.tx3.dev")

    # 3) Configure signer and parties
    sender_signer = CardanoSigner.from_mnemonic(
        address="addr_test1qz...",
        phrase="word1 word2 ... word24",
    )

    client = (
        Tx3Client(protocol, trp)
        .with_profile("preprod")
        .with_party("sender", Party.signer(sender_signer))
        .with_party("receiver", Party.address("addr_test1qz..."))
    )

    # 4) Build, resolve, sign, submit
    submitted = await (
        await (
            await client.tx("transfer").arg("quantity", 10_000_000).resolve()
        ).sign()
    ).submit()

    # 5) Wait for confirmation
    status = await submitted.wait_for_confirmed(PollConfig.default())
    print(f"Confirmed at stage: {status.stage}")


asyncio.run(main())
```

## Concepts

| SDK Type | Glossary Term | Description |
|---|---|---|
| `Protocol` | TII / Protocol | Loaded `.tii` with transactions, parties, and profiles |
| `Tx3Client` | Facade | High-level client holding protocol + TRP + party bindings |
| `TxBuilder` | Invocation builder | Collects args and resolves transactions |
| `Party` | Party | `Party.address(...)` or `Party.signer(...)` |
| `Signer` | Signer | Interface for witness-producing signing implementations |
| `ResolvedTx` | Resolved transaction | Output of `resolve()`, ready for signing |
| `SignedTx` | Signed transaction | Output of `sign()`, ready for submission |
| `SubmittedTx` | Submitted transaction | Output of `submit()`, pollable for status |
| `PollConfig` | Poll configuration | Poll attempts and delay for wait modes |

## Advanced usage

### Low-level TRP client

```python
from tx3_sdk import TrpClient
from tx3_sdk.trp import ResolveParams

trp = TrpClient(endpoint="http://localhost:8000", headers={"Authorization": "Bearer token"})
envelope = await trp.resolve(ResolveParams(tir=..., args={"quantity": 100}))
```

### Custom Signer

```python
from tx3_sdk import Signer
from tx3_sdk.signer import TxWitness


class MySigner(Signer):
    def address(self) -> str:
        return "addr_test1..."

    def sign(self, tx_hash_hex: str) -> TxWitness:
        return TxWitness.vkey(public_key_hex="aabb", signature_hex="ccdd")
```

## Tx3 protocol compatibility

- TRP protocol version: `v1beta0`
- TII schema version: `v1beta0`

## Testing

- Tests follow Python's idiomatic centralized layout under `sdk/tests/`.
- Integration tests are marked with `@pytest.mark.integration` and selected by marker.

```bash
# from python-sdk/sdk
pytest -m "not integration"
pytest tests/integration -m integration
```

## License

Apache-2.0
