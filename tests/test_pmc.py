from datetime import date
from src.analysis.pmc import calculate_pmc


def test_empty_tss_returns_zeros():
    result = calculate_pmc({}, date(2024, 1, 1), date(2024, 1, 3))
    assert len(result) == 3
    for row in result:
        assert row["ctl"] == 0.0
        assert row["atl"] == 0.0
        assert row["tsb"] == 0.0


def test_single_tss_day():
    """100 TSS an Tag 1 → CTL/ATL steigen, TSB ist Morning Value (0 an Tag 1)."""
    result = calculate_pmc({"2024-01-01": 100.0}, date(2024, 1, 1), date(2024, 1, 2))
    day1 = result[0]
    day2 = result[1]
    assert day1["tsb"] == 0.0  # Morning value: CTL[t-1] - ATL[t-1] = 0 - 0
    assert day1["ctl"] > 0
    assert day1["atl"] > day1["ctl"]  # ATL steigt schneller als CTL
    assert day2["tsb"] < 0  # Nach hohem TSS ist Form negativ


def test_ctl_atl_ema_constants():
    """CTL = 42-Tage EMA, ATL = 7-Tage EMA."""
    daily = {f"2024-01-{i:02d}": 100.0 for i in range(1, 29)}
    result = calculate_pmc(daily, date(2024, 1, 1), date(2024, 1, 28))
    last = result[-1]
    assert last["atl"] > last["ctl"]


def test_date_range_inclusive():
    result = calculate_pmc({}, date(2024, 1, 1), date(2024, 1, 5))
    assert len(result) == 5
    assert result[0]["date"] == "2024-01-01"
    assert result[-1]["date"] == "2024-01-05"


def test_missing_dates_treated_as_zero():
    tss = {"2024-01-01": 100.0, "2024-01-03": 50.0}
    result = calculate_pmc(tss, date(2024, 1, 1), date(2024, 1, 3))
    assert result[1]["tss"] == 0.0


def test_warmup_affects_starting_values():
    warmup = {f"2024-01-{i:02d}": 80.0 for i in range(1, 8)}
    all_tss = {**warmup, "2024-01-08": 0.0}
    result_with_warmup = calculate_pmc(all_tss, date(2024, 1, 1), date(2024, 1, 8))
    result_without = calculate_pmc({"2024-01-08": 0.0}, date(2024, 1, 8), date(2024, 1, 8))
    assert result_with_warmup[-1]["ctl"] > result_without[-1]["ctl"]
