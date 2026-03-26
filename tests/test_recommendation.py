from src.analysis.recommendation import get_recommendation, _recovery_score


# --- Recovery Score Tests ---

def test_recovery_score_uses_readiness():
    assert _recovery_score(80, None, None) == 80

def test_recovery_score_uses_body_battery_fallback():
    assert _recovery_score(None, 75, None) == 75

def test_recovery_score_default_when_both_none():
    assert _recovery_score(None, None, None) == 60

def test_recovery_score_hrv_poor_penalty():
    assert _recovery_score(80, None, "POOR") == 60

def test_recovery_score_hrv_unbalanced_penalty():
    assert _recovery_score(80, None, "UNBALANCED") == 70

def test_recovery_score_hrv_balanced_no_penalty():
    assert _recovery_score(80, None, "BALANCED") == 80

def test_recovery_score_clamped_to_zero():
    assert _recovery_score(10, None, "POOR") == 0

def test_recovery_score_clamped_to_100():
    assert _recovery_score(100, None, None) == 100


# --- Empfehlungs-Tests (8 Stufen) ---

def test_stufe1_pause_bei_sehr_niedrigem_recovery():
    r = get_recommendation(tsb=5.0, readiness=20, body_battery=None, hrv_status=None)
    assert r["color"] == "#e74c3c"
    assert "Pause" in r["title"]

def test_stufe2_aktive_regeneration_tsb_sehr_negativ():
    r = get_recommendation(tsb=-25.0, readiness=70, body_battery=None, hrv_status=None)
    assert r["color"] == "#e67e22"
    assert "Regeneration" in r["title"]

def test_stufe2_aktive_regeneration_recovery_niedrig():
    r = get_recommendation(tsb=0.0, readiness=45, body_battery=None, hrv_status=None)
    assert r["color"] == "#e67e22"

def test_stufe3_grundlage_tsb_negativ():
    r = get_recommendation(tsb=-10.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] == "#f39c12"
    assert "Grundlage" in r["title"]

def test_stufe4_kraft_z2_ausgeglichen():
    r = get_recommendation(tsb=2.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] == "#27ae60"

def test_stufe5_grundlage_tsb_positiv_recovery_mittel():
    r = get_recommendation(tsb=8.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] == "#f39c12"

def test_stufe6_schwelle_tsb_positiv_recovery_gut():
    r = get_recommendation(tsb=12.0, readiness=75, body_battery=None, hrv_status=None)
    assert r["color"] == "#2980b9"
    assert "Schwelle" in r["title"]

def test_stufe7_vo2max_tsb_sehr_positiv_recovery_gut():
    r = get_recommendation(tsb=25.0, readiness=80, body_battery=None, hrv_status=None)
    assert r["color"] == "#8e44ad"
    assert "VO2max" in r["title"]

def test_stufe8_wettkampf_tsb_sehr_positiv_recovery_sehr_gut():
    r = get_recommendation(tsb=25.0, readiness=90, body_battery=None, hrv_status=None)
    assert r["color"] == "#c0392b"
    assert "Wettkampf" in r["title"]

def test_result_has_required_fields():
    r = get_recommendation(tsb=0.0, readiness=70, body_battery=None, hrv_status=None)
    assert "emoji" in r
    assert "title" in r
    assert "reason" in r
    assert "color" in r
    assert "recovery_score" in r


# --- Boundary Value Tests ---

def test_boundary_rec_34_ist_pause():
    """rec=34 → Pause (< 35)"""
    r = get_recommendation(tsb=5.0, readiness=34, body_battery=None, hrv_status=None)
    assert "Pause" in r["title"]

def test_boundary_rec_35_ist_nicht_pause():
    """rec=35 → nicht Pause (>= 35)"""
    r = get_recommendation(tsb=5.0, readiness=35, body_battery=None, hrv_status=None)
    assert "Pause" not in r["title"]

def test_boundary_tsb_minus21_ist_regeneration():
    """tsb=-21 → Aktive Regeneration (< -20)"""
    r = get_recommendation(tsb=-21.0, readiness=70, body_battery=None, hrv_status=None)
    assert "Regeneration" in r["title"]

def test_boundary_tsb_minus20_ist_nicht_regeneration_wegen_tsb():
    """tsb=-20 und rec>=50 → Grundlage (tsb=-20 ist NICHT < -20)"""
    r = get_recommendation(tsb=-20.0, readiness=70, body_battery=None, hrv_status=None)
    assert r["color"] == "#f39c12"  # Grundlage Z2

def test_boundary_tsb_minus5_ist_kraft_z2():
    """tsb=-5 → Kraft oder Z2 (NOT < -5, also Stufe 4)"""
    r = get_recommendation(tsb=-5.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] == "#27ae60"  # Kraft oder Z2

def test_boundary_tsb_5_ist_kraft_z2():
    """tsb=5 → Kraft oder Z2 (<= 5)"""
    r = get_recommendation(tsb=5.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] == "#27ae60"

def test_boundary_tsb_6_verlässt_kraft_z2():
    """tsb=6 → nicht mehr Kraft oder Z2 (> 5)"""
    r = get_recommendation(tsb=6.0, readiness=65, body_battery=None, hrv_status=None)
    assert r["color"] != "#27ae60"

def test_boundary_tsb_20_ist_schwelle():
    """tsb=20, rec>=70 → Schwellentraining (<= 20)"""
    r = get_recommendation(tsb=20.0, readiness=75, body_battery=None, hrv_status=None)
    assert "Schwelle" in r["title"]

def test_boundary_tsb_21_ist_vo2max():
    """tsb=21, rec<85 → VO2max (> 20)"""
    r = get_recommendation(tsb=21.0, readiness=80, body_battery=None, hrv_status=None)
    assert "VO2max" in r["title"]
