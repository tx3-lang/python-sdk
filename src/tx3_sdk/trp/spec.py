"""Typed models for TRP request and response payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tx3_sdk.core.bytes import BytesEnvelope, TirEnvelope


class TxStage(StrEnum):
    """Transaction lifecycle stages returned by TRP."""

    PENDING = "pending"
    PROPAGATED = "propagated"
    ACKNOWLEDGED = "acknowledged"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    DROPPED = "dropped"
    ROLLED_BACK = "rolledBack"
    UNKNOWN = "unknown"

    def is_terminal_failure(self) -> bool:
        """Returns true if this stage indicates permanent failure."""
        return self in {TxStage.DROPPED, TxStage.ROLLED_BACK}


@dataclass(frozen=True)
class ResolveParams:
    """Parameters for `trp.resolve`."""

    tir: TirEnvelope
    args: dict[str, Any]
    env: dict[str, Any] | None = None


@dataclass(frozen=True)
class TxEnvelope:
    """Resolved transaction envelope returned by `trp.resolve`."""

    hash: str
    tx: str


@dataclass(frozen=True)
class TxWitness:
    """A witness used by `trp.submit`."""

    key: BytesEnvelope
    signature: BytesEnvelope
    type: str = "vkey"

    def to_json(self) -> dict[str, object]:
        """Converts witness into TRP wire JSON shape."""
        return {
            "key": self.key.to_json(),
            "signature": self.signature.to_json(),
            "type": self.type,
        }


@dataclass(frozen=True)
class SubmitParams:
    """Parameters for `trp.submit`."""

    tx: BytesEnvelope
    witnesses: list[TxWitness]


@dataclass(frozen=True)
class SubmitResponse:
    """Response for `trp.submit`."""

    hash: str


@dataclass(frozen=True)
class ChainPoint:
    """Chain location where a transaction became confirmed."""

    slot: int
    block_hash: str


@dataclass(frozen=True)
class TxStatus:
    """Status of a submitted transaction."""

    stage: TxStage
    confirmations: int
    non_confirmations: int
    confirmed_at: ChainPoint | None = None


@dataclass(frozen=True)
class CheckStatusResponse:
    """Response for `trp.checkStatus`."""

    statuses: dict[str, TxStatus]
