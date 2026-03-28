"""Tests für GarminClient — Token-Caching und Login-Logik."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.collector.garmin_client import GarminClient, MFAPendingError


def _make_token_dir(tmp_path: Path) -> Path:
    """Erstellt ein Token-Verzeichnis mit beiden garth-Dateien."""
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    (token_dir / "oauth1_token.json").write_text('{"oauth_token": "x"}')
    (token_dir / "oauth2_token.json").write_text('{"access_token": "y"}')
    return token_dir


class TestTokenCaching:
    def test_save_token_ruft_garth_dump_auf(self, tmp_path):
        """_save_token() delegiert an garth_client.dump()."""
        token_dir = tmp_path / "tokens"
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_dir
        garth_mock = MagicMock()
        client._save_token(garth_mock)
        garth_mock.dump.assert_called_once_with(str(token_dir))

    def test_has_token_true_wenn_beide_dateien_vorhanden(self, tmp_path):
        """_has_token() gibt True wenn oauth1 und oauth2 existieren."""
        token_dir = _make_token_dir(tmp_path)
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_dir
        assert client._has_token() is True

    def test_has_token_false_wenn_verzeichnis_fehlt(self, tmp_path):
        """_has_token() gibt False wenn Token-Verzeichnis fehlt."""
        client = GarminClient.__new__(GarminClient)
        client.token_path = tmp_path / "nicht_vorhanden"
        assert client._has_token() is False

    def test_has_token_false_wenn_nur_eine_datei_vorhanden(self, tmp_path):
        """_has_token() gibt False wenn nur eine der beiden Token-Dateien fehlt."""
        token_dir = tmp_path / "tokens"
        token_dir.mkdir()
        (token_dir / "oauth1_token.json").write_text("{}")
        # oauth2_token.json fehlt
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_dir
        assert client._has_token() is False


class TestGarminLogin:
    def test_login_ohne_token_nutzt_garth_sso(self, tmp_path):
        """Frischer Login ruft garth.sso.login() auf (kein Token vorhanden)."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            mock_client = MagicMock()
            MockGarmin.return_value = mock_client
            mock_sso_login.return_value = (MagicMock(), MagicMock())

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",  # existiert nicht → kein Token
            )
            gc.ensure_logged_in()

            assert gc._logged_in is True
            mock_sso_login.assert_called_once()

    def test_login_mit_token_nutzt_tokenstore(self, tmp_path):
        """Login mit gecachtem Token ruft Garmin().login(tokenstore=...) auf."""
        token_dir = _make_token_dir(tmp_path)

        with patch("src.collector.garmin_client.Garmin") as MockGarmin:
            mock_client = MagicMock()
            MockGarmin.return_value = mock_client

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=token_dir,
            )
            gc.ensure_logged_in()

            assert gc._logged_in is True
            mock_client.login.assert_called_once_with(tokenstore=str(token_dir))

    def test_login_speichert_token_nach_login(self, tmp_path):
        """Nach erfolgreichem Login wird garth.dump() aufgerufen."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            mock_client = MagicMock()
            MockGarmin.return_value = mock_client
            mock_sso_login.return_value = (MagicMock(), MagicMock())

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            gc.ensure_logged_in()

            mock_client.garth.dump.assert_called_once_with(str(tmp_path / "tokens"))

    def test_login_wirft_mfa_pending_error_bei_mfa_bedarf(self, tmp_path):
        """Wenn garth.sso.login() 'needs_mfa' zurückgibt, wird MFAPendingError geworfen."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.return_value = ("needs_mfa", {"client": MagicMock(), "login_params": {}})

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            with pytest.raises(MFAPendingError):
                gc.ensure_logged_in()

    def test_login_mfa_speichert_mfa_state(self, tmp_path):
        """Bei MFA wird _mfa_state für späteres submit_mfa() gespeichert."""
        mfa_state = {"client": MagicMock(), "login_params": {"x": 1}}
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.return_value = ("needs_mfa", mfa_state)

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            with pytest.raises(MFAPendingError):
                gc.ensure_logged_in()

            assert gc._mfa_state == mfa_state


class TestTestConnection:
    def test_erfolg_gibt_success_true_zurueck(self, tmp_path):
        """Erfolgreicher Login → success=True, error_type=None."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.return_value = (MagicMock(), MagicMock())

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is True
        assert result["error_type"] is None
        assert "Erfolgreich" in result["message"]

    def test_mfa_gibt_mfa_required_zurueck(self, tmp_path):
        """garth.sso.login() gibt 'needs_mfa' → test_connection() gibt error_type='mfa_required'."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.return_value = ("needs_mfa", {"client": MagicMock(), "login_params": {}})

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is False
        assert result["error_type"] == "mfa_required"
        assert "MFA" in result["message"]

    def test_429_gibt_rate_limited_zurueck(self, tmp_path):
        """Exception mit '429' → error_type='rate_limited'."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.side_effect = Exception("429 Too Many Requests")

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is False
        assert result["error_type"] == "rate_limited"

    def test_401_gibt_invalid_credentials_zurueck(self, tmp_path):
        """Exception mit '401' → error_type='invalid_credentials'."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.side_effect = Exception("401 Unauthorized")

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is False
        assert result["error_type"] == "invalid_credentials"

    def test_netzwerkfehler_gibt_network_zurueck(self, tmp_path):
        """Exception mit 'ConnectionError' → error_type='network'."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.side_effect = Exception("ConnectionError: timeout")

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is False
        assert result["error_type"] == "network"

    def test_unbekannter_fehler_gibt_unknown_zurueck(self, tmp_path):
        """Exception ohne bekanntes Muster → error_type='unknown'."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin, \
             patch("garth.sso.login") as mock_sso_login:
            MockGarmin.return_value = MagicMock()
            mock_sso_login.side_effect = Exception("Irgendwas schiefgelaufen")

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "tokens",
            )
            result = gc.test_connection()

        assert result["success"] is False
        assert result["error_type"] == "unknown"
        assert "Verbindungsfehler" in result["message"]
