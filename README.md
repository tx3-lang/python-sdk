# tx3-sdk (Python)

[![PyPI](https://img.shields.io/pypi/v/tx3-sdk.svg)](https://pypi.org/project/tx3-sdk/)
[![CI](https://github.com/tx3-lang/python-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/tx3-lang/python-sdk/actions/workflows/ci.yml)
[![Tx3 docs](https://img.shields.io/badge/Tx3-docs-blue.svg)](https://docs.txpipe.io/tx3)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

The official Python SDK for [Tx3](https://docs.txpipe.io/tx3): a DSL and protocol suite for
defining and executing UTxO-based blockchain transactions declaratively. Load a
compiled `.tii` protocol, bind parties and signers, and drive the full
transaction lifecycle (`resolve -> sign -> submit -> wait`) through TRP.

This repository is organized as a monorepo. The publishable Python package lives in `sdk/`.

## What is Tx3

Tx3 is a domain-specific language and protocol suite for declarative, type-safe UTxO transactions. Authors write `.tx3` files describing parties, environment, and transactions; the toolchain compiles them to `.tii` artifacts that this SDK loads at runtime to drive the resolve → sign → submit → wait lifecycle through a TRP server. See the [Tx3 docs](https://docs.txpipe.io/tx3) for project context.

## Installation

```bash
pip install tx3-sdk
```

## Quick start

```python
import asyncio

from tx3_sdk import CardanoSigner, Party, PollConfig, Protocol


async def main() -> None:
    # 1) Load a compiled .tii protocol
    protocol = Protocol.from_file("examples/transfer.tii")

    # 2) Build a client: configure TRP, profile, and parties on the builder
    sender_signer = CardanoSigner.from_mnemonic(
        address="addr_test1qz...",
        phrase="word1 word2 ... word24",
    )

    client = (
        protocol.client()
        .trp_endpoint("https://preprod.trp.tx3.dev")
        .with_profile("preprod")
        .with_party("sender", Party.signer(sender_signer))
        .with_party("receiver", Party.address("addr_test1qz..."))
        .build()
    )

    # 3) Build, resolve, sign, submit
    submitted = await (
        await (
            await client.tx("transfer").arg("quantity", 10_000_000).resolve()
        ).sign()
    ).submit()

    # 4) Wait for confirmation
    status = await submitted.wait_for_confirmed(PollConfig.default())
    print(f"Confirmed at stage: {status.stage}")


asyncio.run(main())
```

All fallible validation — TRP endpoint present, profile declared, every bound
party declared — happens inside `build()`, which raises `MissingTrpEndpointError`,
`UnknownProfileError`, or `UnknownPartyError` (all under the `BuilderError` family,
rooted at `Tx3Error`). Optional setters never raise, so chains stay fluent. Profile
selection is **builder-only**: there is no profile-switching method on the built
client. Switching profiles requires a new builder.

## Concepts

| SDK Type | Glossary Term | Description |
|---|---|---|
| `Protocol` | TII / Protocol | Loaded `.tii` with transactions, parties, and profiles. `protocol.client()` returns a fresh `Tx3ClientBuilder` |
| `Tx3ClientBuilder` | Client builder | Fluent builder seeded by `Protocol.client()` or `Tx3ClientBuilder.from_parts(...)`; absorbs all fallible validation in `build()` |
| `Tx3Client` | Facade | Output of `Tx3ClientBuilder.build()` — owns the deconstructed protocol parts, TRP client, profile, and party bindings |
| `TxBuilder` | Invocation builder | Source-agnostic; collects args and resolves transactions |
| `Party` | Party | `Party.address(...)` or `Party.signer(...)` |
| `Profile` | Profile | `{ environment, parties }` value baked into the client; embedded by codegen plugins, decomposed from `Protocol` by `from_protocol` |
| `MissingTrpEndpointError` / `UnknownPartyError` | Builder errors | Raised by `build()`; subclass of `BuilderError`, rooted at `Tx3Error` |
| `Signer` | Signer | Protocol producing a `TxWitness` for a `SignRequest` |
| `SignRequest` | SignRequest | Input passed to `Signer.sign`: `tx_hash_hex` + `tx_cbor_hex` |
| `CardanoSigner` | Cardano Signer | BIP32-Ed25519 signer at `m/1852'/1815'/0'/0/0` |
| `Ed25519Signer` | Ed25519 Signer | Generic raw-key Ed25519 signer |
| `ResolvedTx` | Resolved transaction | Output of `resolve()`, ready for signing |
| `SignedTx` | Signed transaction | Output of `sign()`, ready for submission |
| `SubmittedTx` | Submitted transaction | Output of `submit()`, pollable for status |
| `PollConfig` | Poll configuration | Poll attempts and delay for wait modes |

## Advanced usage

### Skipping the runtime `.tii` (codegen flow)

If you've run `trix codegen` to generate typed bindings, your generated `Client`
embeds the per-transaction TIR envelopes and per-profile data at codegen time —
no `.tii` artifact at runtime. Under the hood it seeds the same builder via
`Tx3ClientBuilder.from_parts(transactions, profiles, known_parties)` and routes
typed per-party setters through `with_party_unchecked`. You can also call
`from_parts` directly from hand-written code:

```python
from tx3_sdk import ClientOptions, Party, Tx3ClientBuilder

client = (
    Tx3ClientBuilder.from_parts(transactions, profiles, ["sender", "receiver"])
    .trp(ClientOptions(endpoint="http://localhost:8000"))
    .with_party_unchecked("sender", Party.signer(signer))
    .build()
)
```

### Low-level TRP client

```python
from tx3_sdk import TrpClient
from tx3_sdk.trp import ResolveParams

trp = TrpClient(endpoint="http://localhost:8000", headers={"Authorization": "Bearer token"})
envelope = await trp.resolve(ResolveParams(tir=..., args={"quantity": 100}))
```

### Custom Signer

Implement the `Signer` protocol. `sign` receives a `SignRequest` carrying both
the tx hash and the full tx CBOR; hash-based signers read `tx_hash_hex`,
tx-based signers (e.g. wallet bridges) read `tx_cbor_hex`.

```python
from tx3_sdk import SignRequest, Signer
from tx3_sdk.signer import TxWitness
from tx3_sdk.signer.witness import vkey_witness


class MySigner(Signer):
    def address(self) -> str:
        return "addr_test1..."

    def sign(self, request: SignRequest) -> TxWitness:
        # sign request.tx_hash_hex with your key
        return vkey_witness(public_key_hex="aabb", signature_hex="ccdd")
```

### Manual witness attachment

When a witness is produced outside any registered signer — for example by an
external wallet app or a remote signing service — resolve the transaction
first, hand the resolved hash (or full tx CBOR) to the wallet, then attach
the returned witness before `sign()`:

```python
from tx3_sdk.signer.witness import vkey_witness

resolved = await client.tx("transfer").arg("quantity", 10_000_000).resolve()

# Hand resolved.hash (or resolved.tx_hex) to the external wallet and get
# back a witness. The wallet needs the resolved tx to sign.
witness = vkey_witness(public_key_hex="aabb", signature_hex="ccdd")  # sign resolved.hash with external wallet

signed = await resolved.add_witness(witness).sign()
submitted = await signed.submit()
```

`add_witness` may be called any number of times; manual witnesses are appended after registered-signer witnesses in attach order. Note: `ResolvedTx` is a frozen dataclass, so `add_witness` returns a new instance.

## Tx3 protocol compatibility

- TRP protocol version: `v1beta0`
- TII schema version: `v1beta0`

## Testing

- Tests follow Python's idiomatic centralized layout under `sdk/tests/`.
- End-to-end (e2e) tests are marked with `@pytest.mark.e2e` and selected by marker.

```bash
# from python-sdk/sdk
pytest -m "not e2e"
pytest tests/e2e -m e2e
```

## License

Apache-2.0
