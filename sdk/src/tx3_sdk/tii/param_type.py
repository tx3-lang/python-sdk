"""Parameter type model extracted from TII schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ParamKind(str, Enum):
    """The category of a transaction parameter type."""

    BYTES = "bytes"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    UNIT = "unit"
    UTXO_REF = "utxo_ref"
    ADDRESS = "address"
    UTXO = "utxo"
    ANY_ASSET = "any_asset"
    LIST = "list"
    TUPLE = "tuple"
    MAP = "map"
    RECORD = "record"
    VARIANT = "variant"
    UNKNOWN = "unknown"


@dataclass
class ParamType:
    """A transaction parameter's type.

    Compound kinds carry their element/field types: ``LIST`` / ``MAP`` in
    ``inner``, ``TUPLE`` in ``elements``, ``RECORD`` in ``fields``, ``VARIANT``
    in ``cases``. ``UNKNOWN`` carries the raw ``schema``.
    """

    kind: ParamKind
    inner: ParamType | None = None
    elements: tuple[ParamType, ...] = ()
    fields: dict[str, ParamType] = field(default_factory=dict)
    cases: tuple[VariantCase, ...] = ()
    schema: dict[str, object] | None = None


@dataclass
class VariantCase:
    """One case of a :class:`ParamType` of kind ``VARIANT``."""

    tag: str
    fields: ParamType


def param_type_from_schema(
    schema: dict[str, object],
    components: dict[str, dict[str, object]] | None = None,
) -> ParamType:
    """Maps a JSON schema node into a :class:`ParamType`.

    Never raises: any shape it does not recognize — a bare string, an unresolved
    object, an unknown ``$ref`` — becomes :attr:`ParamKind.UNKNOWN` carrying the
    raw schema. ``components`` is the TII's ``components.schemas`` table, used to
    resolve ``#/components/schemas/<Name>`` references to user-defined types.
    """
    components = components or {}

    ref = schema.get("$ref")
    if isinstance(ref, str):
        return _ref_type(schema, ref, components)

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        cases = tuple(
            _variant_case(case, components) for case in one_of if isinstance(case, dict)
        )
        return ParamType(ParamKind.VARIANT, cases=cases)

    schema_type = schema.get("type")
    if schema_type == "integer":
        return ParamType(ParamKind.INTEGER)
    if schema_type == "boolean":
        return ParamType(ParamKind.BOOLEAN)
    if schema_type == "null":
        return ParamType(ParamKind.UNIT)
    if schema_type == "array":
        return _array_type(schema, components)
    if schema_type == "object":
        return _object_type(schema, components)

    return ParamType(ParamKind.UNKNOWN, schema=schema)


def _ref_type(
    schema: dict[str, object], ref: str, components: dict[str, dict[str, object]]
) -> ParamType:
    """Interprets a ``$ref`` node: a ``#/components/schemas/<Name>`` reference
    resolves against ``components`` (recursing), a core ``$ref`` maps by trailing
    name, anything else falls back to ``UNKNOWN``."""
    prefix = "#/components/schemas/"
    if ref.startswith(prefix):
        resolved = components.get(ref[len(prefix) :])
        if isinstance(resolved, dict):
            return param_type_from_schema(resolved, components)
        return ParamType(ParamKind.UNKNOWN, schema=schema)
    kind = _core_kind_from_ref(ref)
    if kind is not None:
        return ParamType(kind)
    return ParamType(ParamKind.UNKNOWN, schema=schema)


def _array_type(
    schema: dict[str, object], components: dict[str, dict[str, object]]
) -> ParamType:
    """Interprets an ``array`` schema: ``prefixItems`` → ``TUPLE``, ``items`` →
    ``LIST``, neither → ``UNKNOWN``."""
    prefix_items = schema.get("prefixItems")
    if isinstance(prefix_items, list):
        elements = tuple(
            param_type_from_schema(el, components)
            for el in prefix_items
            if isinstance(el, dict)
        )
        return ParamType(ParamKind.TUPLE, elements=elements)
    items = schema.get("items")
    if isinstance(items, dict):
        return ParamType(ParamKind.LIST, inner=param_type_from_schema(items, components))
    return ParamType(ParamKind.UNKNOWN, schema=schema)


def _object_type(
    schema: dict[str, object], components: dict[str, dict[str, object]]
) -> ParamType:
    """Interprets an ``object`` schema: ``additionalProperties`` → ``MAP``,
    ``properties`` → ``RECORD``, neither → ``UNKNOWN``."""
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        return ParamType(
            ParamKind.MAP, inner=param_type_from_schema(additional, components)
        )
    properties = schema.get("properties")
    if isinstance(properties, dict):
        fields = {
            str(key): param_type_from_schema(value, components)
            for key, value in properties.items()
            if isinstance(value, dict)
        }
        return ParamType(ParamKind.RECORD, fields=fields)
    return ParamType(ParamKind.UNKNOWN, schema=schema)


def _variant_case(
    case: dict[str, object], components: dict[str, dict[str, object]]
) -> VariantCase:
    """Interprets one externally-tagged ``oneOf`` branch."""
    required = case.get("required")
    tag = str(required[0]) if isinstance(required, list) and required else ""

    fields = ParamType(ParamKind.UNKNOWN, schema=case)
    properties = case.get("properties")
    if isinstance(properties, dict):
        field_schema = properties.get(tag)
        if isinstance(field_schema, dict):
            fields = param_type_from_schema(field_schema, components)

    return VariantCase(tag=tag, fields=fields)


def _core_kind_from_ref(ref: str) -> ParamKind | None:
    """Matches a built-in core ``$ref`` by trailing name, so both the canonical
    ``…/tii#/$defs/<Name>`` and legacy ``…/core#<Name>`` forms resolve."""
    sep = max(ref.rfind("#"), ref.rfind("/"))
    name = ref[sep + 1 :] if sep >= 0 else ref
    return {
        "Bytes": ParamKind.BYTES,
        "Address": ParamKind.ADDRESS,
        "UtxoRef": ParamKind.UTXO_REF,
        "Utxo": ParamKind.UTXO,
        "AnyAsset": ParamKind.ANY_ASSET,
    }.get(name)
