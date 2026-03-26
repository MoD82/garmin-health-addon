"""Tests für ActivityCollector — Mapping Garmin API → Activity."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from src.collector.garmin_activities import ActivityCollector, map_activity, ACTIVITY_TYPE_MAP
from src.storage.models import Activity


MOCK_ACTIVITY = {
    "activityId": 12345678,
    "activityName": "Morgenrunde",
    "activityType": {"typeKey": "road_biking"},
    "startTimeLocal": "2026-03-25 07:30:00",
    "distance": 45200.0,
    "duration": 5640.0,
    "elevationGain": 380,
    "averageHR": 142,
    "maxHR": 178,
    "avgPower": 195,
    "maxPower": 420,
    "normPower": 212,
    "trainingStressScore": 68.4,
    "intensityFactor": 0.78,
    "aerobicTrainingEffect": 3.2,
    "anaerobicTrainingEffect": 1.1,
    "activityTrainingLoad": 95,
}


class TestActivityTypeMapping:
    def test_road_biking_wird_zu_cycling(self):
        assert ACTIVITY_TYPE_MAP.get("road_biking") == "cycling"

    def test_running_bleibt_running(self):
        assert ACTIVITY_TYPE_MAP.get("running") == "running"

    def test_unbekannter_typ_ist_other(self):
        result = ACTIVITY_TYPE_MAP.get("yoga", "other")
        assert result == "other"

    def test_schwimmen_wird_zu_swimming(self):
        assert ACTIVITY_TYPE_MAP.get("swimming") == "swimming"

    def test_hiking_bleibt_hiking(self):
        assert ACTIVITY_TYPE_MAP.get("hiking") == "hiking"


class TestMapActivity:
    def test_distance_wird_von_meter_in_km_konvertiert(self):
        """45200 Meter → 45.2 km."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.distance_km == pytest.approx(45.2, abs=0.01)

    def test_duration_wird_von_sekunden_in_minuten_konvertiert(self):
        """5640 Sekunden → 94 Minuten."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.duration_min == 94

    def test_activity_type_wird_normiert(self):
        """road_biking → cycling."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.activity_type == "cycling"

    def test_datum_wird_aus_starttime_extrahiert(self):
        """startTimeLocal → date Objekt."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.date == date(2026, 3, 25)

    def test_herzfrequenz_wird_gemappt(self):
        """averageHR → avg_hr, maxHR → max_hr."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.avg_hr == 142
        assert result.max_hr == 178

    def test_power_metriken_werden_gemappt(self):
        """avgPower, maxPower, normPower werden übernommen."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.avg_power == 195
        assert result.max_power == 420
        assert result.norm_power == 212

    def test_tss_und_if_werden_gemappt(self):
        """trainingStressScore → tss, intensityFactor → intensity_factor."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.tss == pytest.approx(68.4)
        assert result.intensity_factor == pytest.approx(0.78)

    def test_training_effects_werden_gemappt(self):
        """aerobicTrainingEffect → aero_te, anaerobicTrainingEffect → anaero_te."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.aero_te == pytest.approx(3.2)
        assert result.anaero_te == pytest.approx(1.1)

    def test_unbekannter_activity_type_wird_zu_other(self):
        """typeKey nicht in ACTIVITY_TYPE_MAP → 'other'."""
        act = {**MOCK_ACTIVITY, "activityType": {"typeKey": "yoga"}}
        result = map_activity(act)
        assert result.activity_type == "other"

    def test_fehlende_power_felder_sind_none(self):
        """Wenn keine Power-Daten → None, kein Fehler."""
        act = {k: v for k, v in MOCK_ACTIVITY.items()
               if k not in ("avgPower", "maxPower", "normPower")}
        result = map_activity(act)
        assert result.avg_power is None
        assert result.max_power is None

    def test_gibt_activity_model_zurueck(self):
        """Rückgabe ist Activity-Pydantic-Instanz."""
        result = map_activity(MOCK_ACTIVITY)
        assert isinstance(result, Activity)

    def test_name_aus_activityName(self):
        """activityName → name."""
        result = map_activity(MOCK_ACTIVITY)
        assert result.name == "Morgenrunde"
