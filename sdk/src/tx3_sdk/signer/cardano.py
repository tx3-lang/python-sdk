"""Cardano signer implementation using CIP-1852 key derivation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from bech32 import bech32_decode, convertbits
from nacl.signing import SigningKey

from tx3_sdk.signer.errors import (
    AddressMismatchError,
    InvalidAddressError,
    InvalidHashError,
    InvalidMnemonicError,
    InvalidPrivateKeyError,
    UnsupportedPaymentCredentialError,
)
from tx3_sdk.signer.witness import vkey_witness
from tx3_sdk.trp.spec import TxWitness


@dataclass(frozen=True)
class CardanoSigner:
    """Cardano signer derived at path `m/1852'/1815'/0'/0/0`."""

    _address: str
    _signing_key: SigningKey
    _public_key: bytes

    @classmethod
    def from_mnemonic(cls, address: str, phrase: str) -> "CardanoSigner":
        """Creates signer by deriving keys from a BIP39 mnemonic phrase."""
        private_key, public_key = _derive_keypair_from_mnemonic(phrase)
        signer = cls(
            _address=address,
            _signing_key=SigningKey(private_key),
            _public_key=public_key,
        )
        signer._verify_address_binding()
        return signer

    @classmethod
    def from_hex(cls, address: str, private_key_hex: str) -> "CardanoSigner":
        """Creates signer from 32-byte seed or 64-byte extended key hex."""
        try:
            raw = bytes.fromhex(private_key_hex)
        except ValueError as exc:
            raise InvalidPrivateKeyError("invalid private key: hex decode failed") from exc
        if len(raw) == 64:
            raw = raw[:32]
        if len(raw) != 32:
            raise InvalidPrivateKeyError(f"invalid private key: expected 32 or 64 bytes, got {len(raw)}")
        signing_key = SigningKey(raw)
        signer = cls(
            _address=address,
            _signing_key=signing_key,
            _public_key=bytes(signing_key.verify_key),
        )
        signer._verify_address_binding()
        return signer

    def address(self) -> str:
        """Returns the signer address."""
        return self._address

    def sign(self, tx_hash_hex: str) -> TxWitness:
        """Signs a tx hash and returns a `vkey` witness."""
        try:
            tx_hash = bytes.fromhex(tx_hash_hex)
        except ValueError as exc:
            raise InvalidHashError("invalid hash: hex decode failed") from exc
        if len(tx_hash) != 32:
            raise InvalidHashError(f"invalid hash: expected 32 bytes, got {len(tx_hash)}")
        signed = self._signing_key.sign(tx_hash)
        return vkey_witness(
            public_key_hex=self._public_key.hex(),
            signature_hex=signed.signature.hex(),
        )

    def _verify_address_binding(self) -> None:
        payment_key_hash = _extract_payment_key_hash(self._address)
        our_hash = hashlib.blake2b(self._public_key, digest_size=28).digest()
        if our_hash != payment_key_hash:
            raise AddressMismatchError("address mismatch: signer key does not match payment credential")


def _derive_keypair_from_mnemonic(phrase: str) -> tuple[bytes, bytes]:
    words = [part for part in phrase.strip().split(" ") if part]
    if len(words) < 12:
        raise InvalidMnemonicError("invalid mnemonic: expected at least 12 words")

    try:
        from bip_utils import Bip39MnemonicValidator, Bip39SeedGenerator, Bip44Changes, Cip1852, Cip1852Coins
    except Exception as exc:  # pragma: no cover - import failure path
        raise InvalidMnemonicError(f"invalid mnemonic: bip-utils unavailable ({exc})") from exc

    validator = Bip39MnemonicValidator()
    if not validator.IsValid(phrase):
        raise InvalidMnemonicError("invalid mnemonic phrase")

    seed = Bip39SeedGenerator(phrase).Generate()
    ctx = Cip1852.FromSeed(seed, Cip1852Coins.CARDANO_ICARUS)
    node = ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    private_key_obj = node.PrivateKey()
    public_key_obj = node.PublicKey()
    key_bytes = _extract_key_bytes(private_key_obj)
    public_key = _extract_public_key_bytes(public_key_obj)
    if len(key_bytes) < 32:
        raise InvalidPrivateKeyError("invalid private key: derived key too short")

    candidates = []
    if len(key_bytes) >= 32:
        candidates.append(key_bytes[:32])
    if len(key_bytes) >= 64:
        candidates.append(key_bytes[32:64])

    for candidate in candidates:
        try:
            if bytes(SigningKey(candidate).verify_key) == public_key:
                return candidate, public_key
        except Exception:
            continue

    return key_bytes[:32], public_key


def _extract_key_bytes(key_obj: Any) -> bytes:
    candidates = [
        lambda obj: obj.Raw().ToBytes(),
        lambda obj: bytes.fromhex(obj.Raw().ToHex()),
        lambda obj: obj.ToBytes(),
        lambda obj: bytes.fromhex(obj.ToHex()),
    ]
    for candidate in candidates:
        try:
            value = candidate(key_obj)
            if isinstance(value, bytes):
                return value
        except Exception:
            continue
    raise InvalidPrivateKeyError("invalid private key: could not extract bytes from key object")


def _extract_public_key_bytes(key_obj: Any) -> bytes:
    candidates = [
        lambda obj: obj.RawCompressed().ToBytes(),
        lambda obj: obj.RawUncompressed().ToBytes(),
        lambda obj: obj.Raw().ToBytes(),
        lambda obj: bytes.fromhex(obj.RawCompressed().ToHex()),
        lambda obj: bytes.fromhex(obj.RawUncompressed().ToHex()),
        lambda obj: bytes.fromhex(obj.Raw().ToHex()),
        lambda obj: obj.ToBytes(),
        lambda obj: bytes.fromhex(obj.ToHex()),
    ]
    for candidate in candidates:
        try:
            value = candidate(key_obj)
            if isinstance(value, bytes):
                if len(value) == 33:
                    return value[1:]
                if len(value) >= 32:
                    return value[:32]
        except Exception:
            continue
    raise InvalidPrivateKeyError("invalid private key: could not extract public key bytes")


def _extract_payment_key_hash(address: str) -> bytes:
    hrp, data = bech32_decode(address)
    if hrp is None or data is None:
        raise InvalidAddressError("invalid address: bech32 decode failed")

    converted = convertbits(data, 5, 8, False)
    if converted is None:
        raise InvalidAddressError("invalid address: bech32 payload conversion failed")
    payload = bytes(converted)
    if len(payload) < 29:
        raise InvalidAddressError("invalid address: payload too short")

    header = payload[0]
    address_type = header >> 4
    if address_type not in {0x00, 0x01, 0x02, 0x03, 0x06, 0x07}:
        raise UnsupportedPaymentCredentialError("unsupported address type")
    if header & 0x10:
        raise UnsupportedPaymentCredentialError("unsupported script payment credential")

    return payload[1:29]
