"""Source-agnostic transaction invocation builder."""

from __future__ import annotations

from typing import Any, Iterable

from tx3_sdk.core.args import coerce_arg, normalize_arg_key
from tx3_sdk.core.bytes import TirEnvelope
from tx3_sdk.facade.party import Party
from tx3_sdk.facade.resolved import ResolvedTx
from tx3_sdk.signer.signer import Signer
from tx3_sdk.trp.spec import ResolveParams


class TxBuilder:
    """Builder for transaction invocation.

    Holds the resolve inputs directly: the TIR envelope, the environment values
    from the selected profile (with builder-supplied overrides already folded
    in), the bound parties, and the typed args. Drives a single `resolve()`
    path regardless of whether the upstream was a runtime-loaded `Protocol` or
    codegen-embedded fragments.
    """

    def __init__(self, trp: Any, tir: TirEnvelope) -> None:
        self._trp = trp
        self._tir = tir
        self._env: dict[str, Any] = {}
        self._parties: dict[str, Party] = {}
        self._args: dict[str, Any] = {}

    def env(self, env: dict[str, Any]) -> "TxBuilder":
        """Sets the environment values applied to this transaction."""
        self._env = dict(env)
        return self

    def parties(
        self, parties: Iterable[tuple[str, Party]] | dict[str, Party]
    ) -> "TxBuilder":
        """Attaches party definitions (case-insensitive names)."""
        items = parties.items() if isinstance(parties, dict) else parties
        for name, party in items:
            self._parties[name.lower()] = party
        return self

    def arg(self, name: str, value: Any) -> "TxBuilder":
        """Adds a single argument (case-insensitive name)."""
        self._args[normalize_arg_key(name)] = coerce_arg(value)
        return self

    def args(self, values: dict[str, Any]) -> "TxBuilder":
        """Adds multiple arguments at once."""
        for key, value in values.items():
            self.arg(key, value)
        return self

    async def resolve(self) -> ResolvedTx:
        """Resolves the transaction through the TRP client."""
        merged: dict[str, Any] = {}
        merged.update(self._env)
        for name, party in self._parties.items():
            merged[name] = party.party_address()
        merged.update(self._args)

        envelope = await self._trp.resolve(
            ResolveParams(tir=self._tir, args=merged)
        )

        signers: list[tuple[str, Signer]] = []
        for name, party in self._parties.items():
            if party.is_signer and party.signer_impl is not None:
                signers.append((name, party.signer_impl))

        return ResolvedTx(
            trp=self._trp,
            hash=envelope.hash,
            tx_hex=envelope.tx,
            signers=signers,
        )
