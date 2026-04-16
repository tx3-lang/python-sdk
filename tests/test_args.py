import pytest

from tx3_sdk.core.args import ArgValue, coerce_arg, normalize_arg_key


def test_coerce_native_types() -> None:
    assert coerce_arg(1) == 1
    assert coerce_arg(True) is True
    assert coerce_arg("hello") == "hello"
    assert coerce_arg(b"\xde\xad") == "0xdead"


def test_coerce_explicit_arg_value() -> None:
    assert coerce_arg(ArgValue.integer(42)) == 42
    assert coerce_arg(ArgValue.bytes(b"\xaa")) == "0xaa"
    assert coerce_arg(ArgValue.utxo_set(["tx1#0"])) == ["tx1#0"]


def test_normalize_arg_key() -> None:
    assert normalize_arg_key("Quantity") == "quantity"


def test_unsupported_arg_type() -> None:
    with pytest.raises(TypeError):
        coerce_arg(object())
