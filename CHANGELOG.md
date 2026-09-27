# Changelog

All notable changes to nmtc-calc are documented here.
Prior release history predates this file.

## [Unreleased] — 0.3.0 (in progress; Phase A of the methodology audit's §9, items 0–5)

**Breaking.** Nothing here is released. Items 6–11 of the audit's build list
are not yet done; see the end of this entry.

### Fixed
- **Credit timing (26 U.S.C. §45D(a)(3)).** Credits are placed on the seven
  statutory credit allowance dates, t=0 (the QEI date) through t=6. 0.2.1
  placed them at t=1…t=7, discounting every credit one year too many:
  `pv_credits` rises exactly 8.00% at the default 8% rate, and investor IRR at
  a 0.83 credit price rises from 4.69% to 6.34%.
- **The leverage loan is serviced.** `waterfall.analyze` now services the
  Investment Fund's leverage loan against the QLICI interest reaching the fund
  and reconciles A-loan principal against leverage principal at unwind. Any
  shortfall is reported on the result and emitted as
  `nmtccalc.LeverageShortfallWarning`. In 0.2.1 `leverage_loan_rate` did not
  affect any transaction, credit, investor or waterfall output.
- **Negative tranches are refused at construction**
  (`nmtccalc.NegativeTrancheError`, a `ValueError`). 0.2.1 built a deal with a
  negative B loan whenever `cde_fee_rate > 0.39 × credit_price` and rendered a
  negative subsidy and an inflated DSCR. The credit-price sweep marks such rows
  REFUSED instead of failing the table.
- Every numeric input must be a finite real number (0.2.1 accepted NaN).

### Added
- `nmtccalc.statute`: the §45D(a)(2)–(3) schedule, the 7-year period
  (§45D(g)(1); 26 CFR §1.45D-1(c)(5)(i)) ending at t=7, and the 39% total,
  derived from the schedule and cited to the IRS NMTC Audit Technique Guide
  (it is not stated in the statute or the regulation).
- `NMTCDeal.unwind_year` (default 7). An unwind before t=7 is inside the
  recapture period: allowance dates show RECAPTURED / NOT ALLOWABLE, net
  credits retained are $0, investor `irr` and `moic` are REFUSED (None, with
  `refused_reason`), and the recapture disclosure renders.
- Provenance: `NMTCDeal.provenance` / `.basis` label every capital-stack
  figure DERIVED or SUPPLIED, with the rule used, and `transaction.summary()`
  prints it inline. Where real terms exist the A/B split can be SUPPLIED
  (`qlici_a_loan_amount`, `qlici_b_loan_amount`); two supplied amounts must
  reconcile to QLICI total (`nmtccalc.UnbalancedStackError`).
- `NMTCDeal.with_credit_price` / `with_discount_rate`, which re-derive DERIVED
  figures, hold SUPPLIED ones and re-run every check; the sweeps use them.
- `tools/mutation_gate.py` and `tools/mutation_baseline.json`: mutation testing
  as the release gate, with the floor derived from the baseline's per-mutant
  records. Current baseline: 381 mutants, 325 killed (85.3%), every survivor
  classified with a written reason.

### Changed (breaking)
- `NMTCDeal.compliance_years` is removed. It could only ever be 7; the 7-year
  period is a statutory constant in `nmtccalc.statute`.
- `InvestorResult.irr` / `.moic` are `Optional` (None when refused).
  `gross_benefit` / `net_benefit` are computed on net credits retained.
- `credits.schedule()` rows are labelled by allowance date (`t=0` … `t=6`)
  and carry a status.
- The waterfall runs from year 1 to `unwind_year`.

### Tests
- Two tests that pinned defects as correct were replaced:
  `test_avg_dscr_equals_min_when_noi_constant` (pinned the flat DSCR
  schedule) and `test_moic_math` (a tautology).

### Not yet done (Phase B of the audit's §9)
Item 6, DSCR/NOI series. Item 7, closing-date QLICI deployment ratio.
Item 8, the `subsidy` repair: the market-rate proxy is still the fund's
leverage rate, and forgiveness is still implicit. Item 9, the `irr`/`moic`
label decision. Item 10, the sdist gate and packaging hygiene (the version in
`pyproject.toml` is still 0.2.1). Item 11, the guarantee-fee/DSCR convention
claim.

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
