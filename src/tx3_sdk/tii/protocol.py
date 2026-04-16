"""Protocol loading and introspection for `.tii` files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tx3_sdk.core.bytes import TirEnvelope
from tx3_sdk.tii.errors import (
    InvalidJsonError,
    InvalidParamsSchemaError,
    UnknownProfileError,
    UnknownTxError,
)
from tx3_sdk.tii.invocation import Invocation
from tx3_sdk.tii.param_type import ParamType, param_type_from_schema


@dataclass(frozen=True)
class ProtocolInfo:
    """Metadata from the `protocol` section of a TII file."""

    name: str
    version: str
    scope: str
    description: str | None = None


class Protocol:
    """In-memory representation of a loaded TII document."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self._spec = spec
        self._validate_top_level()

    @classmethod
    def from_file(cls, path: str | Path) -> "Protocol":
        """Loads a protocol from a `.tii` JSON file."""
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise InvalidJsonError(f"failed to read TII file {path!s}: {exc}") from exc
        return cls.from_string(raw)

    @classmethod
    def from_string(cls, value: str) -> "Protocol":
        """Loads a protocol from a JSON string."""
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise InvalidJsonError(f"invalid TII JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise InvalidJsonError("TII root must be a JSON object")
        return cls(parsed)

    @classmethod
    def from_bytes(cls, value: bytes) -> "Protocol":
        """Loads a protocol from UTF-8 encoded JSON bytes."""
        try:
            decoded = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidJsonError(f"invalid TII bytes: {exc}") from exc
        return cls.from_string(decoded)

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "Protocol":
        """Loads a protocol from an already parsed JSON object."""
        if not isinstance(value, dict):
            raise InvalidJsonError("TII root must be a JSON object")
        return cls(value)

    @property
    def tii_version(self) -> str:
        """Returns the loaded TII schema version."""
        return str(self._spec["tii"]["version"])

    @property
    def protocol_info(self) -> ProtocolInfo:
        """Returns protocol metadata from the loaded TII."""
        info = self._spec["protocol"]
        return ProtocolInfo(
            name=str(info.get("name", "unknown")),
            version=str(info.get("version", "unknown")),
            scope=str(info.get("scope", "unknown")),
            description=info.get("description"),
        )

    @property
    def transactions(self) -> dict[str, dict[str, Any]]:
        """Returns the transaction definitions from the protocol."""
        return dict(self._spec["transactions"])

    @property
    def parties(self) -> dict[str, dict[str, Any]]:
        """Returns the parties map from the protocol."""
        return dict(self._spec["parties"])

    @property
    def profiles(self) -> dict[str, dict[str, Any]]:
        """Returns the profile map from the protocol."""
        return dict(self._spec["profiles"])

    def invoke(self, tx_name: str, profile: str | None = None) -> Invocation:
        """Creates an invocation model for a known transaction name."""
        tx = self._spec["transactions"].get(tx_name)
        if tx is None:
            raise UnknownTxError(tx_name)

        params_schema = tx.get("params")
        if not isinstance(params_schema, dict):
            raise InvalidParamsSchemaError("transaction params must be an object schema")

        properties = params_schema.get("properties")
        if not isinstance(properties, dict):
            raise InvalidParamsSchemaError("params.properties must be an object")

        params: dict[str, ParamType] = {}
        for key, schema in properties.items():
            if not isinstance(schema, dict):
                raise InvalidParamsSchemaError(f"param schema for {key} must be an object")
            params[key] = param_type_from_schema(schema)

        required_raw = params_schema.get("required", [])
        if not isinstance(required_raw, list):
            raise InvalidParamsSchemaError("params.required must be an array")
        required = {str(name) for name in required_raw}

        tir_raw = tx.get("tir")
        if not isinstance(tir_raw, dict):
            raise InvalidParamsSchemaError("transaction TIR envelope is missing or invalid")
        tir = TirEnvelope(
            content=str(tir_raw["content"]),
            encoding=str(tir_raw["encoding"]),
            version=str(tir_raw["version"]),
        )

        invocation = Invocation(tir=tir, params=params, required=required)
        if profile is not None:
            profile_spec = self._spec["profiles"].get(profile)
            if profile_spec is None:
                raise UnknownProfileError(profile)
            env = profile_spec.get("environment", {})
            if isinstance(env, dict):
                invocation.set_args({str(k): v for k, v in env.items()})

        return invocation

    def _validate_top_level(self) -> None:
        for key in ("tii", "protocol", "parties", "transactions", "profiles"):
            if key not in self._spec:
                raise InvalidJsonError(f"missing required TII field: {key}")
