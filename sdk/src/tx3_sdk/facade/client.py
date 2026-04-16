"""Facade entrypoint for protocol-bound transaction building."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tx3_sdk.facade.builder import TxBuilder
from tx3_sdk.facade.party import Party
from tx3_sdk.tii.protocol import Protocol
from tx3_sdk.trp.client import TrpClient


@dataclass(frozen=True)
class Tx3Client:
    """High-level client that ties protocol, TRP client, and parties together."""

    protocol: Protocol
    trp: TrpClient
    parties: dict[str, Party] = field(default_factory=dict)
    profile: str | None = None

    def with_profile(self, name: str) -> "Tx3Client":
        """Returns a new client with a profile bound to future invocations."""
        return replace(self, profile=name)

    def with_party(self, name: str, party: Party) -> "Tx3Client":
        """Returns a new client with one named party binding."""
        next_parties = dict(self.parties)
        next_parties[name.lower()] = party
        return replace(self, parties=next_parties)

    def with_parties(self, parties: dict[str, Party]) -> "Tx3Client":
        """Returns a new client with multiple named party bindings."""
        next_parties = dict(self.parties)
        for name, party in parties.items():
            next_parties[name.lower()] = party
        return replace(self, parties=next_parties)

    def tx(self, name: str) -> TxBuilder:
        """Starts building an invocation for a transaction name."""
        return TxBuilder(
            protocol=self.protocol,
            trp=self.trp,
            tx_name=name,
            parties=dict(self.parties),
            profile=self.profile,
        )
