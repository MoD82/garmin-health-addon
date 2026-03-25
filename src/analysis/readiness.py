from ..storage.models import DailyData


def calculate_readiness(data: DailyData) -> int:
    """
    Training Readiness Score 0–100.

    Score = sleep_score * 0.30 + body_battery * 0.25 + hrv_balanced * 25 + stress_inverted * 0.20
    """
    if (
        data.sleep_score is None
        and data.body_battery is None
        and data.hrv_status is None
        and data.stress_total is None
    ):
        return 0

    sleep = (data.sleep_score or 0) / 100.0 * 30.0
    bb = (data.body_battery or 0) / 100.0 * 25.0
    hrv_ok = 25.0 if (data.hrv_status or "").lower() == "balanced" else 0.0
    stress_raw = min(data.stress_total or 0, 1500)
    stress_score = (1.0 - stress_raw / 1500.0) * 20.0
    total = sleep + bb + hrv_ok + stress_score
    return max(0, min(100, round(total)))


def readiness_label(score: int) -> str:
    if score >= 75:
        return "GUT"
    elif score >= 50:
        return "MODERAT"
    return "ERHOLUNG"
