from dataclasses import dataclass
import pandas as pd

from nmtccalc.data.schema import NMTCDeal


@dataclass
class TransactionResult:
    """Output object from NMTC transaction structure analysis."""
    project_name: str
    total_project_cost: float
    qei: float
    total_nmtcs: float
    investor_equity: float
    leverage_loan: float
    cde_fee: float
    qlici_total: float
    qlici_a_loan: float
    qlici_b_loan: float
    credit_price: float
    nmtc_coverage: float        # NMTCs as % of total project cost
    leverage_ratio: float       # leverage loan / investor equity

    def summary(self) -> pd.DataFrame:
        rows = [
            ("Total Project Cost",      f"${self.total_project_cost/1e6:.2f}MM"),
            ("── QEI (NMTC Allocation)", f"${self.qei/1e6:.2f}MM"),
            ("── Total NMTCs (39% × QEI)", f"${self.total_nmtcs/1e6:.2f}MM"),
            ("",                         ""),
            ("INVESTMENT FUND",          ""),
            ("── Investor Equity",       f"${self.investor_equity/1e6:.2f}MM"),
            ("── Leverage Loan",         f"${self.leverage_loan/1e6:.2f}MM"),
            ("── Total QEI",             f"${self.qei/1e6:.2f}MM"),
            ("",                         ""),
            ("CDE / SUB-CDE",            ""),
            ("── CDE Fee",               f"${self.cde_fee/1e6:.2f}MM"),
            ("── Total QLICI",           f"${self.qlici_total/1e6:.2f}MM"),
            ("",                         ""),
            ("QLICI TO QALICB",          ""),
            ("── A Loan (Senior)",       f"${self.qlici_a_loan/1e6:.2f}MM"),
            ("── B Loan (Subordinate)",  f"${self.qlici_b_loan/1e6:.2f}MM"),
            ("",                         ""),
            ("KEY RATIOS",               ""),
            ("── Credit Price",          f"${self.credit_price:.2f} per $1 of NMTCs"),
            ("── NMTC Coverage",         f"{self.nmtc_coverage*100:.1f}% of project cost"),
            ("── Leverage Ratio",        f"{self.leverage_ratio:.2f}x"),
        ]

        df = pd.DataFrame(rows, columns=["Item", "Amount"])
        print(f"\nNMTC Transaction Structure — {self.project_name}")
        print("=" * 55)
        print(df.to_string(index=False))
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "total_project_cost": self.total_project_cost,
            "qei": self.qei,
            "total_nmtcs": self.total_nmtcs,
            "investor_equity": self.investor_equity,
            "leverage_loan": self.leverage_loan,
            "cde_fee": self.cde_fee,
            "qlici_total": self.qlici_total,
            "qlici_a_loan": self.qlici_a_loan,
            "qlici_b_loan": self.qlici_b_loan,
            "credit_price": self.credit_price,
            "nmtc_coverage": self.nmtc_coverage,
            "leverage_ratio": self.leverage_ratio,
        }


def structure(deal: NMTCDeal) -> TransactionResult:
    """
    Compute the full NMTC leveraged transaction structure.

    Args:
        deal: NMTCDeal instance with all deal parameters

    Returns:
        TransactionResult with complete capital stack breakdown
    """
    nmtc_coverage = deal.total_nmtcs / deal.total_project_cost
    leverage_ratio = deal.leverage_loan / deal.investor_equity

    return TransactionResult(
        project_name=deal.project_name,
        total_project_cost=deal.total_project_cost,
        qei=deal.qei,
        total_nmtcs=deal.total_nmtcs,
        investor_equity=deal.investor_equity,
        leverage_loan=deal.leverage_loan,
        cde_fee=deal.cde_fee,
        qlici_total=deal.qlici_total,
        qlici_a_loan=deal.qlici_a_loan,
        qlici_b_loan=deal.qlici_b_loan,
        credit_price=deal.credit_price,
        nmtc_coverage=nmtc_coverage,
        leverage_ratio=leverage_ratio,
    )
