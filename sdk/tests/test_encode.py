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


BYTES_SCHEMA = {"$ref": "https://tx3.land/specs/v1beta0/tii#/$defs/Bytes"}
LIST_OF_BYTES_SCHEMA = {"type": "array", "items": BYTES_SCHEMA}


def test_native_byte_arrays_canonicalize_to_hex() -> None:
    # A native byte array (`bytes`, or an integer list — the JSON shape other
    # SDKs' native byte arrays serialize to) canonicalizes to 0x-prefixed hex
    # (regression: TRP `(-32005) value is not bytes: [1,1]`).
    bytes_param = param_type_from_schema(BYTES_SCHEMA)
    assert encode(bytes_param, b"\x01\x01") == "0x0101"
    assert encode(bytes_param, bytearray(b"\x01\x01")) == "0x0101"
    assert encode(bytes_param, [1, 1]) == "0x0101"

    list_param = param_type_from_schema(LIST_OF_BYTES_SCHEMA)
    assert encode(list_param, [b"\x01\x02"]) == {"list": [{"bytes": "0x0102"}]}


def test_rejects_non_byte_arrays_for_bytes() -> None:
    bytes_param = param_type_from_schema(BYTES_SCHEMA)
    for bad in ([1, 256], [1, -1], ["aa", 1], [True], 42):
        with pytest.raises(EncodeArgError):
            encode(bytes_param, bad)


def test_hydra_init_arg_shapes() -> None:
    # Hydra `init`: `participants` / `parties` are `List<Bytes>`, `head_id` is
    # `Bytes` (regression: `(-32005) target type not supported: List` /
    # `value is not bytes: [1,2]`).
    list_param = param_type_from_schema(LIST_OF_BYTES_SCHEMA)
    assert encode(list_param, ["0102", "0304"]) == {
        "list": [{"bytes": "0102"}, {"bytes": "0304"}]
    }
    assert encode(list_param, [b"\x01\x02"]) == {"list": [{"bytes": "0x0102"}]}

    bytes_param = param_type_from_schema(BYTES_SCHEMA)
    assert encode(bytes_param, "abcd0123") == "abcd0123"


def test_asteria_name_arg_shapes() -> None:
    # Asteria `create_ship`: `ship_name` / `pilot_name` are `Bytes` params
    # (regression: `(-32005) value is not bytes: [1,1]`).
    bytes_param = param_type_from_schema(BYTES_SCHEMA)
    assert encode(bytes_param, "53484950313233") == "53484950313233"
    assert encode(bytes_param, b"SHIP") == "0x53484950"
