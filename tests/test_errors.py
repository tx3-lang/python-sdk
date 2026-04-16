from tx3_sdk.errors import PollingError, ResolutionError, SignerError, TiiError, TrpError
from tx3_sdk.facade.errors import FinalizedTimeoutError, UnknownPartyError
from tx3_sdk.signer.errors import InvalidPrivateKeyError
from tx3_sdk.tii.errors import UnknownTxError
from tx3_sdk.trp.errors import HttpError


def test_error_categories_are_discriminable() -> None:
    assert isinstance(UnknownTxError("transfer"), TiiError)
    assert isinstance(HttpError(500, "Error", "boom"), TrpError)
    assert isinstance(InvalidPrivateKeyError("bad key"), SignerError)
    assert isinstance(UnknownPartyError("sender"), ResolutionError)
    assert isinstance(FinalizedTimeoutError("hash", 1, 0), PollingError)
