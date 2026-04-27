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
from tx3_sdk.signer.signer import SignRequest
from tx3_sdk.signer.witness import vkey_witness
from tx3_sdk.trp.spec import TxWitness


@dataclass(frozen=True)
class CardanoSigner:
    """Cardano signer derived at path `m/1852'/1815'/0'/0/0`."""

    _address: str
    _public_key: bytes
    _signing_key: SigningKey | None = None
    _extended_secret: bytes | None = None

    @classmethod
    def from_mnemonic(cls, address: str, phrase: str) -> "CardanoSigner":
        """Creates signer by deriving keys from a BIP39 mnemonic phrase."""
        extended_secret, public_key = _derive_keypair_from_mnemonic(phrase)
        signer = cls(
            _address=address,
            _public_key=public_key,
            _extended_secret=extended_secret,
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
            _public_key=bytes(signing_key.verify_key),
            _signing_key=signing_key,
        )
        signer._verify_address_binding()
        return signer

    def address(self) -> str:
        """Returns the signer address."""
        return self._address

    def sign(self, request: SignRequest) -> TxWitness:
        """Signs the request's tx hash and returns a `vkey` witness."""
        try:
            tx_hash = bytes.fromhex(request.tx_hash_hex)
        except ValueError as exc:
            raise InvalidHashError("invalid hash: hex decode failed") from exc
        if len(tx_hash) != 32:
            raise InvalidHashError(f"invalid hash: expected 32 bytes, got {len(tx_hash)}")
        if self._extended_secret is not None:
            signature = _extended_sign(self._extended_secret, self._public_key, tx_hash)
            return vkey_witness(
                public_key_hex=self._public_key.hex(),
                signature_hex=signature.hex(),
            )

        if self._signing_key is None:
            raise InvalidPrivateKeyError("invalid private key: signer is not initialized")

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
        from bip_utils import Bip39MnemonicValidator, CardanoIcarusBip32, CardanoIcarusSeedGenerator
    except Exception as exc:  # pragma: no cover - import failure path
        raise InvalidMnemonicError(f"invalid mnemonic: bip-utils unavailable ({exc})") from exc

    validator = Bip39MnemonicValidator()
    if not validator.IsValid(phrase):
        raise InvalidMnemonicError("invalid mnemonic phrase")

    hardened = 0x80000000

    seed = CardanoIcarusSeedGenerator(phrase).Generate()
    node = (
        CardanoIcarusBip32.FromSeed(seed)
        .ChildKey(hardened | 1852)
        .ChildKey(hardened | 1815)
        .ChildKey(hardened | 0)
        .ChildKey(0)
        .ChildKey(0)
    )

    extended_secret = _extract_key_bytes(node.PrivateKey())
    public_key = _extract_public_key_bytes(node.PublicKey())

    if len(extended_secret) != 64:
        raise InvalidPrivateKeyError(
            f"invalid private key: expected 64-byte extended secret, got {len(extended_secret)}"
        )

    return extended_secret, public_key


def _extended_sign(extended_secret: bytes, public_key: bytes, message: bytes) -> bytes:
    if len(extended_secret) != 64:
        raise InvalidPrivateKeyError("invalid private key: expected 64-byte extended secret")

    try:
        from bip_utils.ecc.ed25519.lib import ed25519_lib
    except Exception as exc:  # pragma: no cover - import failure path
        raise InvalidPrivateKeyError(f"invalid private key: signing backend unavailable ({exc})") from exc

    group_order = 2**252 + 27742317777372353535851937790883648493

    r_digest = hashlib.sha512(extended_secret[32:] + message).digest()
    r = int.from_bytes(ed25519_lib.scalar_reduce(r_digest), "little")
    r_point = ed25519_lib.point_scalar_mul_base(r)

    hram_digest = hashlib.sha512(r_point + public_key + message).digest()
    hram = int.from_bytes(ed25519_lib.scalar_reduce(hram_digest), "little")

    left = bytearray(extended_secret[:32])
    left[0] &= 0xF8
    left[31] &= 0x3F
    left[31] |= 0x40
    a = int.from_bytes(left, "little")

    s = (r + (hram * a)) % group_order
    return r_point + s.to_bytes(32, "little")


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
