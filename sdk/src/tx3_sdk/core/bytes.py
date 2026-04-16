"""Envelope types for binary payloads used on TRP wire format."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BytesEnvelope:
    """Wraps binary data with explicit content type metadata."""

    content: str
    content_type: str = "hex"

    def to_json(self) -> dict[str, str]:
        """Returns the JSON representation expected by TRP."""
        return {"content": self.content, "contentType": self.content_type}

    @classmethod
    def hex(cls, content: str) -> "BytesEnvelope":
        """Creates a hex bytes envelope."""
        return cls(content=content, content_type="hex")


@dataclass(frozen=True)
class TirEnvelope:
    """Wraps TIR content with version and encoding metadata."""

    content: str
    encoding: str
    version: str

    def to_json(self) -> dict[str, str]:
        """Returns the JSON representation expected by TRP."""
        return {
            "content": self.content,
            "encoding": self.encoding,
            "version": self.version,
        }
