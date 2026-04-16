"""Invocation model used by the facade resolution step."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tx3_sdk.core.args import normalize_arg_key
from tx3_sdk.core.bytes import TirEnvelope
from tx3_sdk.tii.errors import MissingParamsError
from tx3_sdk.tii.param_type import ParamType


@dataclass
class Invocation:
    """Represents a partially built transaction invocation."""

    tir: TirEnvelope
    params: dict[str, ParamType]
    required: set[str]
    args: dict[str, Any] = field(default_factory=dict)

    def set_arg(self, name: str, value: Any) -> None:
        """Sets an argument by key, matching key case-insensitively."""
        self.args[normalize_arg_key(name)] = value

    def set_args(self, args: dict[str, Any]) -> None:
        """Sets multiple arguments in a single call."""
        for key, value in args.items():
            self.set_arg(key, value)

    def unspecified_params(self) -> list[str]:
        """Returns required params that are not currently set."""
        missing: list[str] = []
        for name in self.required:
            if normalize_arg_key(name) not in self.args:
                missing.append(name)
        return missing

    def into_resolve_request(self) -> tuple[TirEnvelope, dict[str, Any]]:
        """Converts invocation into the TRP resolve payload."""
        missing = self.unspecified_params()
        if missing:
            raise MissingParamsError(missing)
        return self.tir, self.args
