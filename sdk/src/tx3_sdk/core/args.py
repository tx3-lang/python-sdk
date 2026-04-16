"""Argument marshalling helpers for Tx3 invocation arguments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArgValue:
    """Represents an explicitly tagged argument value."""

    kind: str
    value: Any

    @staticmethod
    def integer(value: int) -> "ArgValue":
        """Creates an integer argument value."""
        return ArgValue("integer", value)

    @staticmethod
    def boolean(value: bool) -> "ArgValue":
        """Creates a boolean argument value."""
        return ArgValue("boolean", value)

    @staticmethod
    def string(value: str) -> "ArgValue":
        """Creates a string argument value."""
        return ArgValue("string", value)

    @staticmethod
    def bytes(value: bytes) -> "ArgValue":
        """Creates a bytes argument value."""
        return ArgValue("bytes", value)

    @staticmethod
    def address(value: str) -> "ArgValue":
        """Creates an address argument value."""
        return ArgValue("address", value)

    @staticmethod
    def utxo_ref(value: str) -> "ArgValue":
        """Creates a UTxO reference argument value."""
        return ArgValue("utxo_ref", value)

    @staticmethod
    def utxo_set(value: list[str]) -> "ArgValue":
        """Creates a UTxO set argument value."""
        return ArgValue("utxo_set", value)


def normalize_arg_key(key: str) -> str:
    """Normalizes an arg key for case-insensitive matching."""
    return key.lower()


def coerce_arg(value: Any) -> Any:
    """Coerces a native Python value into TRP-compatible JSON data."""
    if isinstance(value, ArgValue):
        return _coerce_arg_value(value)
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, list):
        return [coerce_arg(item) for item in value]
    if isinstance(value, dict):
        return {str(k): coerce_arg(v) for k, v in value.items()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported arg type: {type(value)!r}")


def _coerce_arg_value(value: ArgValue) -> Any:
    if value.kind in {"integer", "boolean", "string", "address", "utxo_ref"}:
        return value.value
    if value.kind == "bytes":
        if not isinstance(value.value, bytes):
            raise TypeError("bytes ArgValue expects bytes payload")
        return "0x" + value.value.hex()
    if value.kind == "utxo_set":
        if not isinstance(value.value, list):
            raise TypeError("utxo_set ArgValue expects a list")
        return list(value.value)
    return value.value
