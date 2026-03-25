"""Tests für HealthCollector — Mapping Garmin API → DailyData."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from src.collector.garmin_health import HealthCollector, map_stats_to_daily_data
from src.storage.models import DailyData

# ---------------------------------------------------------------------------
# Fixtures: Realistische Garmin-API Mock-Antworten
# ---------------------------------------------------------------------------

MOCK_STATS = {
    "bodyBatteryChargedValue": 85,
    "bodyBatteryDrainedValue": 42,
    "averageStressLevel": 28,
    "highStressDuration": 1200,    # Sekunden → Prozent berechnen
    "totalStressDuration": 6000,
    "vo2MaxValue": 52.3,
    "averageSpO2": 97,
    "lowestSpO2": 94,
    "averageRespirationValue": 14.2,
}

MOCK_SLEEP = {
    "dailySleepDTO": {
        "sleepScores": {
            "overall": {"value": 78}
        }
    }
}

MOCK_HRV = {
    "hrvSummary": {"status": "BALANCED"}
}

MOCK_BODY_COMP = {
    "weight": 75400,
    "bodyFat": 18.5,
    "muscleMass": 58200,
}


class TestMapStatsToDailyData:
    def test_body_battery_wird_korrekt_gemappt(self):
        """bodyBatteryChargedValue und Drained werden übernommen."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep={},
            hrv={},
            body_comp={},
        )
        assert result.body_battery_charged == 85
        assert result.body_battery_drained == 42

    def test_stress_wird_gemappt(self):
        """averageStressLevel → stress_total."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep={},
            hrv={},
            body_comp={},
        )
        assert result.stress_total == 28

    def test_stress_high_wird_als_prozent_berechnet(self):
        """highStressDuration / totalStressDuration * 100 → stress_high."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep={},
            hrv={},
            body_comp={},
        )
        # 1200 / 6000 * 100 = 20
        assert result.stress_high == 20

    def test_sleep_score_aus_nested_dict(self):
        """dailySleepDTO.sleepScores.overall.value → sleep_score."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep=MOCK_SLEEP,
            hrv={},
            body_comp={},
        )
        assert result.sleep_score == 78

    def test_hrv_status_wird_gemappt(self):
        """hrvSummary.status → hrv_status."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep={},
            hrv=MOCK_HRV,
            body_comp={},
        )
        assert result.hrv_status == "BALANCED"

    def test_gewicht_wird_von_gramm_in_kg_konvertiert(self):
        """weight in Gramm → kg (Division durch 1000)."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep={},
            hrv={},
            body_comp=MOCK_BODY_COMP,
        )
        assert result.weight == pytest.approx(75.4, abs=0.01)

    def test_muskelmasse_wird_von_gramm_in_kg_konvertiert(self):
        """muscleMass in Gramm → kg."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep={},
            hrv={},
            body_comp=MOCK_BODY_COMP,
        )
        assert result.muscle_mass == pytest.approx(58.2, abs=0.01)

    def test_body_fat_wird_direkt_uebernommen(self):
        """bodyFat ist bereits in Prozent."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep={},
            hrv={},
            body_comp=MOCK_BODY_COMP,
        )
        assert result.body_fat == 18.5

    def test_fehlende_felder_sind_none(self):
        """Wenn Garmin-Felder fehlen → None, kein KeyError."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats={},
            sleep={},
            hrv={},
            body_comp={},
        )
        assert result.body_battery_charged is None
        assert result.sleep_score is None
        assert result.hrv_status is None
        assert result.weight is None

    def test_gibt_daily_data_modell_zurueck(self):
        """Rückgabewert ist DailyData-Instanz mit korrektem Datum."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep=MOCK_SLEEP,
            hrv=MOCK_HRV,
            body_comp=MOCK_BODY_COMP,
        )
        assert isinstance(result, DailyData)
        assert result.date == date(2026, 3, 25)

    def test_vo2max_wird_gemappt(self):
        """vo2MaxValue → vo2max."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep={},
            hrv={},
            body_comp={},
        )
        assert result.vo2max == pytest.approx(52.3)

    def test_spo2_werte_werden_gemappt(self):
        """averageSpO2 → spo2, lowestSpO2 → spo2_lowest."""
        result = map_stats_to_daily_data(
            date_str="2026-03-25",
            stats=MOCK_STATS,
            sleep={},
            hrv={},
            body_comp={},
        )
        assert result.spo2 == 97
        assert result.spo2_lowest == 94


class TestHealthCollectorGracefulDegradation:
    @pytest.mark.asyncio
    async def test_collect_gibt_none_zurueck_bei_api_fehler(self, tmp_path):
        """Wenn Garmin API nicht erreichbar → None zurück, kein Crash."""
        mock_client = MagicMock()
        mock_client.api.get_stats.side_effect = Exception("Verbindung fehlgeschlagen")
        mock_client.api.get_sleep_data.side_effect = Exception("Verbindung fehlgeschlagen")
        mock_client.api.get_hrv_data.side_effect = Exception("Verbindung fehlgeschlagen")
        mock_client.api.get_body_composition.side_effect = Exception("Verbindung fehlgeschlagen")

        db_path = tmp_path / "test.db"
        with patch("src.collector.garmin_health.DB_PATH", db_path):
            import aiosqlite
            from src.storage.database import _CREATE_TABLES
            async with aiosqlite.connect(db_path) as db:
                await db.executescript(_CREATE_TABLES)
                await db.commit()

            collector = HealthCollector()
            result = await collector.collect(mock_client, "2026-03-25")
            assert result is None  # Graceful Degradation
