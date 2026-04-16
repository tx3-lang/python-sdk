import json

import httpx
import pytest

from tx3_sdk.core.bytes import BytesEnvelope, TirEnvelope
from tx3_sdk.trp import (
    GenericRpcError,
    HttpError,
    MalformedResponseError,
    MissingTxArgError,
    ResolveParams,
    SubmitParams,
    TrpClient,
    TxWitness,
)


def _make_client(handler: httpx.MockTransport) -> TrpClient:
    client = TrpClient("https://example.invalid")
    client._client = httpx.AsyncClient(transport=handler)  # type: ignore[attr-defined]
    return client


@pytest.mark.asyncio
async def test_resolve_request_shape() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": "1", "result": {"hash": "abc", "tx": "beef"}},
        )

    client = _make_client(httpx.MockTransport(handle))
    result = await client.resolve(
        ResolveParams(
            tir=TirEnvelope(content="dead", encoding="hex", version="v1beta0"),
            args={"quantity": 100},
        )
    )
    await client.close()

    assert result.hash == "abc"
    assert captured["method"] == "trp.resolve"
    assert "params" in captured


@pytest.mark.asyncio
async def test_submit_and_check_status() -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        method = body["method"]
        calls.append(method)
        if method == "trp.submit":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"hash": "abc"}})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "statuses": {
                        "abc": {
                            "stage": "confirmed",
                            "confirmations": 1,
                            "nonConfirmations": 0,
                        }
                    }
                },
            },
        )

    client = _make_client(httpx.MockTransport(handle))
    submit = await client.submit(
        SubmitParams(
            tx=BytesEnvelope.hex("beef"),
            witnesses=[
                TxWitness(
                    key=BytesEnvelope.hex("aa"),
                    signature=BytesEnvelope.hex("bb"),
                    type="vkey",
                )
            ],
        )
    )
    status = await client.check_status([submit.hash])
    await client.close()

    assert calls == ["trp.submit", "trp.checkStatus"]
    assert status.statuses["abc"].stage.value == "confirmed"


@pytest.mark.asyncio
async def test_http_error_maps_to_typed_error() -> None:
    client = _make_client(httpx.MockTransport(lambda _: httpx.Response(500, text="boom")))
    with pytest.raises(HttpError):
        await client.resolve(ResolveParams(tir=TirEnvelope("", "hex", "v1beta0"), args={}))
    await client.close()


@pytest.mark.asyncio
async def test_rpc_error_classification() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -32000, "message": "bad", "data": {"kind": "MissingTxArg", "key": "quantity"}},
            },
        )

    client = _make_client(httpx.MockTransport(handle))
    with pytest.raises(MissingTxArgError):
        await client.resolve(ResolveParams(tir=TirEnvelope("", "hex", "v1beta0"), args={}))
    await client.close()


@pytest.mark.asyncio
async def test_malformed_result() -> None:
    client = _make_client(httpx.MockTransport(lambda _: httpx.Response(200, json={"jsonrpc": "2.0", "id": "1"})))
    with pytest.raises(MalformedResponseError):
        await client.resolve(ResolveParams(tir=TirEnvelope("", "hex", "v1beta0"), args={}))
    await client.close()


def test_generic_rpc_error_type() -> None:
    err = GenericRpcError(code=-1, message="x")
    assert err.code == -1
