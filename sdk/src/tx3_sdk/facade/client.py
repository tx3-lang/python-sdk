"""High-level facade client for a Tx3 protocol."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Union

from tx3_sdk.core.bytes import TirEnvelope
from tx3_sdk.facade.builder import TxBuilder
from tx3_sdk.facade.errors import UnknownPartyError
from tx3_sdk.facade.party import Party
from tx3_sdk.facade.profile import Profile
from tx3_sdk.tii.errors import UnknownTxError


class Tx3Client:
    """High-level client over a Tx3 protocol.

    Holds the deconstructed protocol parts — per-transaction TIR envelopes,
    the set of declared party names, the selected profile — plus the runtime
    state (TRP client, bound parties, env overrides). Built through
    `Tx3ClientBuilder` (obtained via `Protocol.client()` or
    `Tx3ClientBuilder.from_parts(...)`). Profile selection is locked in at
    build time: there is no profile-switching method on the built client.
    """

    def __init__(
        self,
        transactions: Mapping[str, TirEnvelope],
        known_parties: Iterable[str],
        trp: Any,
        bound_parties: Mapping[str, Party] | None = None,
        selected_profile: Profile | None = None,
        env_overrides: Mapping[str, Any] | None = None,
    ) -> None:
        self._transactions: dict[str, TirEnvelope] = dict(transactions)
        self._known_parties: set[str] = {name.lower() for name in known_parties}
        self._trp = trp
        self._bound_parties: dict[str, Party] = (
            dict(bound_parties) if bound_parties is not None else {}
        )
        self._selected_profile = selected_profile
        self._env_overrides: dict[str, Any] = (
            dict(env_overrides) if env_overrides is not None else {}
        )

    @classmethod
    def _from_builder(
        cls,
        transactions: Mapping[str, TirEnvelope],
        known_parties: Iterable[str],
        trp: Any,
        bound_parties: Mapping[str, Party],
        selected_profile: Profile | None,
        env_overrides: Mapping[str, Any],
    ) -> "Tx3Client":
        """Internal — call site is `Tx3ClientBuilder.build()`."""
        return cls(
            transactions=transactions,
            known_parties=known_parties,
            trp=trp,
            bound_parties=bound_parties,
            selected_profile=selected_profile,
            env_overrides=env_overrides,
        )

    def with_party(self, name: str, party: Party) -> "Tx3Client":
        """Late-binding party setter. Returns a new client with the party
        bound. Validated against the protocol's declared parties.

        Raises:
            UnknownPartyError: if `name` is not declared by the protocol.
        """
        lower = name.lower()
        if lower not in self._known_parties:
            raise UnknownPartyError(lower)
        next_parties = dict(self._bound_parties)
        next_parties[lower] = party
        return self._with_parties(next_parties)

    def with_party_unchecked(self, name: str, party: Party) -> "Tx3Client":
        """Late-binding party setter that skips the declared-party lookup.
        Intended for codegen-generated wrappers; hand-written code SHOULD
        prefer `with_party`.
        """
        next_parties = dict(self._bound_parties)
        next_parties[name.lower()] = party
        return self._with_parties(next_parties)

    def with_parties(
        self,
        parties: Union[Mapping[str, Party], Iterable[tuple[str, Party]]],
    ) -> "Tx3Client":
        """Late-binds multiple parties at once. See `with_party`."""
        if isinstance(parties, Mapping):
            items: Iterable[tuple[str, Party]] = parties.items()
        else:
            items = parties
        next_parties = dict(self._bound_parties)
        for name, party in items:
            lower = name.lower()
            if lower not in self._known_parties:
                raise UnknownPartyError(lower)
            next_parties[lower] = party
        return self._with_parties(next_parties)

    def tx(self, name: str) -> TxBuilder:
        """Starts building a transaction invocation.

        Raises:
            UnknownTxError: if `name` is not declared by the protocol.
        """
        if name not in self._transactions:
            raise UnknownTxError(name)
        tir = self._transactions[name]
        env = self._merged_env()
        parties = self._merged_parties()
        return TxBuilder(trp=self._trp, tir=tir).env(env).parties(parties)

    def _with_parties(self, parties: dict[str, Party]) -> "Tx3Client":
        return Tx3Client(
            transactions=self._transactions,
            known_parties=self._known_parties,
            trp=self._trp,
            bound_parties=parties,
            selected_profile=self._selected_profile,
            env_overrides=self._env_overrides,
        )

    def _merged_env(self) -> dict[str, Any]:
        env: dict[str, Any] = {}
        if self._selected_profile is not None:
            env.update(self._selected_profile.environment)
        env.update(self._env_overrides)
        return env

    def _merged_parties(self) -> dict[str, Party]:
        merged: dict[str, Party] = {}
        if self._selected_profile is not None:
            for name, address in self._selected_profile.parties.items():
                merged[name.lower()] = Party.address(address)
        merged.update(self._bound_parties)
        return merged
