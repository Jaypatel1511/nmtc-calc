import pytest
from nmtccalc.data.schema import NMTCDeal


@pytest.fixture
def sample_deal():
    return NMTCDeal(
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
        investor_name="US Bancorp CDC",
        cde_name="Chicago Development Fund",
        project_location="Chicago, IL",
    )
