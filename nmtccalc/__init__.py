from nmtccalc.data.schema import NMTCDeal, Provenance, Basis
from nmtccalc.exceptions import (
    LeverageShortfallWarning, NegativeTrancheError, UnbalancedStackError,
)
from nmtccalc import statute
from nmtccalc.models import transaction, credits, investor, subsidy, waterfall
from nmtccalc import utils

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("nmtc-calc")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
    "NMTCDeal", "transaction", "credits", "investor", "subsidy", "waterfall", "utils",
    "statute", "LeverageShortfallWarning", "NegativeTrancheError",
    "UnbalancedStackError", "Provenance", "Basis",
]
