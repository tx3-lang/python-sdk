"""Top-level exports for the Tx3 Python SDK."""

from tx3_sdk.core.args import ArgValue, coerce_arg
from tx3_sdk.facade.client import Tx3Client
from tx3_sdk.facade.party import Party
from tx3_sdk.facade.poll import PollConfig
from tx3_sdk.signer.cardano import CardanoSigner
from tx3_sdk.signer.ed25519 import Ed25519Signer
from tx3_sdk.signer.signer import Signer
from tx3_sdk.tii.protocol import Protocol
from tx3_sdk.trp.client import TrpClient

__all__ = [
    "ArgValue",
    "CardanoSigner",
    "Ed25519Signer",
    "Party",
    "PollConfig",
    "Protocol",
    "Signer",
    "TrpClient",
    "Tx3Client",
    "coerce_arg",
]

__version__ = "1.0.0"
