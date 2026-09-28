from dataclasses import dataclass
from typing import Optional
import pandas as pd

from nmtccalc import statute
from nmtccalc.data.schema import NMTCDeal


REFUSED = "REFUSED"

CREDIT_ONLY_NOTE = (
    "CREDIT-ONLY: these cash flows are the equity paid and the credits received, "
    "and nothing else: no fund-level taxable income or tax drag, no put or "
    "disposition value, no exit tax, no sub-annual timing, no §45D(h) basis "
    "reduction, no §38 tax-capacity limit. Investor equity is always total NMTCs x "
    "credit price, so every flow is proportional to QEI and both figures depend on "
    "the credit price ALONE: credit-only MOIC = 1 / credit price, and two deals "
    "at the same price report the same credit-only IRR whatever their size, rates "
    "or fees. They are not an investor IRR or MOIC."
)

REFUSAL_RECAPTURE = (
    "REFUSED: the unwind at t={k} is inside the 7-year recapture period, so every "
    "credit is recaptured (plus nondeductible interest this package does not "
    "compute). No return is computed on credits the investor does not keep."
)

REFUSAL_NO_SIGN_CHANGE = (
    "REFUSED: the cash flows have no sign change, so no IRR exists. At a credit "
    "price at or below {threshold:.4f} the t=0 credit ({first}) is at least the "
    "equity paid on the same date."
)


@dataclass
class InvestorResult:
    """Output object from investor economics analysis.

    ``credit_only_irr`` and ``credit_only_moic`` are None when refused;
    ``refused_reason`` then says why. Both are refused when the unwind is
    inside the recapture period; the IRR alone is refused when the flows have
    no sign change. They are CREDIT-ONLY figures, not an investor IRR/MOIC:
    see ``CREDIT_ONLY_NOTE``. ``cash_flows[t]`` is the investor's net flow at t years after the QEI
    date: the equity outflow and the first credit are both at t=0.
    """
    project_name: str
    investor_equity: float
    annual_credits: list
    total_nmtcs: float
    credit_price: float
    gross_benefit: float
    net_benefit: float
    credit_only_irr: Optional[float]
    credit_only_moic: Optional[float]
    net_credits_retained: float
    unwind_year: int
    in_recapture_period: bool
    cash_flows: list
    refused_reason: Optional[str]

    def summary(self) -> pd.DataFrame:
        rows = []
        for t, credit, status in zip(
            statute.CREDIT_ALLOWANCE_YEARS, self.annual_credits,
            statute.allowance_statuses(self.unwind_year),
        ):
            rows.append({
                "Allowance Date": f"t={t}",
                "Tax Credit ($)": f"${credit:,.0f}",
                "Status": status,
            })

        df = pd.DataFrame(rows)
        print(f"\nInvestor Economics — {self.project_name}")
        print(f"Equity In (t=0): ${self.investor_equity/1e6:.2f}MM  |  "
              f"Credit Price: ${self.credit_price:.2f}/$1")
        print("-" * 60)
        print(df.to_string(index=False))
        print("-" * 60)
        print(f"  Total NMTCs:          ${self.total_nmtcs:,.0f}")
        print(f"  NET CREDITS RETAINED: ${self.net_credits_retained:,.0f}")
        print(f"  Gross Benefit:        ${self.gross_benefit:,.0f}")
        print(f"  Net Benefit:          ${self.net_benefit:,.0f}")
        print(f"  Credit-only MOIC:     "
              f"{f'{self.credit_only_moic:.2f}x' if self.credit_only_moic is not None else REFUSED}")
        print(f"  Credit-only IRR:      "
              f"{f'{self.credit_only_irr*100:.1f}%' if self.credit_only_irr is not None else REFUSED}")
        if self.refused_reason:
            print(f"  {self.refused_reason}")
        print("  " + CREDIT_ONLY_NOTE)
        print("  " + statute.timing_convention_disclosure())
        if self.in_recapture_period:
            print("  " + statute.recapture_disclosure(self.unwind_year))
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "investor_equity": self.investor_equity,
            "total_nmtcs": self.total_nmtcs,
            "credit_price": self.credit_price,
            "gross_benefit": self.gross_benefit,
            "net_benefit": self.net_benefit,
            "credit_only_irr": self.credit_only_irr,
            "credit_only_moic": self.credit_only_moic,
            "net_credits_retained": self.net_credits_retained,
            "unwind_year": self.unwind_year,
            "in_recapture_period": self.in_recapture_period,
            "cash_flows": self.cash_flows,
            "refused_reason": self.refused_reason,
        }


def _npv(rate: float, cash_flows: list) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _has_single_outflow_then_inflows(cash_flows: list) -> bool:
    """True for [negative, non-negative, ...] with at least one positive inflow.

    For such a vector NPV is strictly decreasing in the rate on (-1, inf), so
    exactly one IRR exists.
    """
    if not cash_flows or cash_flows[0] >= 0:
        return False
    rest = cash_flows[1:]
    return all(cf >= 0 for cf in rest) and any(cf > 0 for cf in rest)


def _compute_irr(cash_flows: list, tol: float = 1e-12, max_iter: int = 500) -> Optional[float]:
    """IRR by bisection on a bracket, for a single-outflow-then-inflows vector.

    Returns None when the vector does not have that shape (no unique IRR). The
    bracket is (-1, hi], with hi doubled until NPV(hi) < 0.
    """
    if not _has_single_outflow_then_inflows(cash_flows):
        return None
    lo, hi = -1.0 + 1e-9, 1.0
    while _npv(hi, cash_flows) > 0:
        hi *= 2.0
        if hi > 1e9:
            return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if _npv(mid, cash_flows) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2.0


def analyze(deal: NMTCDeal) -> InvestorResult:
    """
    Compute investor economics for an NMTC transaction.

    The investor pays its equity at t=0 and holds the QEI through the credit
    allowance dates t=0..6 (§45D(a)(3)). The first credit falls on the QEI
    date, so the t=0 cash flow is the equity outflow plus the first credit.

    These cash flows carry the equity and the credits only, so the results are
    named ``credit_only_irr`` / ``credit_only_moic``. Investor equity is always
    total NMTCs x credit price, so every flow is proportional to QEI and both
    figures depend on the credit price alone (MOIC = 1 / credit price). The
    disclosure ``CREDIT_ONLY_NOTE`` renders with every summary.

    When ``deal.unwind_year`` is inside the 7-year recapture period, every
    credit is recaptured (§45D(g)(3)(C), §45D(g)(2)): ``net_credits_retained``
    is 0, ``net_benefit`` is the equity lost, and ``irr``/``moic`` are REFUSED.

    Args:
        deal: NMTCDeal instance

    Returns:
        InvestorResult
    """
    from nmtccalc.models.credits import schedule

    credit_result = schedule(deal)
    annual_credits = credit_result.annual_credits
    retained = credit_result.net_credits_retained
    in_period = credit_result.in_recapture_period

    gross_benefit = retained
    net_benefit = gross_benefit - deal.investor_equity

    cash_flows = [0.0] * (max(statute.CREDIT_ALLOWANCE_YEARS) + 1)
    cash_flows[0] -= deal.investor_equity
    for t, credit in zip(statute.CREDIT_ALLOWANCE_YEARS, annual_credits):
        cash_flows[t] += credit

    irr: Optional[float] = None
    moic: Optional[float] = None
    reason: Optional[str] = None
    if in_period:
        reason = REFUSAL_RECAPTURE.format(k=deal.unwind_year)
    else:
        moic = retained / deal.investor_equity
        irr = _compute_irr(cash_flows)
        if irr is None:
            reason = REFUSAL_NO_SIGN_CHANGE.format(
                threshold=statute.APPLICABLE_PERCENTAGES[0] / statute.TOTAL_CREDIT_RATE,
                first=f"${annual_credits[0]:,.0f}",
            )

    return InvestorResult(
        project_name=deal.project_name,
        investor_equity=deal.investor_equity,
        annual_credits=annual_credits,
        total_nmtcs=deal.total_nmtcs,
        credit_price=deal.credit_price,
        gross_benefit=gross_benefit,
        net_benefit=net_benefit,
        credit_only_irr=irr,
        credit_only_moic=moic,
        net_credits_retained=retained,
        unwind_year=deal.unwind_year,
        in_recapture_period=in_period,
        cash_flows=cash_flows,
        refused_reason=reason,
    )
