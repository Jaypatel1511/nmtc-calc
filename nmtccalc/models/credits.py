from dataclasses import dataclass
import pandas as pd
import numpy as np

from nmtccalc import statute
from nmtccalc.data.schema import NMTCDeal


@dataclass
class CreditScheduleResult:
    """Output object from the NMTC credit schedule.

    ``allowance_years[i]`` is the credit allowance date (years after the QEI
    date) on which ``annual_credits[i]`` is determined. Per §45D(a)(3) these
    are t=0..6. ``statuses[i]`` is ALLOWED, RECAPTURED or NOT ALLOWABLE given
    ``unwind_year``. ``net_credits_retained`` is the credits the investor
    keeps after the unwind; it is 0 when the unwind is inside the recapture
    period.
    """
    project_name: str
    qei: float
    total_nmtcs: float
    annual_credits: list
    cumulative_credits: list
    pv_credits: float
    discount_rate: float
    allowance_years: list
    statuses: list
    unwind_year: int
    in_recapture_period: bool
    net_credits_retained: float
    basis: dict

    def summary(self) -> pd.DataFrame:
        rows = []
        for t, rate, credit, cumulative, status in zip(
            self.allowance_years, statute.APPLICABLE_PERCENTAGES,
            self.annual_credits, self.cumulative_credits, self.statuses,
        ):
            rows.append({
                "Allowance Date": f"t={t}" + (" (QEI date)" if t == 0 else ""),
                "Credit Rate": statute.pct_label(rate),
                "Credit ($)": f"${credit:,.0f}",
                "Cumulative ($)": f"${cumulative:,.0f}",
                "Status": status,
            })

        df = pd.DataFrame(rows)
        print(f"\nNMTC Credit Schedule — {self.project_name}")
        print(f"QEI: ${self.qei/1e6:.2f}MM [{self.basis.get('qei', '')}]")
        print(f"Total NMTCs ({statute.pct_label(statute.TOTAL_CREDIT_RATE)} × QEI): "
              f"${self.total_nmtcs/1e6:.2f}MM [{self.basis.get('total_nmtcs', '')}]")
        print("-" * 72)
        print(df.to_string(index=False))
        print("-" * 72)
        print(f"  Total NMTCs:          ${self.total_nmtcs:,.0f}  [{self.basis.get('total_nmtcs', '')}]")
        print(f"  NET CREDITS RETAINED: ${self.net_credits_retained:,.0f}  "
              f"(unwind at t={self.unwind_year})")
        print(f"  PV of Credits:        ${self.pv_credits:,.0f}  "
              f"(@ {self.discount_rate*100:.1f}% discount rate, before any recapture)")
        print()
        print("  " + statute.timing_convention_disclosure())
        if self.in_recapture_period:
            print("  " + statute.recapture_disclosure(self.unwind_year))
        elif self.unwind_year == statute.RECAPTURE_PERIOD_END_YEAR:
            print("  " + statute.boundary_disclosure())
        print()
        return df

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "qei": self.qei,
            "total_nmtcs": self.total_nmtcs,
            "annual_credits": self.annual_credits,
            "cumulative_credits": self.cumulative_credits,
            "pv_credits": self.pv_credits,
            "discount_rate": self.discount_rate,
            "allowance_years": self.allowance_years,
            "statuses": self.statuses,
            "unwind_year": self.unwind_year,
            "in_recapture_period": self.in_recapture_period,
            "net_credits_retained": self.net_credits_retained,
        }


def schedule(deal: NMTCDeal) -> CreditScheduleResult:
    """
    Generate the NMTC credit schedule on the statutory credit allowance dates.

    Per 26 U.S.C. §45D(a)(3) the credit allowance dates are the date the QEI
    is initially made (t=0) and each of the 6 anniversary dates thereafter
    (t=1..6). Per §45D(a)(2) the credit is 5% of the QEI on the first 3 dates
    and 6% on the remainder. The total, 39% of QEI, is not stated in the
    statute; it is cited to the IRS NMTC Audit Technique Guide.

    ``pv_credits`` discounts each credit from its allowance date: the t=0
    credit is not discounted. It is the PV of the credits before any
    recapture.

    If ``deal.unwind_year`` is inside the 7-year recapture period (t < 7),
    the redemption is a recapture event (§45D(g)(3)(C)): credits already
    allowed are RECAPTURED, later dates are NOT ALLOWABLE, and
    ``net_credits_retained`` is 0.

    Args:
        deal: NMTCDeal instance

    Returns:
        CreditScheduleResult
    """
    allowance_years = list(statute.CREDIT_ALLOWANCE_YEARS)
    annual_credits = [deal.qei * rate for rate in statute.APPLICABLE_PERCENTAGES]
    cumulative_credits = [float(c) for c in np.cumsum(annual_credits)]

    pv_credits = sum(
        credit / ((1 + deal.discount_rate) ** t)
        for t, credit in zip(allowance_years, annual_credits)
    )

    statuses = list(statute.allowance_statuses(deal.unwind_year))
    in_period = statute.unwind_in_recapture_period(deal.unwind_year)
    net_retained = sum(
        c for c, s in zip(annual_credits, statuses) if s == statute.STATUS_ALLOWED
    )

    return CreditScheduleResult(
        project_name=deal.project_name,
        qei=deal.qei,
        total_nmtcs=deal.total_nmtcs,
        annual_credits=annual_credits,
        cumulative_credits=cumulative_credits,
        pv_credits=pv_credits,
        discount_rate=deal.discount_rate,
        allowance_years=allowance_years,
        statuses=statuses,
        unwind_year=deal.unwind_year,
        in_recapture_period=in_period,
        net_credits_retained=net_retained,
        basis={k: v.label() for k, v in deal.basis.items()},
    )
