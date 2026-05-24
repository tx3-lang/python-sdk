"""Builder for `Tx3Client`."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Union

from tx3_sdk.core.bytes import TirEnvelope
from tx3_sdk.facade.client import Tx3Client
from tx3_sdk.facade.errors import MissingTrpEndpointError, UnknownPartyError
from tx3_sdk.facade.party import Party
from tx3_sdk.facade.profile import Profile
from tx3_sdk.tii.errors import UnknownProfileError
from tx3_sdk.tii.protocol import Protocol
from tx3_sdk.trp.client import ClientOptions, TrpClient


class Tx3ClientBuilder:
    """Builds a `Tx3Client`.

    Obtained via `Protocol.client()` for the dynamic flow or
    `Tx3ClientBuilder.from_parts(...)` for the codegen flow. All fallible
    validation — TRP endpoint present, selected profile declared, every bound
    party declared — happens in `build()`. Optional setters never raise, so
    chains stay fluent.

    Example:
        >>> client = (
        ...     Protocol.from_file("protocol.tii")
        ...     .client()
        ...     .trp_endpoint("https://trp.example")
        ...     .with_profile("preprod")
        ...     .with_party("sender", Party.signer(signer))
        ...     .build()
        ... )
    """

    def __init__(
        self,
        transactions: Mapping[str, TirEnvelope],
        profiles: Mapping[str, Profile],
        known_parties: Iterable[str],
    ) -> None:
        self._transactions: dict[str, TirEnvelope] = dict(transactions)
        self._profiles: dict[str, Profile] = dict(profiles)
        self._known_parties: set[str] = {name.lower() for name in known_parties}
        self._trp_options: ClientOptions | None = None
        self._trp_client_override: Any = None
        self._profile: str | None = None
        self._parties: dict[str, Party] = {}
        self._unchecked_parties: dict[str, Party] = {}
        self._env_overrides: dict[str, Any] = {}

    @classmethod
    def from_parts(
        cls,
        transactions: Mapping[str, TirEnvelope],
        profiles: Mapping[str, Profile],
        known_parties: Iterable[str],
    ) -> "Tx3ClientBuilder":
        """Seeds a builder with already-deconstructed protocol fragments.

        Codegen-generated bindings call this with embedded per-transaction TIR
        envelopes, per-profile environment + party-address maps, and
        (typically) an empty known-parties set — the typed
        `with_<party>_unchecked` wrapper methods bake party names in at
        codegen time so runtime name validation is unnecessary.
        """
        return cls(transactions, profiles, known_parties)

    @classmethod
    def from_protocol(cls, protocol: Protocol) -> "Tx3ClientBuilder":
        """Entry point used by `Protocol.client()`."""
        transactions: dict[str, TirEnvelope] = {}
        for name, tx in protocol.transactions.items():
            tir_raw = tx.get("tir")
            if not isinstance(tir_raw, dict):
                continue
            transactions[name] = TirEnvelope(
                content=str(tir_raw["content"]),
                encoding=str(tir_raw["encoding"]),
                version=str(tir_raw["version"]),
            )

        profiles: dict[str, Profile] = {}
        for name, spec in protocol.profiles.items():
            env = spec.get("environment", {})
            if not isinstance(env, dict):
                env = {}
            parties_map = spec.get("parties", {})
            if not isinstance(parties_map, dict):
                parties_map = {}
            profiles[name] = Profile(
                environment=dict(env),
                parties={str(k): str(v) for k, v in parties_map.items()},
            )

        known_parties = set(protocol.parties.keys())
        return cls(transactions, profiles, known_parties)

    def trp(self, options: ClientOptions) -> "Tx3ClientBuilder":
        """Sets the full TRP client options."""
        self._trp_options = options
        return self

    def trp_endpoint(self, url: str) -> "Tx3ClientBuilder":
        """Shorthand for `trp(ClientOptions(endpoint=url))`."""
        self._trp_options = ClientOptions(endpoint=url, headers={})
        return self

    def with_header(self, key: str, value: str) -> "Tx3ClientBuilder":
        """Adds a single TRP request header. Initializes options to an empty
        endpoint if not set — callers must still supply the endpoint via
        `trp()` or `trp_endpoint()`.
        """
        if self._trp_options is None:
            self._trp_options = ClientOptions(endpoint="", headers={key: value})
        else:
            headers = dict(self._trp_options.headers)
            headers[key] = value
            self._trp_options = ClientOptions(
                endpoint=self._trp_options.endpoint,
                headers=headers,
                timeout_seconds=self._trp_options.timeout_seconds,
            )
        return self

    def with_profile(self, name: str) -> "Tx3ClientBuilder":
        """Selects a profile by name. Validated in `build()`."""
        self._profile = name
        return self

    def with_party(self, name: str, party: Party) -> "Tx3ClientBuilder":
        """Binds a party by name. The name is validated against the
        protocol's declared parties in `build()`.
        """
        self._parties[name.lower()] = party
        return self

    def with_party_unchecked(self, name: str, party: Party) -> "Tx3ClientBuilder":
        """Binds a party without validating the name against the protocol's
        declared parties. Intended for codegen-generated wrappers; hand-
        written code SHOULD prefer `with_party`.
        """
        self._unchecked_parties[name.lower()] = party
        return self

    def with_parties(
        self,
        parties: Union[Mapping[str, Party], Iterable[tuple[str, Party]]],
    ) -> "Tx3ClientBuilder":
        """Binds multiple parties at once. See `with_party`."""
        if isinstance(parties, Mapping):
            items: Iterable[tuple[str, Party]] = parties.items()
        else:
            items = parties
        for name, party in items:
            self.with_party(name, party)
        return self

    def with_env_value(self, key: str, value: Any) -> "Tx3ClientBuilder":
        """Sets a single environment value, merged on top of the selected
        profile's environment at resolve time (override wins).
        """
        self._env_overrides[key] = value
        return self

    def _trp_client(self, client: Any) -> "Tx3ClientBuilder":
        """Internal: lets tests inject a pre-built / mock TRP client without
        going through the `ClientOptions` construction path. Not part of the
        public API.
        """
        self._trp_client_override = client
        return self

    def build(self) -> Tx3Client:
        """Validates the builder state and materializes the `Tx3Client`.

        Raises:
            MissingTrpEndpointError: if no TRP endpoint was supplied.
            UnknownProfileError: if the selected profile is not declared.
            UnknownPartyError: if any bound party is not declared.
        """
        if self._trp_client_override is not None:
            trp = self._trp_client_override
        else:
            if self._trp_options is None or not self._trp_options.endpoint:
                raise MissingTrpEndpointError()
            trp = TrpClient(
                endpoint=self._trp_options.endpoint,
                headers=dict(self._trp_options.headers),
                timeout_seconds=self._trp_options.timeout_seconds,
            )

        selected_profile: Profile | None = None
        if self._profile is not None:
            if self._profile not in self._profiles:
                raise UnknownProfileError(self._profile)
            selected_profile = self._profiles[self._profile]

        for name in self._parties:
            if name not in self._known_parties:
                raise UnknownPartyError(name)

        bound_parties: dict[str, Party] = {}
        bound_parties.update(self._parties)
        bound_parties.update(self._unchecked_parties)

        return Tx3Client._from_builder(
            transactions=self._transactions,
            known_parties=self._known_parties,
            trp=trp,
            bound_parties=bound_parties,
            selected_profile=selected_profile,
            env_overrides=dict(self._env_overrides),
        )
