"""Profile value type used by `Tx3ClientBuilder`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Profile:
    """Environment values and party-address overrides keyed by name.

    Produced either by deconstructing a loaded `Protocol` inside
    `Tx3ClientBuilder.from_protocol`, or by feeding the per-profile JSON blob a
    generated codegen client embeds through `Tx3ClientBuilder.from_parts`.
    """

    environment: dict[str, Any] = field(default_factory=dict)
    parties: dict[str, str] = field(default_factory=dict)
