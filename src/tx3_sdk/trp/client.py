"""Async low-level TRP JSON-RPC client."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from tx3_sdk.trp.errors import (
    DeserializationError,
    GenericRpcError,
    HttpError,
    MalformedResponseError,
    MissingTxArgError,
    NetworkError,
)
from tx3_sdk.trp.spec import (
    ChainPoint,
    CheckStatusResponse,
    ResolveParams,
    SubmitParams,
    SubmitResponse,
    TxEnvelope,
    TxStage,
    TxStatus,
)


@dataclass(frozen=True)
class ClientOptions:
    """Options for constructing a TRP client."""

    endpoint: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0


class TrpClient:
    """Low-level JSON-RPC client for TRP methods."""

    def __init__(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._options = ClientOptions(
            endpoint=endpoint,
            headers=headers or {},
            timeout_seconds=timeout_seconds,
        )
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def resolve(self, params: ResolveParams) -> TxEnvelope:
        """Calls `trp.resolve` and returns the resolved transaction envelope."""
        payload = {
            "tir": params.tir.to_json(),
            "args": params.args,
        }
        if params.env is not None:
            payload["env"] = params.env
        result = await self._call("trp.resolve", payload)
        if not isinstance(result, dict) or "hash" not in result or "tx" not in result:
            raise MalformedResponseError("resolve result must include hash and tx")
        return TxEnvelope(hash=str(result["hash"]), tx=str(result["tx"]))

    async def submit(self, params: SubmitParams) -> SubmitResponse:
        """Calls `trp.submit` and returns the submission hash."""
        result = await self._call(
            "trp.submit",
            {
                "tx": params.tx.to_json(),
                "witnesses": [w.to_json() for w in params.witnesses],
            },
        )
        if not isinstance(result, dict) or "hash" not in result:
            raise MalformedResponseError("submit result must include hash")
        return SubmitResponse(hash=str(result["hash"]))

    async def check_status(self, hashes: list[str]) -> CheckStatusResponse:
        """Calls `trp.checkStatus` and returns per-hash status data."""
        result = await self._call("trp.checkStatus", {"hashes": hashes})
        if not isinstance(result, dict) or not isinstance(result.get("statuses"), dict):
            raise MalformedResponseError("checkStatus result must include statuses map")
        statuses_raw = result["statuses"]
        statuses: dict[str, TxStatus] = {}
        for tx_hash, value in statuses_raw.items():
            if not isinstance(value, dict):
                continue
            stage_raw = str(value.get("stage", TxStage.UNKNOWN.value))
            try:
                stage = TxStage(stage_raw)
            except ValueError:
                stage = TxStage.UNKNOWN

            chain_point = value.get("confirmedAt")
            confirmed_at = None
            if isinstance(chain_point, dict):
                confirmed_at = ChainPoint(
                    slot=int(chain_point.get("slot", 0)),
                    block_hash=str(chain_point.get("blockHash", "")),
                )

            statuses[str(tx_hash)] = TxStatus(
                stage=stage,
                confirmations=int(value.get("confirmations", 0)),
                non_confirmations=int(value.get("nonConfirmations", 0)),
                confirmed_at=confirmed_at,
            )
        return CheckStatusResponse(statuses=statuses)

    async def close(self) -> None:
        """Closes the underlying HTTP transport."""
        await self._client.aclose()

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        headers = {"Content-Type": "application/json", **self._options.headers}
        try:
            response = await self._client.post(
                self._options.endpoint,
                headers=headers,
                json=request,
            )
        except httpx.RequestError as exc:
            raise NetworkError(f"TRP network error: {exc}") from exc

        if response.status_code != 200:
            raise HttpError(response.status_code, response.reason_phrase, response.text)

        try:
            payload = response.json()
        except ValueError as exc:
            raise DeserializationError(f"TRP deserialization error: {exc}") from exc

        if not isinstance(payload, dict):
            raise MalformedResponseError("response root must be an object")

        error = payload.get("error")
        if isinstance(error, dict):
            raise _classify_rpc_error(error)

        if "result" not in payload:
            raise MalformedResponseError("response has no result")
        return payload["result"]


def _classify_rpc_error(error: dict[str, Any]) -> Exception:
    code = int(error.get("code", -1))
    message = str(error.get("message", "unknown JSON-RPC error"))
    data = error.get("data")

    if isinstance(data, dict) and data.get("kind") == "MissingTxArg":
        return MissingTxArgError(str(data.get("key", "unknown")), data.get("argType"))

    return GenericRpcError(code=code, message=message, data=data)
