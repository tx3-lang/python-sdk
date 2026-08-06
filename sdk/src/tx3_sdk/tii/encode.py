"""Type-directed argument encoding into the TRP ``TaggedArg`` wire form.

A TRP resolve request carries an **untyped** TIR, so the resolver cannot recover
the structure of an aggregate argument (a record, list, tuple, or map) on its
own. The full type lives in the ``.tii``, a client-side artifact — so the SDK is
authoritative: it walks the resolved :class:`~tx3_sdk.tii.param_type.ParamType`
alongside the user value and emits the deterministic, self-describing
``TaggedArg`` (single-key tagged, recursive — see the ``TaggedArg`` schema in
``core/trp/v1beta0/trp.json`` and the SDK spec's ``api-surface/args.md``). The
resolver then decodes it structurally, without a schema.

It is one recursive walk over ``(type, value)``. A scalar leaf renders **bare**
at the top level — the resolver coerces it via the param's flat type — and
**tagged** when it sits inside an aggregate, where the resolver has no element
type. Aggregates always render to their tagged structural form.
"""

from __future__ import annotations

from typing import Any

from tx3_sdk.tii.errors import EncodeArgError
from tx3_sdk.tii.param_type import ParamKind, ParamType, VariantCase


def _shape_of(value: Any) -> str:
    """The JSON shape name of a value, for :class:`EncodeArgError` messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _wrong_shape(kind: str, expected: str, value: Any) -> EncodeArgError:
    return EncodeArgError(
        f"expected {expected} for a `{kind}` argument, got `{_shape_of(value)}`"
    )


def _as_byte_array(value: Any) -> bytes | None:
    """Interprets a value as a raw byte array: ``bytes``/``bytearray``, or a
    list whose every element is an integer in ``0..=255``. ``None`` if it is
    neither."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, list) and all(
        isinstance(b, int) and not isinstance(b, bool) and 0 <= b <= 255 for b in value
    ):
        return bytes(value)
    return None


def _leaf(tag: str, value: Any, nested: bool) -> Any:
    """Renders a scalar leaf: bare at the top level (the resolver knows the
    param's flat type), tagged when nested inside an aggregate (it doesn't)."""
    return {tag: value} if nested else value


def encode(param: ParamType, value: Any) -> Any:
    """Marshals an argument ``value`` into its TRP wire form, directed by ``param``.

    One recursive walk over ``(type, value)``: a scalar leaf renders bare at the
    top level and tagged when nested inside an aggregate; aggregates always render
    to their tagged structural form.

    Raises :class:`EncodeArgError` if ``value``'s shape cannot match ``param``.
    """
    return _marshal(param, value, nested=False)


def _marshal(param: ParamType, value: Any, nested: bool) -> Any:
    """``nested`` is true when ``value`` sits inside an aggregate, where scalar
    leaves must be tagged for the schema-less resolver."""
    kind = param.kind

    # Scalar leaves. Shape checks here are the "reject before sending" pass; the
    # resolver still performs the authoritative coercion.
    if kind is ParamKind.INTEGER:
        # Accept number or decimal/hex string.
        if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
            return _leaf("int", value, nested)
        raise _wrong_shape("integer", "number or decimal/hex string", value)

    if kind is ParamKind.BOOLEAN:
        # Accept the same lenient forms the resolver coerces (bool, 0/1,
        # "true"/"false").
        if isinstance(value, (bool, int, str)):
            return _leaf("bool", value, nested)
        raise _wrong_shape("boolean", "bool", value)

    if kind is ParamKind.BYTES:
        # Hex string or a BytesEnvelope object.
        if isinstance(value, (str, dict)):
            return _leaf("bytes", value, nested)
        # A native byte array (`bytes`/`bytearray`, or an integer list — the
        # JSON shape other SDKs' native byte arrays serialize to) canonicalizes
        # to 0x-prefixed hex, the wire form the resolver coerces (SDK spec
        # §3.9).
        raw = _as_byte_array(value)
        if raw is not None:
            return _leaf("bytes", f"0x{raw.hex()}", nested)
        raise _wrong_shape("bytes", "hex string, bytes envelope, or byte array", value)

    if kind is ParamKind.ADDRESS:
        if isinstance(value, str):
            return _leaf("address", value, nested)
        raise _wrong_shape("address", "bech32 or hex string", value)

    if kind is ParamKind.UTXO_REF:
        if isinstance(value, str):
            return _leaf("utxoRef", value, nested)
        raise _wrong_shape("utxoRef", "txid#index string", value)

    # A unit field has no payload; it lowers to a nullary struct.
    if kind is ParamKind.UNIT:
        return {"struct": {"constructor": 0, "fields": []}}

    if kind is ParamKind.LIST:
        if not isinstance(value, list):
            raise _wrong_shape("list", "array", value)
        inner = param.inner
        assert inner is not None  # LIST always carries its element type.
        return {"list": [_marshal(inner, item, nested=True) for item in value]}

    if kind is ParamKind.TUPLE:
        if not isinstance(value, list):
            raise _wrong_shape("tuple", "array", value)
        if len(value) != len(param.elements):
            raise EncodeArgError(
                f"tuple arity mismatch: expected {len(param.elements)} "
                f"element(s), got {len(value)}"
            )
        return {
            "tuple": [
                _marshal(t, v, nested=True)
                for t, v in zip(param.elements, value, strict=True)
            ]
        }

    if kind is ParamKind.MAP:
        if not isinstance(value, dict):
            raise _wrong_shape("map", "object", value)
        value_type = param.inner
        assert value_type is not None  # MAP always carries its value type.
        # The `.tii` erases the Tx3 key type (JSON object keys are strings), so
        # keys are carried as `string` leaves. Sort by key for a deterministic,
        # language-neutral pair order.
        pairs = [
            [{"string": key}, _marshal(value_type, value[key], nested=True)]
            for key in sorted(value)
        ]
        return {"map": pairs}

    # A record is constructor 0; a variant resolves its case index. Both emit the
    # same positional `struct` form.
    if kind is ParamKind.RECORD:
        return {
            "struct": {
                "constructor": 0,
                "fields": _marshal_record_fields(param.fields, value),
            }
        }

    if kind is ParamKind.VARIANT:
        return _marshal_variant(param.cases, value)

    # No wire-leaf form and no element types to drive encoding (`utxo`,
    # `anyAsset`, `unknown`): pass the value through and let the resolver coerce
    # it via the flat type.
    return value


def _marshal_record_fields(fields: dict[str, ParamType], value: Any) -> list[Any]:
    """Marshals a record's fields **positionally** in declared order, mapping the
    user's by-name object. Rejects missing or extra fields up front."""
    if not isinstance(value, dict):
        raise _wrong_shape("record", "object", value)

    # Reject any field the record does not declare.
    for key in value:
        if key not in fields:
            raise EncodeArgError(f"unknown record field `{key}`")

    encoded: list[Any] = []
    for name, ty in fields.items():
        if name not in value:
            raise EncodeArgError(f"missing record field `{name}`")
        encoded.append(_marshal(ty, value[name], nested=True))
    return encoded


def _marshal_variant(cases: tuple[VariantCase, ...], value: Any) -> Any:
    """Marshals an externally-tagged variant value ``{ "<Case>": <payload> }``
    into a ``struct`` whose ``constructor`` is the case index from the ``.tii``
    ``oneOf`` order."""
    if not isinstance(value, dict) or len(value) != 1:
        raise EncodeArgError("variant value must be a single-key object naming the case")

    tag, payload = next(iter(value.items()))

    index = next((i for i, c in enumerate(cases) if c.tag == tag), None)
    if index is None:
        raise EncodeArgError(f"unknown variant case `{tag}`")

    # A case payload is a record (possibly empty). Marshal its fields positionally
    # and stamp the case index as the constructor.
    case_fields = cases[index].fields
    if case_fields.kind is ParamKind.RECORD:
        fields = _marshal_record_fields(case_fields.fields, payload)
    else:
        # Defensive: a non-record payload encodes as the single field.
        fields = [_marshal(case_fields, payload, nested=True)]

    return {"struct": {"constructor": index, "fields": fields}}
