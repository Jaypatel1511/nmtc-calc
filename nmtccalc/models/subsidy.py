from dataclasses import dataclass
from typing import Optional

import pandas as pd

from nmtccalc import statute
from nmtccalc.data.schema import NMTCDeal
from nmtccalc._format import money


REFUSED_FORGIVENESS = "REFUSED: b_loan_forgiveness_rate not supplied (it has no default)"
REFUSED_ALT_RATE = "REFUSED: qalicb_alternative_borrowing_rate not supplied"

NET_SUBSIDY_NOTE = (
    "Net subsidy = B loan x b_loan_forgiveness_rate, less the exit fee paid at "
    "unwind. Deducting the exit fee here assumes the QALICB bears it; the model "
    "does not know who does, and the deal documents decide. The rows above are "
    "a list, not a subtraction: the B loan follows the rule in its Basis column. "
    "Net subsidy does not deduct interest paid on the QLICI loans, guarantee fees, "
    "the put price, any tax on cancellation-of-debt income from the forgiveness, or "
    "the time value of money; it is a face-amount figure at unwind."
)

BLENDED_COUPON_NOTE = (
    "Blended QLICI coupon = (A x A rate + B x B rate) / QLICI total. It is a "
    "principal-weighted average coupon, not a cost of capital: it moves with the "
    "A/B split and the two rates only, and ignores every fee, the forgiveness, the "
    "put and the exit fee. (0.2.1 called it effective_cost_of_capital.)"
)

INTEREST_SAVINGS_NOTE = (
    "Interest savings to unwind = simple, undiscounted interest over years "
    "1..{k} on the full QLICI principal (A and B loans), comparing the QALICB's "
    "alternative borrowing rate, which you supply, with the QLICI coupons. A "
    "negative figure means the QLICI loans cost more than the alternative. 0.2.1 "
    "used the Investment Fund's leverage-loan rate here, which is the wrong "
    "entity's cost of capital, and the B loan only."
)


@dataclass
class SubsidyResult:
    """Output object from NMTC net subsidy analysis.

    Figures that depend on an input that was not supplied are None, and
    ``refused`` maps each such field to the reason.
    """
    project_name: str
    total_project_cost: float
    qei: float
    investor_equity: float
    cde_fee: float
    qlici_b_loan: float
    b_loan_forgiveness_rate: Optional[float]
    b_loan_forgiven: Optional[float]
    exit_fee: float
    net_subsidy: Optional[float]
    net_subsidy_pct: Optional[float]
    blended_qlici_coupon: float
    qalicb_alternative_borrowing_rate: Optional[float]
    interest_savings_to_unwind: Optional[float]
    unwind_year: int
    in_recapture_period: bool
    refused: dict
    basis: dict

    def summary(self) -> pd.DataFrame:
        def money_or_refused(v, name):
            return f"{money(v/1e6, '.2f')}MM" if v is not None else self.refused[name]

        def pct(v, name, digits):
            return f"{v*100:.{digits}f}%" if v is not None else self.refused[name]

        b = self.basis
        k = self.unwind_year
        rows = [
            ("Investor Equity (into fund)", f"{money(self.investor_equity/1e6, '.2f')}MM", b.get("investor_equity", "")),
            ("CDE Fee (upfront)",           f"{money(self.cde_fee/1e6, '.2f')}MM", b.get("cde_fee", "")),
            ("B Loan to QALICB",            f"{money(self.qlici_b_loan/1e6, '.2f')}MM", b.get("qlici_b_loan", "")),
            ("B-Loan Forgiveness Rate",     pct(self.b_loan_forgiveness_rate, "b_loan_forgiveness_rate", 1),
             "SUPPLIED: b_loan_forgiveness_rate" if self.b_loan_forgiveness_rate is not None else ""),
            ("B Loan Forgiven at Unwind",   money_or_refused(self.b_loan_forgiven, "b_loan_forgiven"),
             "DERIVED: B loan x forgiveness rate" if self.b_loan_forgiven is not None else ""),
            ("Exit Fee at Unwind",          f"{money(self.exit_fee/1e6, '.2f')}MM", b.get("exit_fee", "")),
            ("",                             "", ""),
            (f"Net Subsidy at Unwind (t={k})", money_or_refused(self.net_subsidy, "net_subsidy"),
             "DERIVED: B loan forgiven - exit fee" if self.net_subsidy is not None else ""),
            ("Net Subsidy as % of Project", pct(self.net_subsidy_pct, "net_subsidy_pct", 1),
             "DERIVED: net subsidy / project cost" if self.net_subsidy_pct is not None else ""),
            ("",                             "", ""),
            ("Blended QLICI Coupon",        f"{self.blended_qlici_coupon*100:.2f}%",
             "DERIVED: (A x A rate + B x B rate) / QLICI total"),
            ("QALICB Alternative Rate",     pct(self.qalicb_alternative_borrowing_rate,
                                                "qalicb_alternative_borrowing_rate", 2),
             "SUPPLIED: qalicb_alternative_borrowing_rate"
             if self.qalicb_alternative_borrowing_rate is not None else ""),
            (f"Interest Savings to Unwind ({k} yrs)",
             money_or_refused(self.interest_savings_to_unwind, "interest_savings_to_unwind"),
             "DERIVED: QLICI principal x (alt rate - coupons) x years"
             if self.interest_savings_to_unwind is not None else ""),
        ]

        df = pd.DataFrame(rows, columns=["Item", "Value", "Basis"])
        print(f"\nNet Subsidy Analysis — {self.project_name}")
        print("=" * 100)
        print(df.to_string(index=False))
        print()
        print("  " + NET_SUBSIDY_NOTE)
        print("  " + BLENDED_COUPON_NOTE)
        print("  " + INTEREST_SAVINGS_NOTE.format(k=self.unwind_year))
        print("  " + statute.forgiveness_note())
        if self.in_recapture_period:
            print("  " + statute.recapture_disclosure(self.unwind_year))
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "b_loan_forgiveness_rate": self.b_loan_forgiveness_rate,
            "b_loan_forgiven": self.b_loan_forgiven,
            "exit_fee": self.exit_fee,
            "net_subsidy": self.net_subsidy,
            "net_subsidy_pct": self.net_subsidy_pct,
            "blended_qlici_coupon": self.blended_qlici_coupon,
            "qalicb_alternative_borrowing_rate": self.qalicb_alternative_borrowing_rate,
            "interest_savings_to_unwind": self.interest_savings_to_unwind,
            "unwind_year": self.unwind_year,
            "in_recapture_period": self.in_recapture_period,
            "refused": dict(self.refused),
        }


def analyze(deal: NMTCDeal) -> SubsidyResult:
    """
    Compute the QALICB's net subsidy and interest savings.

    * ``b_loan_forgiven`` = B loan x ``deal.b_loan_forgiveness_rate``. The
      rate has no default: B-loan forgiveness is a negotiated exit term, and
      the IRS ATG (p. 17) holds that forgiveness stated in the loan documents
      means the loan is not bona fide debt. Without the rate, the forgiven
      amount, net subsidy and net subsidy % are REFUSED.
    * ``net_subsidy`` = forgiven amount less the exit fee, at unwind.
    * ``interest_savings_to_unwind`` = simple, undiscounted interest over
      years 1..``deal.unwind_year`` on the full QLICI principal at
      ``deal.qalicb_alternative_borrowing_rate`` less the QLICI coupons.
      REFUSED without the QALICB rate.
    * ``blended_qlici_coupon``: principal-weighted average QLICI coupon
      (renamed from ``effective_cost_of_capital``; see BLENDED_COUPON_NOTE).

    Args:
        deal: NMTCDeal instance

    Returns:
        SubsidyResult
    """
    refused = {}
    rate = deal.b_loan_forgiveness_rate
    if rate is None:
        forgiven = net_subsidy = net_pct = None
        for name in ("b_loan_forgiveness_rate", "b_loan_forgiven", "net_subsidy", "net_subsidy_pct"):
            refused[name] = REFUSED_FORGIVENESS
    else:
        forgiven = deal.qlici_b_loan * rate
        net_subsidy = forgiven - deal.exit_fee
        net_pct = net_subsidy / deal.total_project_cost

    alt = deal.qalicb_alternative_borrowing_rate
    k = deal.unwind_year
    if alt is None:
        savings = None
        refused["qalicb_alternative_borrowing_rate"] = REFUSED_ALT_RATE
        refused["interest_savings_to_unwind"] = REFUSED_ALT_RATE
    else:
        annual = (deal.qlici_a_loan * (alt - deal.qlici_a_loan_rate)
                  + deal.qlici_b_loan * (alt - deal.qlici_b_loan_rate))
        savings = annual * k

    # qlici_total = QEI x (1 - cde_fee_rate) > 0 for every constructible deal
    # (QEI > 0 and 0 < cde_fee_rate < 1 are validated), so no zero guard.
    blended_qlici_coupon = (
        (deal.qlici_a_loan * deal.qlici_a_loan_rate) +
        (deal.qlici_b_loan * deal.qlici_b_loan_rate)
    ) / deal.qlici_total

    return SubsidyResult(
        project_name=deal.project_name,
        total_project_cost=deal.total_project_cost,
        qei=deal.qei,
        investor_equity=deal.investor_equity,
        cde_fee=deal.cde_fee,
        qlici_b_loan=deal.qlici_b_loan,
        b_loan_forgiveness_rate=rate,
        b_loan_forgiven=forgiven,
        exit_fee=deal.exit_fee,
        net_subsidy=net_subsidy,
        net_subsidy_pct=net_pct,
        blended_qlici_coupon=blended_qlici_coupon,
        qalicb_alternative_borrowing_rate=alt,
        interest_savings_to_unwind=savings,
        unwind_year=k,
        in_recapture_period=statute.unwind_in_recapture_period(k),
        refused=refused,
        basis={k: v.label() for k, v in deal.basis.items()},
    )
