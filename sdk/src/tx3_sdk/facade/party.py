"""Party constructors used by `Tx3Client.with_party`."""

from __future__ import annotations

from dataclasses import dataclass

from tx3_sdk.signer.signer import Signer


@dataclass(frozen=True)
class Party:
    """Represents a transaction party as address-only or signer-backed."""

    _address: str | None = None
    _signer: Signer | None = None

    @staticmethod
    def address(address: str) -> "Party":
        """Creates a read-only party with a fixed address."""
        return Party(_address=address)

    @staticmethod
    def signer(signer: Signer) -> "Party":
        """Creates a signer-backed party whose address comes from the signer."""
        return Party(_signer=signer)

    @property
    def is_signer(self) -> bool:
        """Returns true if this party provides signing capability."""
        return self._signer is not None

    @property
    def signer_impl(self) -> Signer | None:
        """Returns the signer implementation, if present."""
        return self._signer

    def party_address(self) -> str:
        """Returns party address, using signer address when signer-backed."""
        if self._signer is not None:
            return self._signer.address()
        if self._address is None:
            raise ValueError("party has no address")
        return self._address
