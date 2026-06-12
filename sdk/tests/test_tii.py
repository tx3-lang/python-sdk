import json
from pathlib import Path

import pytest

from tx3_sdk.tii import (
    InvalidJsonError,
    MissingParamsError,
    ParamKind,
    Protocol,
    UnknownProfileError,
    UnknownTxError,
)


def test_protocol_from_file() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    assert "transfer" in protocol.transactions
    assert "sender" in protocol.parties


def test_protocol_from_string_equivalent_to_file() -> None:
    raw = Path("tests/fixtures/transfer.tii").read_text(encoding="utf-8")
    from_file = Protocol.from_file("tests/fixtures/transfer.tii")
    from_string = Protocol.from_string(raw)
    assert from_file.transactions.keys() == from_string.transactions.keys()
    assert from_file.parties.keys() == from_string.parties.keys()


def test_protocol_from_json() -> None:
    raw = Path("tests/fixtures/transfer.tii").read_text(encoding="utf-8")
    protocol = Protocol.from_json(json.loads(raw))
    assert protocol.tii_version == "v1beta0"


def test_protocol_from_bytes() -> None:
    raw = Path("tests/fixtures/transfer.tii").read_bytes()
    protocol = Protocol.from_bytes(raw)
    assert "transfer" in protocol.transactions


def test_reject_malformed_json() -> None:
    with pytest.raises(InvalidJsonError):
        Protocol.from_string("{oops")


def test_unknown_tx_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    with pytest.raises(UnknownTxError):
        protocol.invoke("missing")


def test_unknown_profile_raises() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    with pytest.raises(UnknownProfileError):
        protocol.invoke("transfer", profile="missing")


def test_profile_populates_env_args() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    invocation = protocol.invoke("transfer", profile="preprod")
    assert invocation.args.get("tax") == 5_000_000


def test_missing_params_detected() -> None:
    protocol = Protocol.from_file("tests/fixtures/transfer.tii")
    invocation = protocol.invoke("transfer")
    with pytest.raises(MissingParamsError):
        invocation.into_resolve_request()


def test_invoke_interprets_complex_params() -> None:
    """Locks in the ``Protocol.invoke`` path the unit tests can't reach: threading
    ``components`` into ``param_type_from_schema``, and exposing party (Address)
    and environment-schema params. Asserts a real ``complex.tii`` produces the
    expected compound kinds, including a component-``$ref`` Record and Variant."""
    protocol = Protocol.from_file("tests/fixtures/complex.tii")
    params = protocol.invoke("complex").params

    want_kind = {
        "quantity": ParamKind.INTEGER,
        "flag": ParamKind.BOOLEAN,
        "nothing": ParamKind.UNIT,
        "recipient": ParamKind.ADDRESS,
        "source": ParamKind.UTXO_REF,
        "bag": ParamKind.ANY_ASSET,
        "amounts": ParamKind.LIST,
        "pair": ParamKind.TUPLE,
        "labels": ParamKind.MAP,
        "asset": ParamKind.RECORD,
        "side": ParamKind.VARIANT,
        # Parties surface as implicit Address params (lowercased).
        "sender": ParamKind.ADDRESS,
        "receiver": ParamKind.ADDRESS,
        # Protocol-level environment schema params.
        "fee": ParamKind.INTEGER,
    }
    for name, kind in want_kind.items():
        assert name in params, f"missing param {name!r}"
        assert params[name].kind is kind, f"param {name!r}: {params[name].kind} != {kind}"

    # The component-$ref Record must have resolved its inner Bytes field — this is
    # the assertion that actually guards the components threading.
    assert params["asset"].fields["policy"].kind is ParamKind.BYTES

    # The component-$ref Variant must have resolved its cases.
    assert len(params["side"].cases) == 2
