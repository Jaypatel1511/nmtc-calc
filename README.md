# nmtc-calc

**A correct pedagogical model of a simplified single-CDE New Markets Tax Credit
(NMTC) leveraged structure — not a deal tool.**

`nmtc-calc` models one CDE, one qualified equity investment (QEI), a two-source
Investment Fund (investor equity plus one leverage loan), an interest-only A/B
QLICI loan pair, and an unwind. That is enough to learn how the credit schedule,
the capital stack, the leverage loan and the QALICB's subsidy relate to each
other, and to see how they move. Many NMTC transactions combine allocations
from more than one CDE, which this model cannot represent, and it leaves out
much of what a real closing depends on (see
[What this model does not do](#what-this-model-does-not-do)). Use it to
understand a structure, not to price or underwrite one.

Every capital-stack figure it prints — QEI, total credits, investor equity, the
leverage loan, the CDE fee, QLICI total and the A and B loans, wherever they
appear — is labelled **SUPPLIED** (you entered it) or **DERIVED** (with the rule
used). Computed results such as DSCR, the credit-only IRR or net subsidy are
outputs of those inputs and carry the rule in their notes rather than a label.
Figures it cannot honestly compute are **REFUSED** with a reason, and everything
else still renders.

Part of the [CDFI Superpowers](https://jaypatel1511.github.io/cdfi-superpowers/)
portfolio of open-source tools for community development finance.

## Installation

```bash
# docs-check: skip shell installation command, not executable Python
pip install nmtc-calc
```

## Quickstart

```python
# docs-check: run quickstart
from nmtccalc import NMTCDeal, transaction, credits, investor, subsidy, waterfall

deal = NMTCDeal(
    project_name="Southside Community Health Center",
    total_project_cost=12_000_000,
    nmtc_allocation=10_000_000,          # QEI
    credit_price=0.83,
    leverage_loan_rate=0.045,
    qlici_a_loan_rate=0.045,
    qlici_b_loan_rate=0.010,
    cde_fee_rate=0.02,
    noi=[520_000, 560_000, 600_000, 620_000, 640_000, 660_000, 680_000],
    b_loan_forgiveness_rate=1.0,          # a negotiated term: no default
    qalicb_alternative_borrowing_rate=0.07,
)

tx = transaction.structure(deal)
cr = credits.schedule(deal)
inv = investor.analyze(deal)
sub = subsidy.analyze(deal)
wf = waterfall.analyze(deal)

print(f"Investor equity:        ${tx.investor_equity:,.0f}  ({deal.basis['investor_equity'].label()})")
print(f"Leverage loan:          ${tx.leverage_loan:,.0f}")
print(f"A / B loans:            ${tx.qlici_a_loan:,.0f} / ${tx.qlici_b_loan:,.0f}")
print(f"Deployment at closing:  {tx.closing_qlici_deployment_ratio:.1%} of QEI  (substantially-all test: {tx.substantially_all_test})")
print(f"Allowance dates:        {cr.allowance_years}")
print(f"PV of credits @ 8%:     ${cr.pv_credits:,.0f}")
print(f"Credit-only IRR / MOIC: {inv.credit_only_irr:.2%} / {inv.credit_only_moic:.3f}x")
print(f"Net subsidy at unwind:  ${sub.net_subsidy:,.0f}")
print(f"Interest savings:       ${sub.interest_savings_to_unwind:,.0f} over {sub.unwind_year} years")
print(f"Blended QLICI coupon:   {sub.blended_qlici_coupon:.2%}")
print(f"DSCR by year:           {[round(y.dscr, 2) for y in wf.years]}  (varies: {wf.dscr_varies})")
print(f"Fund shortfall / year:  ${wf.annual_fund_shortfall:,.0f}  (leverage serviced: {wf.leverage_serviced})")
```

Every result object also has `.summary()`, which prints a table with its
disclosures, and `.to_dict()`.

## What each module computes

### `transaction` — the capital stack

`transaction.structure(deal)` returns the stack: QEI, total NMTCs, investor
equity, leverage loan, CDE fee, QLICI total, and the A and B loans, each with its
basis. By default everything after your inputs is DERIVED — a screening model:

| Figure | Rule |
|---|---|
| Total NMTCs | 39% × QEI — the §45D(a)(2) percentages over the §45D(a)(3) allowance dates; the 39% total is cited to the IRS NMTC Audit Technique Guide, not to the statute |
| Investor equity | total NMTCs × credit price |
| Leverage loan | QEI − investor equity (two-source fund) |
| QLICI total | QEI − CDE fee |
| A loan | mirrors the leverage loan |
| B loan | investor equity − CDE fee |

Where real terms exist, supply the A/B split with `qlici_a_loan_amount` and/or
`qlici_b_loan_amount`; the other tranche is DERIVED as the balance, and two
supplied amounts must reconcile to QLICI total. `deal.provenance` and
`deal.basis` expose the label for every figure, as `Provenance` and `Basis`
objects.

It also reports the **closing-date QLICI deployment ratio** (QLICI total / QEI at
face). That is *not* the substantially-all test of 26 CFR §1.45D-1(c)(5), which
the package **refuses** to compute and says why: the 85% is regulatory, the
numerator is §1012 cost basis, there are two tests with different denominators,
it is not testable at closing, and the threshold is 75% in year seven.

`leverage_loan_to_equity_ratio` depends on the credit price alone and is
disclosed as such.

### `credits` — the statutory credit schedule

`credits.schedule(deal)` places the seven credits on the **statutory credit
allowance dates**, t = 0 (the QEI date) through t = 6 (26 U.S.C. §45D(a)(3)): 5%
of QEI on the first three, 6% on the remaining four. The first credit falls on
the day the equity is paid and is not discounted.

### `investor` — credit-only returns

`investor.analyze(deal)` reports `credit_only_irr` and `credit_only_moic`. The
cash flows are the equity paid and the credits received **and nothing else**, so
when they are computed both figures depend on no deal input except the credit
price (credit-only MOIC = 1 / credit price); both are REFUSED when the unwind
falls inside the recapture period. The investor's cash realization is not
modeled; it can fall earlier or later than each allowance date, so the
credit-only IRR is neither a floor nor a ceiling on an IRR measured on cash
realization. They are labelled credit-only, disclosed as such on every
summary, and are not an investor IRR.

### `subsidy` — the QALICB's side

`subsidy.analyze(deal)` reports the B loan forgiven at unwind
(`b_loan_forgiveness_rate` × B loan), the net subsidy (less the exit fee, which assumes the QALICB bears it; the model does not know who does), the
`blended_qlici_coupon`, and `interest_savings_to_unwind` against the QALICB's
own `qalicb_alternative_borrowing_rate`. **Neither rate has a default.** B-loan
forgiveness is a negotiated exit term, and the IRS NMTC Audit Technique Guide
(p. 17) holds that a loan whose documents state it will be forgiven is not bona
fide debt. Leave either rate out and the deal still constructs and renders; only
the figures that depend on it are REFUSED.

### `waterfall` — cash flow, DSCR and the leverage loan

`waterfall.analyze(deal)` runs years 1 to `unwind_year`: NOI (one number, or a
series with one entry per year), interest-only A/B debt service, DSCR, net cash
flow, and the unwind. `dscr_varies` says whether DSCR changes over the years; a
flat NOI is reported as one stabilized figure, not a schedule.

It also **services the leverage loan** at the Investment Fund level and
reconciles it against the QLICI interest reaching the fund and the A-loan
principal repaid at unwind. A structure that cannot fund its leverage loan
raises a `LeverageShortfallWarning`.

Whether guarantee fees enter the DSCR denominator is a **house election**
(`include_guarantee_fee_in_dscr`, default False = excluded, which makes DSCR
higher); it is disclosed on every summary, not attributed to any authority.

### `utils` — sensitivity sweeps

`utils.credit_price_sensitivity(deal)` and `utils.discount_rate_sensitivity(deal)`
sweep one input using `deal.with_credit_price()` / `deal.with_discount_rate()`,
which re-derive DERIVED figures, hold SUPPLIED ones and re-run every check. A
price at which a tranche would go negative renders a REFUSED row. The
credit-only MOIC and IRR columns are the same for every deal at the same prices,
and the table says so.

### `statute` — the law, retrieved

`nmtccalc.statute` holds the schedule, the 7-year period, the recapture rules and
the substantially-all refusal reasons, each quoted from the provision it comes
from.

## An unwind inside the recapture period

The 7-year credit period and recapture period both run from the QEI date to
t = 7 (26 U.S.C. §45D(g)(1); the IRS ATG describes the credit period the same way). The last credit is at
t = 6, so the final year carries full recapture exposure after the last credit
is earned. Redemption of the QEI is a recapture event (§45D(g)(3)(C)).

```python
# docs-check: run recapture
from nmtccalc import NMTCDeal, credits, investor

deal = NMTCDeal(
    project_name="Early Exit", total_project_cost=10_000_000,
    nmtc_allocation=10_000_000, credit_price=0.83, leverage_loan_rate=0.045,
    qlici_a_loan_rate=0.045, qlici_b_loan_rate=0.010, cde_fee_rate=0.02,
    unwind_year=4,
)
cr = credits.schedule(deal)
inv = investor.analyze(deal)
print(cr.statuses)
print(f"Net credits retained: ${cr.net_credits_retained:,.0f}")
sign = "-" if inv.net_benefit < 0 else ""
print(f"Net benefit: {sign}${abs(inv.net_benefit):,.0f}")
print(inv.credit_only_irr, inv.credit_only_moic)
```

## Refusals, warnings and errors

| Name | When |
|---|---|
| `NegativeTrancheError` | construction would produce a negative tranche (e.g. `cde_fee_rate` > 39% × `credit_price` with the B loan derived) |
| `UnbalancedStackError` | a SUPPLIED A and B loan do not add up to QLICI total |
| `LeverageShortfallWarning` | the fund's QLICI interest does not cover leverage interest, or the A-loan principal does not cover the leverage principal |
| REFUSED figures | credit-only IRR/MOIC inside the recapture period; credit-only IRR when the cash flows have no sign change (credit price at or below 0.05/0.39) or the IRR exceeds the solver's bound; DSCR when QLICI debt service is zero; net subsidy without a forgiveness rate; interest savings without a QALICB rate; the substantially-all test always |

## What this model does not do

Multi-CDE structures; state NMTC programs and other state tax credits;
historic tax credits; ongoing CDE or
sub-CDE fees; fund-level taxable income, the put or disposition value, and exit
taxes in any return; §45D(h) basis reduction and the §38 tax-capacity limit;
the reinvestment rule as an ongoing obligation; tax on cancellation-of-debt
income from a forgiven B loan; the day-level boundary at the seventh
anniversary; sub-annual cash timing (credits are placed on their statutory dates;
the timing of the investor's cash realization is not modeled).

## Tests and gates

499 tests, run in CI on Python 3.9–3.12.

```bash
# docs-check: skip shell commands; CI runs these, not this gate
pytest tests/                              # the suite, from a checkout
python tools/check_sdist.py                # the sdist ships and passes its own suite
python tools/mutation_gate.py              # mutation testing, floor derived from the baseline
python tools/docs_check.py --root .        # this README against the installed wheel
```

## License

MIT — see [LICENSE](LICENSE).
