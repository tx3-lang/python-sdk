"""Submitted transaction model with wait modes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tx3_sdk.facade.errors import FinalizedFailedError, FinalizedTimeoutError
from tx3_sdk.facade.poll import PollConfig
from tx3_sdk.trp.client import TrpClient
from tx3_sdk.trp.spec import TxStage, TxStatus


@dataclass(frozen=True)
class SubmittedTx:
    """Output of `SignedTx.submit`, pollable for chain status."""

    trp: TrpClient
    hash: str

    async def wait_for_confirmed(self, poll_config: PollConfig) -> TxStatus:
        """Waits until tx stage is Confirmed or Finalized."""
        return await self._wait_for_stage(poll_config, TxStage.CONFIRMED)

    async def wait_for_finalized(self, poll_config: PollConfig) -> TxStatus:
        """Waits until tx stage is Finalized."""
        return await self._wait_for_stage(poll_config, TxStage.FINALIZED)

    async def _wait_for_stage(self, poll_config: PollConfig, target: TxStage) -> TxStatus:
        attempts = max(1, poll_config.attempts)
        for attempt in range(attempts):
            response = await self.trp.check_status([self.hash])
            status = response.statuses.get(self.hash)

            if status is not None:
                if status.stage.is_terminal_failure():
                    raise FinalizedFailedError(self.hash, status.stage.value)

                if _stage_reached(status.stage, target):
                    return status

            if attempt < attempts - 1:
                await asyncio.sleep(max(0.0, poll_config.delay_seconds))

        raise FinalizedTimeoutError(self.hash, attempts, poll_config.delay_seconds)


def _stage_reached(current: TxStage, target: TxStage) -> bool:
    if target == TxStage.CONFIRMED:
        return current in {TxStage.CONFIRMED, TxStage.FINALIZED}
    return current == target
