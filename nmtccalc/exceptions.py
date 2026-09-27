"""Warnings and errors raised by nmtc-calc."""


class LeverageShortfallWarning(UserWarning):
    """The Investment Fund cannot service its leverage loan from QLICI flows.

    Raised by ``waterfall.analyze`` when the modeled QLICI interest reaching
    the fund is less than the leverage loan's annual interest, or when the
    A-loan principal repaid at unwind is less than the leverage loan principal
    due. The result object carries the figures; the warning makes sure a
    structure that cannot fund itself does not render silently.
    """


class NegativeTrancheError(ValueError):
    """A capital-stack tranche would be negative, so the deal is refused.

    A subclass of ValueError, so existing ``except ValueError`` handlers still
    catch it.
    """


class UnbalancedStackError(ValueError):
    """SUPPLIED capital-stack amounts do not reconcile, so the deal is refused.

    Raised when both the A and B loan amounts are SUPPLIED and their sum
    differs from QLICI total (QEI less the CDE fee) by more than the stated
    tolerance.
    """
