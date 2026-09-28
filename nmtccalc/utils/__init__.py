import warnings

import pandas as pd


DISCOUNT_INVARIANCE_NOTE = (
    "The PV / Face Value column depends on the discount rate alone: it is the "
    "present value of the statutory 5%/6% schedule divided by its 39% total, so it "
    "is the same for every deal at the same rates. PV of Credits scales with QEI."
)

LEVERAGE_COLUMN_NOTE = (
    "Leverage Serviced is the waterfall's reconciliation at each price: 'yes', or "
    "the annual interest shortfall and/or the principal gap. The leverage loan "
    "moves with the price; a SUPPLIED A loan does not."
)

REFUSED_CELL = {
    "recapture": "REFUSED (unwind inside recapture period)",
    "no_sign_change": "REFUSED (no sign change)",
    "irr_bound": "REFUSED (IRR above solver bound)",
}

SWEEP_INVARIANCE_NOTE = (
    "Where computed, the Credit-only MOIC and Credit-only IRR columns depend on no "
    "deal input except the credit price: they are the same for every deal at the "
    "same prices, whatever its size, rates or fees (MOIC = 1 / price). They are "
    "REFUSED when the unwind falls inside the recapture period. They are a lookup table of the credit price, "
    "not this deal's investor returns. Equity and leverage scale with QEI; net "
    "subsidy depends on the A/B split, the fee and the forgiveness rate."
)


def credit_price_sensitivity(deal, prices=None) -> pd.DataFrame:
    """
    Sweep credit_price and show equity, leverage, credit-only MOIC/IRR, and net
    subsidy. The credit-only columns are deal-invariant; SWEEP_INVARIANCE_NOTE
    renders with the table.

    Args:
        deal: NMTCDeal base case
        prices: credit prices to sweep (default: $0.70–$0.90 in $0.02 steps)

    Returns:
        DataFrame with one row per credit price
    """
    from nmtccalc.models import investor, subsidy, waterfall

    if prices is None:
        prices = [round(p / 100, 2) for p in range(70, 92, 2)]

    from nmtccalc.exceptions import NegativeTrancheError

    rows = []
    for price in prices:
        try:
            d = deal.with_credit_price(price)
        except NegativeTrancheError:
            rows.append({
                "Credit Price": f"${price:.2f}",
                "Equity ($MM)": "REFUSED",
                "Leverage Loan ($MM)": "REFUSED",
                "Credit-only MOIC": "REFUSED",
                "Credit-only IRR": "REFUSED",
                "Net Subsidy ($MM)": "REFUSED",
                "Subsidy % of Cost": "REFUSED (negative tranche)",
                "Leverage Serviced": "REFUSED (negative tranche)",
            })
            continue
        inv = investor.analyze(d)
        sub = subsidy.analyze(d)
        with warnings.catch_warnings():
            # The shortfall is reported in the Leverage Serviced cell instead.
            warnings.simplefilter("ignore")
            wf = waterfall.analyze(d)
        if wf.leverage_serviced:
            serviced = "yes"
        else:
            parts = []
            if wf.annual_fund_shortfall > 0:
                parts.append(f"short ${wf.annual_fund_shortfall:,.0f}/yr")
            if wf.leverage_principal_gap > 0:
                parts.append(f"principal gap ${wf.leverage_principal_gap:,.0f}")
            serviced = "NO: " + ", ".join(parts)
        rows.append({
            "Credit Price": f"${price:.2f}",
            "Equity ($MM)": round(d.investor_equity / 1e6, 2),
            "Leverage Loan ($MM)": round(d.leverage_loan / 1e6, 2),
            "Credit-only MOIC": (round(inv.credit_only_moic, 3) if inv.credit_only_moic is not None
                                 else REFUSED_CELL[inv.refused_code]),
            "Credit-only IRR": (f"{inv.credit_only_irr * 100:.1f}%" if inv.credit_only_irr is not None
                                else REFUSED_CELL[inv.refused_code]),
            "Net Subsidy ($MM)": round(sub.net_subsidy / 1e6, 2) if sub.net_subsidy is not None else "REFUSED",
            "Subsidy % of Cost": (f"{sub.net_subsidy_pct * 100:.1f}%" if sub.net_subsidy_pct is not None
                                  else "REFUSED (no forgiveness rate)"),
            "Leverage Serviced": serviced,
        })

    df = pd.DataFrame(rows)
    print(f"\nCredit Price Sensitivity — {deal.project_name}")
    print("=" * 75)
    print(df.to_string(index=False))
    print()
    print(SWEEP_INVARIANCE_NOTE)
    print(LEVERAGE_COLUMN_NOTE)
    print()
    return df


def discount_rate_sensitivity(deal, rates=None) -> pd.DataFrame:
    """
    Sweep discount_rate and show PV of credits vs face value.

    Args:
        deal: NMTCDeal base case
        rates: discount rates to sweep (default: 5%–12%)

    Returns:
        DataFrame with one row per discount rate
    """
    from nmtccalc.models import credits

    if rates is None:
        rates = [r / 100 for r in range(5, 13)]

    rows = []
    for rate in rates:
        d = deal.with_discount_rate(rate)
        cr = credits.schedule(d)
        rows.append({
            "Discount Rate": f"{rate * 100:.0f}%",
            "PV of Credits ($MM)": round(cr.pv_credits / 1e6, 3),
            "PV / Face Value": f"{cr.pv_credits / cr.total_nmtcs * 100:.1f}%",
        })

    df = pd.DataFrame(rows)
    print(f"\nDiscount Rate Sensitivity — {deal.project_name}")
    print("=" * 45)
    print(df.to_string(index=False))
    print()
    print(DISCOUNT_INVARIANCE_NOTE)
    print()
    return df
