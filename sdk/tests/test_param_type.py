"""Tests for the TII parameter-type model."""

from __future__ import annotations

import pytest

from tx3_sdk.tii.param_type import ParamKind, param_type_from_schema

_TII = "https://tx3.land/specs/v1beta0/tii#/$defs/"
_CORE = "https://tx3.land/specs/v1beta0/core#"


def test_primitives_and_unit() -> None:
    assert param_type_from_schema({"type": "integer"}).kind is ParamKind.INTEGER
    assert param_type_from_schema({"type": "boolean"}).kind is ParamKind.BOOLEAN
    assert param_type_from_schema({"type": "null"}).kind is ParamKind.UNIT


@pytest.mark.parametrize("prefix", [_TII, _CORE])
@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Bytes", ParamKind.BYTES),
        ("Address", ParamKind.ADDRESS),
        ("UtxoRef", ParamKind.UTXO_REF),
        ("Utxo", ParamKind.UTXO),
        ("AnyAsset", ParamKind.ANY_ASSET),
    ],
)
def test_core_refs_in_both_url_forms(prefix: str, name: str, kind: ParamKind) -> None:
    assert param_type_from_schema({"$ref": prefix + name}).kind is kind


def test_nested_list() -> None:
    pt = param_type_from_schema(
        {"type": "array", "items": {"type": "array", "items": {"type": "boolean"}}}
    )
    assert pt.kind is ParamKind.LIST
    assert pt.inner is not None and pt.inner.kind is ParamKind.LIST
    assert pt.inner.inner is not None and pt.inner.inner.kind is ParamKind.BOOLEAN


def test_tuple_with_prefix_items() -> None:
    pt = param_type_from_schema(
        {
            "type": "array",
            "prefixItems": [{"type": "integer"}, {"$ref": _TII + "Bytes"}],
            "items": False,
        }
    )
    assert pt.kind is ParamKind.TUPLE
    assert [e.kind for e in pt.elements] == [ParamKind.INTEGER, ParamKind.BYTES]


def test_map() -> None:
    pt = param_type_from_schema(
        {"type": "object", "additionalProperties": {"type": "integer"}}
    )
    assert pt.kind is ParamKind.MAP
    assert pt.inner is not None and pt.inner.kind is ParamKind.INTEGER


def test_record() -> None:
    pt = param_type_from_schema(
        {
            "type": "object",
            "properties": {"price": {"type": "integer"}, "live": {"type": "boolean"}},
            "required": ["price", "live"],
        }
    )
    assert pt.kind is ParamKind.RECORD
    assert pt.fields["price"].kind is ParamKind.INTEGER
    assert pt.fields["live"].kind is ParamKind.BOOLEAN


def test_variant() -> None:
    pt = param_type_from_schema(
        {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["Buy"],
                    "properties": {"Buy": {"type": "object", "properties": {}, "required": []}},
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["Sell"],
                    "properties": {
                        "Sell": {
                            "type": "object",
                            "properties": {"price": {"type": "integer"}},
                            "required": ["price"],
                        }
                    },
                },
            ]
        }
    )
    assert pt.kind is ParamKind.VARIANT
    assert [c.tag for c in pt.cases] == ["Buy", "Sell"]
    assert pt.cases[1].fields.kind is ParamKind.RECORD
    assert pt.cases[1].fields.fields["price"].kind is ParamKind.INTEGER


def test_component_ref_resolves_recursively() -> None:
    components = {
        "AssetClass": {
            "type": "object",
            "properties": {"policy": {"$ref": _TII + "Bytes"}},
            "required": ["policy"],
        }
    }
    pt = param_type_from_schema({"$ref": "#/components/schemas/AssetClass"}, components)
    assert pt.kind is ParamKind.RECORD
    assert pt.fields["policy"].kind is ParamKind.BYTES

    missing = param_type_from_schema({"$ref": "#/components/schemas/Nope"}, components)
    assert missing.kind is ParamKind.UNKNOWN


@pytest.mark.parametrize(
    "schema",
    [{"type": "string"}, {}, {"type": "array"}, {"$ref": "https://example.com/Weird"}],
)
def test_unrecognized_shapes_fall_back_to_unknown(schema: dict[str, object]) -> None:
    assert param_type_from_schema(schema).kind is ParamKind.UNKNOWN
