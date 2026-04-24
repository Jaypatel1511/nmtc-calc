# nmtc-calc 🏗️

**Python calculator for New Markets Tax Credit (NMTC) leveraged transactions.**

Built for CDFI practitioners, CDEs, tax credit investors, and project sponsors who need
reproducible, auditable NMTC deal math — without starting from scratch in Excel.

---

## Why nmtc-calc?

New Markets Tax Credit transactions involve complex layered capital structures — QEIs,
QLICIs, leverage loans, 7-year credit schedules, investor IRR, and net subsidy calculations.
Every practitioner builds these models from scratch in Excel. `nmtc-calc` standardizes
and automates the math.

---

## Installation

```bash
cat > README.md << 'EOF'
# nmtc-calc 🏗️

**Python calculator for New Markets Tax Credit (NMTC) leveraged transactions.**

Built for CDFI practitioners, CDEs, tax credit investors, and project sponsors who need
reproducible, auditable NMTC deal math — without starting from scratch in Excel.

---

## Why nmtc-calc?

New Markets Tax Credit transactions involve complex layered capital structures — QEIs,
QLICIs, leverage loans, 7-year credit schedules, investor IRR, and net subsidy calculations.
Every practitioner builds these models from scratch in Excel. `nmtc-calc` standardizes
and automates the math.

---

## Installation

```bash
pip install nmtc-calc
```

---

## Quickstart

```python
from nmtccalc import NMTCDeal, transaction, credits, investor, subsidy

deal = NMTCDeal(
    project_name="Southside Community Health Center",
    total_project_cost=10_000_000,
    nmtc_allocation=10_000_000,
    credit_price=0.83,
    leverage_loan_rate=0.045,
    qlici_a_loan_rate=0.045,
    qlici_b_loan_rate=0.010,
    cde_fee_rate=0.02,
    compliance_years=7,
    discount_rate=0.08,
)

# Full capital stack
transaction.structure(deal).summary()

# 7-year credit schedule
credits.schedule(deal).summary()

# Investor economics & IRR
investor.analyze(deal).summary()

# Net subsidy to project
subsidy.analyze(deal).summary()
```

---

## Modules

| Module | What It Computes |
|--------|-----------------|
| `transaction` | QEI, NMTCs, investor equity, leverage loan, QLICI A/B split |
| `credits` | 7-year credit schedule (5%/5%/5%/6%/6%/6%/6%), PV of credits |
| `investor` | Investor IRR, MOIC, gross/net benefit |
| `subsidy` | Net subsidy to QALICB, effective cost of capital, interest savings |

---

## Key NMTC Concepts

| Term | Definition |
|------|-----------|
| QEI | Qualified Equity Investment — the total investment made into the CDE |
| QLICI | Qualified Low-Income Community Investment — loans from CDE to QALICB |
| QALICB | Qualified Active Low-Income Community Business — the project borrower |
| CDE | Community Development Entity — allocatee of NMTC authority |
| A Loan | Senior QLICI mirroring the leverage loan |
| B Loan | Subordinate QLICI mirroring investor equity, typically forgiven at year 7 |
| Credit Price | $ per $1 of NMTC benefit paid by investor (typically $0.70–$0.85) |

---

## Running Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

32 tests across all modules.

---

## Who This Is For

- **CDEs** structuring NMTC allocations for projects
- **Tax credit investors** evaluating deal economics
- **Project sponsors** understanding subsidy and cost of capital
- **CDFI analysts** modeling NMTC transactions in IC memos

---

## License

MIT © 2026 Jaypatel1511
