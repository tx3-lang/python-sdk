"""Invocation builder for resolve step of facade flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tx3_sdk.core.args import coerce_arg, normalize_arg_key
from tx3_sdk.facade.errors import MissingParamsError, UnknownArgError, UnknownPartyError
from tx3_sdk.facade.party import Party
from tx3_sdk.facade.resolved import ResolvedTx
from tx3_sdk.signer.signer import Signer
from tx3_sdk.tii.errors import MissingParamsError as TiiMissingParamsError
from tx3_sdk.tii.protocol import Protocol
from tx3_sdk.trp.client import TrpClient
from tx3_sdk.trp.spec import ResolveParams


@dataclass
class TxBuilder:
    """Collects args and resolves a transaction through TRP."""

    protocol: Protocol
    trp: TrpClient
    tx_name: str
    parties: dict[str, Party]
    profile: str | None = None
    _args: dict[str, Any] = field(default_factory=dict)

    def arg(self, name: str, value: Any) -> "TxBuilder":
        """Sets one arg by key, with case-insensitive key matching."""
        self._args[normalize_arg_key(name)] = coerce_arg(value)
        return self

    def args(self, values: dict[str, Any]) -> "TxBuilder":
        """Sets multiple args at once."""
        for key, value in values.items():
            self.arg(key, value)
        return self

    async def resolve(self) -> ResolvedTx:
        """Resolves this invocation via TRP and returns a `ResolvedTx`."""
        invocation = self.protocol.invoke(self.tx_name, self.profile)
        protocol_parties = {key.lower() for key in self.protocol.parties.keys()}

        signers: list[tuple[str, Signer]] = []
        for name, party in self.parties.items():
            if name.lower() not in protocol_parties:
                raise UnknownPartyError(name)
            invocation.set_arg(name, party.party_address())
            if party.is_signer and party.signer_impl is not None:
                signers.append((name, party.signer_impl))

        param_keys = {name.lower() for name in invocation.params.keys()}
        for key, value in self._args.items():
            if key not in param_keys:
                raise UnknownArgError(key)
            invocation.set_arg(key, value)

        try:
            tir, args = invocation.into_resolve_request()
        except TiiMissingParamsError as exc:
            raise MissingParamsError(exc.params) from exc

        envelope = await self.trp.resolve(ResolveParams(tir=tir, args=args))
        return ResolvedTx(
            trp=self.trp,
            hash=envelope.hash,
            tx_hex=envelope.tx,
            signers=signers,
        )
