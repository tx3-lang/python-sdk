import json
from pathlib import Path

import pytest

from tx3_sdk.tii import InvalidJsonError, MissingParamsError, Protocol, UnknownProfileError, UnknownTxError


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
