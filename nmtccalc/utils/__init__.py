import dataclasses
import pandas as pd


def credit_price_sensitivity(deal, prices=None) -> pd.DataFrame:
    """
    Sweep credit_price and show investor IRR, MOIC, equity, and net subsidy.

    Args:
        deal: NMTCDeal base case
        prices: credit prices to sweep (default: $0.70–$0.90 in $0.02 steps)

    Returns:
        DataFrame with one row per credit price
    """
    from nmtccalc.models import investor, subsidy

    if prices is None:
        prices = [round(p / 100, 2) for p in range(70, 92, 2)]

    rows = []
    for price in prices:
        d = dataclasses.replace(deal, credit_price=price)
        inv = investor.analyze(d)
        sub = subsidy.analyze(d)
        rows.append({
            "Credit Price": f"${price:.2f}",
            "Equity ($MM)": round(d.investor_equity / 1e6, 2),
            "Leverage Loan ($MM)": round(d.leverage_loan / 1e6, 2),
            "MOIC": round(inv.moic, 3),
            "IRR": f"{inv.irr * 100:.1f}%",
            "Net Subsidy ($MM)": round(sub.net_subsidy / 1e6, 2),
            "Subsidy % of Cost": f"{sub.net_subsidy_pct * 100:.1f}%",
        })

    df = pd.DataFrame(rows)
    print(f"\nCredit Price Sensitivity — {deal.project_name}")
    print("=" * 75)
    print(df.to_string(index=False))
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
        d = dataclasses.replace(deal, discount_rate=rate)
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
    return df
