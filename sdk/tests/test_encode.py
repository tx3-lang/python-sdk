"""Tests for the type-directed complex-argument `TaggedArg` encoder.

The `accept`/`reject` vectors come from the shared cross-SDK oracle
(`sdk-spec/test-vectors/complex-types/wire-vectors.json`, mirrored into
`tests/fixtures/`). Each `accept` vector pins (schema + components, value) →
tagged; each `reject` vector is a value the encoder MUST refuse before sending.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tx3_sdk.tii.encode import encode
from tx3_sdk.tii.errors import EncodeArgError
from tx3_sdk.tii.param_type import param_type_from_schema

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_vectors() -> dict:
    return json.loads((_FIXTURES / "wire-vectors.json").read_text(encoding="utf-8"))


_VECTORS = _load_vectors()
_COMPONENTS = _VECTORS.get("components", {})


@pytest.mark.parametrize(
    "vector",
    _VECTORS["accept"],
    ids=[v["name"] for v in _VECTORS["accept"]],
)
def test_accept_vectors(vector: dict) -> None:
    param = param_type_from_schema(vector["schema"], _COMPONENTS)
    assert encode(param, vector["value"]) == vector["tagged"]


@pytest.mark.parametrize(
    "vector",
    _VECTORS["reject"],
    ids=[v["name"] for v in _VECTORS["reject"]],
)
def test_reject_vectors(vector: dict) -> None:
    param = param_type_from_schema(vector["schema"], _COMPONENTS)
    with pytest.raises(EncodeArgError):
        encode(param, vector["value"])


def test_record_field_order_follows_required_not_alphabetical() -> None:
    # Meta { tags: List<Int>, level: Int } — required = [tags, level], while
    # `properties` alphabetizes to [level, tags]. The struct fields must be
    # [list, int], not [int, list].
    schema = {
        "type": "object",
        "properties": {
            "level": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["tags", "level"],
    }
    param = param_type_from_schema(schema)
    assert list(param.fields) == ["tags", "level"]

    encoded = encode(param, {"level": 7, "tags": [1, 2, 3]})
    assert encoded == {
        "struct": {
            "constructor": 0,
            "fields": [
                {"list": [{"int": 1}, {"int": 2}, {"int": 3}]},
                {"int": 7},
            ],
        }
    }


def test_top_level_scalars_render_bare() -> None:
    # A scalar at the top level is sent bare; the resolver coerces it via the
    # param's flat type.
    assert encode(param_type_from_schema({"type": "integer"}), 5) == 5
    assert encode(param_type_from_schema({"type": "boolean"}), True) is True
    address = param_type_from_schema(
        {"$ref": "https://tx3.land/specs/v1beta0/tii#/$defs/Address"}
    )
    assert encode(address, "addr1abc") == "addr1abc"


def test_nested_scalars_are_tagged() -> None:
    # The same scalar nested inside an aggregate is tagged.
    schema = {"type": "array", "items": {"type": "integer"}}
    assert encode(param_type_from_schema(schema), [5]) == {"list": [{"int": 5}]}


def test_unit_lowers_to_nullary_struct() -> None:
    assert encode(param_type_from_schema({"type": "null"}), None) == {
        "struct": {"constructor": 0, "fields": []}
    }
