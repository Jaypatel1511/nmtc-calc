from dataclasses import dataclass
from typing import Optional


@dataclass
class NMTCDeal:
    """
    Core input contract for an NMTC leveraged transaction.
    All dollar amounts in whole dollars (e.g. 10_000_000 for $10MM).
    """
    project_name: str
    total_project_cost: float          # total project budget
    nmtc_allocation: float             # QEI amount
    credit_price: float                # $ per $1 of NMTC benefit e.g. 0.83
    leverage_loan_rate: float          # annual interest rate e.g. 0.045
    qlici_a_loan_rate: float           # senior QLICI loan rate
    qlici_b_loan_rate: float           # subordinate QLICI loan rate
    cde_fee_rate: float                # CDE upfront fee as % of QEI e.g. 0.02
    compliance_years: int = 7          # always 7 per Section 45D
    discount_rate: float = 0.08        # for NPV/IRR calculations
    noi: Optional[float] = None        # annual net operating income; required for waterfall/DSCR
    guarantee_fee_rate: float = 0.0    # annual guarantee fee as % of leverage loan e.g. 0.01
    exit_fee_rate: float = 0.0         # year-7 exit fee as % of QEI e.g. 0.005
    investor_name: Optional[str] = None
    cde_name: Optional[str] = None
    project_location: Optional[str] = None

    def __post_init__(self):
        if self.total_project_cost <= 0:
            raise ValueError("total_project_cost must be positive")
        if self.nmtc_allocation <= 0:
            raise ValueError("nmtc_allocation (QEI) must be positive")
        if self.nmtc_allocation > self.total_project_cost:
            raise ValueError("nmtc_allocation cannot exceed total_project_cost")
        if not (0 < self.credit_price < 1):
            raise ValueError("credit_price must be between 0 and 1 (e.g. 0.83)")
        if not (0 < self.cde_fee_rate < 1):
            raise ValueError("cde_fee_rate must be between 0 and 1 (e.g. 0.02)")
        if self.compliance_years != 7:
            raise ValueError("compliance_years must be 7 per Section 45D")
        if not (0 < self.discount_rate < 1):
            raise ValueError("discount_rate must be between 0 and 1 (e.g. 0.08)")
        if self.noi is not None and self.noi < 0:
            raise ValueError("noi must be non-negative")
        if self.guarantee_fee_rate < 0:
            raise ValueError("guarantee_fee_rate must be non-negative")
        if self.exit_fee_rate < 0:
            raise ValueError("exit_fee_rate must be non-negative")

    @property
    def qei(self) -> float:
        """Qualified Equity Investment amount."""
        return self.nmtc_allocation

    @property
    def total_nmtcs(self) -> float:
        """Total tax credits generated: 39% of QEI."""
        return self.qei * 0.39

    @property
    def investor_equity(self) -> float:
        """Investor equity contribution: total NMTCs × credit price."""
        return self.total_nmtcs * self.credit_price

    @property
    def leverage_loan(self) -> float:
        """Leverage loan amount: QEI minus investor equity."""
        return self.qei - self.investor_equity

    @property
    def cde_fee(self) -> float:
        """CDE upfront fee in dollars."""
        return self.qei * self.cde_fee_rate

    @property
    def qlici_total(self) -> float:
        """Total QLICI to QALICB: QEI minus CDE fee."""
        return self.qei - self.cde_fee

    @property
    def qlici_a_loan(self) -> float:
        """A Loan: mirrors leverage loan."""
        return self.leverage_loan

    @property
    def qlici_b_loan(self) -> float:
        """B Loan: mirrors investor equity net of CDE fee."""
        return self.investor_equity - self.cde_fee

    @property
    def guarantee_fee_annual(self) -> float:
        """Annual guarantee fee in dollars: leverage loan × guarantee_fee_rate."""
        return self.leverage_loan * self.guarantee_fee_rate

    @property
    def exit_fee(self) -> float:
        """Year-7 exit fee in dollars: QEI × exit_fee_rate."""
        return self.qei * self.exit_fee_rate

    @property
    def qei_mm(self) -> float:
        return self.qei / 1_000_000

    @property
    def total_project_cost_mm(self) -> float:
        return self.total_project_cost / 1_000_000

    def __repr__(self):
        return (
            f"NMTCDeal(project='{self.project_name}', "
            f"QEI=${self.qei_mm:.1f}MM, "
            f"NMTCs=${self.total_nmtcs/1e6:.2f}MM, "
            f"credit_price=${self.credit_price:.2f})"
        )
