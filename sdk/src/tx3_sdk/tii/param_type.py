"""Parameter type model extracted from TII schemas."""

from __future__ import annotations

from enum import Enum

from tx3_sdk.tii.errors import InvalidParamTypeError

_TX3_CORE_PREFIX = "https://tx3.land/specs/v1beta0/core#"


class ParamType(str, Enum):
    """Supported parameter kinds for invocation validation."""

    BYTES = "bytes"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    UTXO_REF = "utxo_ref"
    ADDRESS = "address"
    LIST = "list"
    CUSTOM = "custom"


def param_type_from_schema(schema: dict[str, object]) -> ParamType:
    """Maps a JSON schema node into a `ParamType`."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return _param_type_from_ref(ref)

    schema_type = schema.get("type")
    if schema_type == "integer":
        return ParamType.INTEGER
    if schema_type == "boolean":
        return ParamType.BOOLEAN
    if schema_type == "string":
        return ParamType.ADDRESS
    if schema_type == "array":
        return ParamType.LIST
    if schema_type == "object" or schema_type is None:
        return ParamType.CUSTOM
    raise InvalidParamTypeError(f"unknown schema type: {schema_type}")


def _param_type_from_ref(ref: str) -> ParamType:
    if not ref.startswith(_TX3_CORE_PREFIX):
        return ParamType.CUSTOM
    kind = ref.removeprefix(_TX3_CORE_PREFIX)
    if kind == "Bytes":
        return ParamType.BYTES
    if kind == "Address":
        return ParamType.ADDRESS
    if kind == "UtxoRef":
        return ParamType.UTXO_REF
    raise InvalidParamTypeError(f"unknown core type ref: {kind}")
