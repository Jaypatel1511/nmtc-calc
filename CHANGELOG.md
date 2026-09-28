# Changelog

All notable changes to nmtc-calc are documented here.
Prior release history predates this file.

## [0.3.0] — unreleased (built 2026-09-27; not tagged or published)

**Breaking.** A correctness and honest-labelling release built to the
2026-09-22 methodology audit's §9, items 0–11. The framing it ships under:
**a correct pedagogical model of a simplified single-CDE NMTC structure, not a
deal tool.** There are no known users of 0.2.1.

### Fixed
- **Credit timing (26 U.S.C. §45D(a)(3)).** Credits are placed on the seven
  statutory credit allowance dates, t=0 (the QEI date) through t=6. 0.2.1
  placed them at t=1…t=7, discounting every credit one year too many:
  `pv_credits` rises 8.00% at the default 8% rate, and the credit-only IRR at
  a 0.83 credit price rises from 4.69% to 6.34%.
- **The leverage loan is serviced.** `waterfall.analyze` services the
  Investment Fund's leverage loan against the QLICI interest reaching the fund
  and reconciles A-loan principal against leverage principal at unwind; any
  shortfall is reported and emitted as `LeverageShortfallWarning`. In 0.2.1
  `leverage_loan_rate` moved no transaction, credit, investor or waterfall
  output.
- **Negative tranches are refused at construction** (`NegativeTrancheError`).
  0.2.1 built a negative B loan whenever `cde_fee_rate > 0.39 × credit_price`.
- **Subsidy repaired, not withdrawn.** Interest savings use the QALICB's own
  alternative borrowing rate (0.2.1 used the fund's leverage rate and reported
  $4.04MM of savings on a $3.04MM B loan). B-loan forgiveness is an input with
  no default; "typically forgiven" is gone and the IRS ATG's bona-fide-debt
  passage (p. 17) is quoted.
- **DSCR.** NOI may be a series; `dscr_varies` says whether DSCR changes; a flat
  NOI is reported as one stabilized figure, not a seven-row schedule.
- **Guarantee fees and DSCR.** The claim that excluding guarantee fees was
  "standard NMTC underwriting convention" is withdrawn. Exclusion is now a
  disclosed house election (`HOUSE_GUARANTEE_FEE_IN_DSCR`), and
  `include_guarantee_fee_in_dscr=True` gives the opposite treatment.
- **The 39% total** is derived from the §45D(a)(2)–(3) schedule and cited to
  the IRS NMTC Audit Technique Guide, not to §45D.
- Every numeric input must be a finite real number (0.2.1 accepted NaN), and
  is stored as a float (a `Fraction` no longer crashes `summary()`).
- Leverage, A, B, guarantee-fee and exit-fee rates must lie in [0, 1)
  (0.2.1 accepted negative and 300% rates).
- `NMTCDeal` is frozen: assigning an attribute after construction raises, so
  no refusal can be bypassed by mutating a built deal.
- No silent DSCR: with zero QLICI debt service the summary says
  "DSCR REFUSED"; without NOI it says DSCR was not computed.

### Added
- `nmtccalc.statute`: the schedule, the 7-year period (§45D(g)(1); 26 CFR
  §1.45D-1(c)(5)(i)) ending at t=7, recapture rules, the substantially-all
  refusal reasons and the ATG passage, each quoted from a source retrieved on
  2026-09-27.
- `NMTCDeal.unwind_year` (default 7). An unwind before t=7 is inside the
  recapture period: statuses RECAPTURED / NOT ALLOWABLE, net credits retained
  $0, credit-only IRR/MOIC REFUSED, disclosure rendered.
- Provenance: `NMTCDeal.provenance` / `.basis` (`Provenance`, `Basis`) label
  every stack figure DERIVED or SUPPLIED with its rule; `transaction.summary()`
  prints it. SUPPLIED A/B split via `qlici_a_loan_amount` /
  `qlici_b_loan_amount` (`UnbalancedStackError` if two do not reconcile).
- `NMTCDeal.with_credit_price` / `with_discount_rate`; the sweeps use them.
- `NMTCDeal.b_loan_forgiveness_rate`, `qalicb_alternative_borrowing_rate`,
  `include_guarantee_fee_in_dscr`; `noi` accepts a series (list, tuple, range,
  numpy array, pandas Series); `unwind_year` accepts any integer type, at most
  `MAX_UNWIND_YEAR` = 30 (a sanity bound, not statutory).
- Provenance labels inline in the credits, investor, subsidy (a Basis column)
  and waterfall summaries, not only the transaction summary.
- The waterfall shows the fund shortfall counting A-loan interest only beside
  the A+B figure, to bracket the fund's position.
- Sweeps: a "Leverage Serviced" column; REFUSED cells say why; the discount
  sweep discloses that PV / Face Value is deal-invariant.
- `TransactionResult.closing_qlici_deployment_ratio`, and
  `substantially_all_test = "REFUSED"` with five reasons
  (§45D(b)(1)(B); §1.45D-1(c)(5)(i)–(v); (d)(2)(i)).
- Disclosures on the face of every summary: credit-only invariance, blended
  coupon, leverage/equity invariance, fund line, timing convention, recapture
  boundary, forgiveness/ATG, guarantee-fee election, sweep invariance.
- Gates: `tools/mutation_gate.py` (533 mutants including 51 text mutants on
  disclosure and refusal strings, 514 killed, 96.4%; floor derived from the
  baseline records; every survivor has a written reason anchored to its source
  line; a ratchet against the main-branch baseline fails on a floor drop or a
  killed->survived mutant unless an override lists it with a reason — on this
  first release main has no baseline and the ratchet says so and skips),
  `tools/check_sdist.py` (the sdist ships and passes its own suite; test set
  must equal the checkout's), `tools/docs_check.py` (copied verbatim from
  nmtc-mapper; README vs installed wheel), and CI jobs for each plus
  `release-invocation`, which runs release.yml's exact wheel-test command on
  every PR.

### Changed (breaking)
- `NMTCDeal.compliance_years` removed (it could only be 7). `NMTCDeal` is
  frozen; rates outside [0, 1) and `unwind_year` above 30 are refused.
- `InvestorResult.refused_code`; `WaterfallResult.dscr_refused_reason`,
  `annual_fund_shortfall_a_only`, `qlici_b_loan`; every result class carries
  `basis`.
- `SubsidyResult.summary()` returns Item / Value / Basis columns; the "Less:"
  rows are renamed ("CDE Fee (upfront)", "Exit Fee at Unwind").
- `InvestorResult.irr` / `.moic` → `credit_only_irr` / `credit_only_moic`
  (Optional; None when refused). `gross_benefit` / `net_benefit` use net
  credits retained. New fields `net_credits_retained`, `unwind_year`,
  `in_recapture_period`, `cash_flows`, `refused_reason`.
- `SubsidyResult.effective_cost_of_capital` → `blended_qlici_coupon`;
  `interest_savings_7yr` → `interest_savings_to_unwind`; `net_subsidy`,
  `net_subsidy_pct` are Optional (None without a forgiveness rate) and now net
  of the exit fee; new fields for the two rates, `b_loan_forgiven`, `exit_fee`,
  `unwind_year`, `in_recapture_period`, `refused`.
- `TransactionResult.leverage_ratio` → `leverage_loan_to_equity_ratio`; new
  fields for the deployment ratio, the refused test, `basis`, `provenance`.
- `WaterfallResult.net_year7_subsidy` → `net_subsidy_at_unwind`;
  `b_loan_forgiven` Optional; many new fund-line and flag fields. The waterfall
  runs years 1..`unwind_year`.
- `credits.schedule()` rows are labelled `t=0`…`t=6` with a status; new
  result fields `allowance_years`, `statuses`, `unwind_year`,
  `in_recapture_period`, `net_credits_retained`.
- Sensitivity columns renamed "Credit-only MOIC" / "Credit-only IRR";
  net-subsidy columns REFUSED without a forgiveness rate.
- New fields on the result classes are required constructor arguments (no
  placeholder defaults), except the three new `WaterfallYear` fund-line fields,
  which must follow 0.2.1's defaulted `b_loan_forgiven` / `exit_fee`; all 0.2.1
  fields keep their positions.

### Packaging
- The sdist ships `tests/conftest.py` (0.2.1's did not: 52 of its 53 tests
  errored), LICENSE, CHANGELOG and the gate tools. The wheel ships LICENSE
  (SPDX `MIT`), classifiers and `py.typed`. `authors` carries the human name.
- `release.yml`: the installed-version check now runs outside the checkout and
  asserts a site-packages origin (it used to import `./nmtccalc`); a new
  `test-sdist` job checks the tarball that will be published.
- README rewritten; the example notebook rebuilt, run against the installed
  wheel, outputs stored.

### Tests
- 446 tests, including fixtures where project cost differs from QEI and a
  SUPPLIED A loan differs from the leverage loan (the shared
  `conftest.sample_deal` fixture made both pairs equal, which hid six
  wrong-operand mutants), and exact-text tests
  for every rendered disclosure. Two tests that pinned defects as correct were
  replaced:
  `test_avg_dscr_equals_min_when_noi_constant` and `test_moic_math`.

### Divergences from the READY record and the methodology audit, disclosed
Each is a deliberate judgment, stated in code where it renders:
- **Fund line counts A- and B-loan interest** as reaching the fund
  (`waterfall.FUND_LINE_DISCLOSURE`: neither a floor nor a ceiling). The audit
  measured its shortfall on A-loan interest alone.
- **No user-settable cash-timing lag.** The audit asked for one; credits sit on
  their statutory dates and the lag is disclosed
  (`statute.TIMING_CONVENTION_DISCLOSURE`).
- **Credit-only IRR is also REFUSED when the flows have no sign change**
  (credit price at or below 0.05/0.39 ≈ 0.1282, where the t=0 credit covers the
  equity). MOIC still computes. Not in the READY record.
- **Only the A/B split can be SUPPLIED.** Investor equity (credits × price) and
  the leverage loan (QEI − equity) are identities of this model
  (`NMTCDeal` docstring).
- **An allowance date in the unwind year is NOT ALLOWABLE**, not RECAPTURED;
  it changes no figure (`statute.allowance_statuses`).
- **Forgiveness and QALICB rates have no default but are not required at
  construction**: omitting them refuses only the dependent figures (as the
  runbook's step 6 expects). READY says "required, no default".
- **`interest_savings_to_unwind`** (not READY's `interest_savings_7yr`): the
  figure follows `unwind_year`, so a "7yr" name would be false; it covers the
  full QLICI principal, A and B, not the B loan only.
- **`net_subsidy` is net of the exit fee**, and excludes interest paid,
  guarantee fees, the put price, COD-income tax and time value
  (`subsidy.NET_SUBSIDY_NOTE`).
- **Rename targets** READY did not name: `net_subsidy_at_unwind`,
  `leverage_loan_to_equity_ratio`.
- **Mutation score 96.4%**, not READY's 98.1%: a different operator set and
  population (533 vs 528 mutants, including text mutants).
- **Credit-only MOIC still renders when the IRR is refused at the solver
  bound**: it is credits / equity = 1 / price (about 7.80x there), a correct
  credit-only figure.

### Not modeled (recorded)
Multi-CDE (first 0.4.0 candidate); state and historic credits; ongoing CDE
fees; fund taxable income, put value and exit tax in any return; §45D(h) basis
reduction; the §38 limit; the reinvestment rule as an ongoing obligation;
COD-income tax on a forgiven B loan; the day-level t=7 boundary;
`_compute_irr`'s private-path behaviour beyond its public-API reach.

## [0.2.1] — 2026-06-23

### Changed
- **`__version__` is now derived from installed package metadata** via
  `importlib.metadata.version("nmtc-calc")` instead of a hardcoded string.
  This fixes a drift where the shipped wheel reported `__version__ == "0.1.0"`
  while the distribution had been bumped to `0.2.0` — `pyproject.toml` is now
  the single authoritative source of the version.

### Added
- **CI / release infrastructure** — `ci.yml` (test matrix on Python 3.9–3.12,
  all actions SHA-pinned) and a tag-triggered `release.yml` that verifies the
  tag matches `pyproject.toml`, builds the wheel, tests the installed wheel in a
  fresh venv, and publishes to PyPI via an OIDC Trusted Publisher (no API token).

No behavioral or API change — this is a hygiene-only release.
