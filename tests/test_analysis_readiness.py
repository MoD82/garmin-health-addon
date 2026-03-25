import pytest
from src.analysis.readiness import calculate_readiness, readiness_label
from src.storage.models import DailyData


def make_daily(sleep=80, bb=70, hrv="balanced", stress=600) -> DailyData:
    return DailyData(
        date="2026-03-25",
        sleep_score=sleep,
        body_battery=bb,
        hrv_status=hrv,
        stress_total=stress,
    )


def test_perfect_score():
    data = make_daily(sleep=100, bb=100, hrv="balanced", stress=0)
    score = calculate_readiness(data)
    assert score == 100


def test_zero_score_all_bad():
    data = make_daily(sleep=0, bb=0, hrv="high", stress=1500)
    score = calculate_readiness(data)
    assert score == 0


def test_typical_good_day():
    data = make_daily(sleep=80, bb=70, hrv="balanced", stress=620)
    score = calculate_readiness(data)
    assert 65 <= score <= 85


def test_hrv_not_balanced_reduces_score():
    balanced = calculate_readiness(make_daily(hrv="balanced"))
    unbalanced = calculate_readiness(make_daily(hrv="high"))
    assert balanced > unbalanced


def test_none_values_handled():
    data = DailyData(date="2026-03-25")
    score = calculate_readiness(data)
    assert score == 0


def test_stress_capped_at_1500():
    data1 = make_daily(sleep=0, bb=0, hrv="high", stress=1500)
    data2 = make_daily(sleep=0, bb=0, hrv="high", stress=9999)
    assert calculate_readiness(data1) == calculate_readiness(data2)


def test_score_clamped_0_100():
    data = make_daily(sleep=100, bb=100, hrv="balanced", stress=0)
    assert 0 <= calculate_readiness(data) <= 100


def test_label_gruen():
    assert readiness_label(75) == "GUT"
    assert readiness_label(100) == "GUT"


def test_label_gelb():
    assert readiness_label(50) == "MODERAT"
    assert readiness_label(74) == "MODERAT"


def test_label_rot():
    assert readiness_label(0) == "ERHOLUNG"
    assert readiness_label(49) == "ERHOLUNG"
