"""Polling configuration for submitted transaction wait modes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PollConfig:
    """Configures polling attempts and delay between checks."""

    attempts: int = 20
    delay_seconds: float = 5.0

    @staticmethod
    def default() -> "PollConfig":
        """Returns default polling config (20 attempts, 5s delay)."""
        return PollConfig()
