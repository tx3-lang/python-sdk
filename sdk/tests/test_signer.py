import hashlib

import pytest
from bech32 import bech32_encode, convertbits
from nacl.signing import SigningKey, VerifyKey

from tx3_sdk.signer import (
    CardanoSigner,
    Ed25519Signer,
    InvalidHashError,
    InvalidMnemonicError,
    InvalidPrivateKeyError,
)


def test_ed25519_signer_from_hex_signs_known_hash() -> None:
    seed_hex = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    signer = Ed25519Signer.from_hex("addr_test1qz...", seed_hex)
    tx_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    witness = signer.sign(tx_hash)
    assert witness.type == "vkey"

    vk = VerifyKey(bytes.fromhex(witness.key.content))
    vk.verify(bytes.fromhex(tx_hash), bytes.fromhex(witness.signature.content))


def test_ed25519_invalid_private_key_length() -> None:
    with pytest.raises(InvalidPrivateKeyError):
        Ed25519Signer.from_hex("addr", "aabb")


def test_ed25519_invalid_hash_length() -> None:
    signer = Ed25519Signer.from_mnemonic(
        "addr",
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
    )
    with pytest.raises(InvalidHashError):
        signer.sign("aabb")


def test_cardano_signer_from_hex_with_bound_address() -> None:
    seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    verify_key = SigningKey(seed).verify_key
    key_hash = hashlib.blake2b(bytes(verify_key), digest_size=28).digest()
    payload = bytes([0x60]) + key_hash
    words = convertbits(payload, 8, 5, True)
    assert words is not None
    address = bech32_encode("addr_test", words)

    signer = CardanoSigner.from_hex(address=address, private_key_hex=seed.hex())
    witness = signer.sign("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert witness.type == "vkey"


def test_cardano_signer_invalid_mnemonic() -> None:
    with pytest.raises(InvalidMnemonicError):
        CardanoSigner.from_mnemonic("addr_test1...", "not a valid mnemonic")
