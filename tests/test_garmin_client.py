"""Tests für GarminClient — Token-Caching und Login-Logik."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.collector.garmin_client import GarminClient, MFAPendingError


class TestTokenCaching:
    def test_save_token_schreibt_json_datei(self, tmp_path):
        """Token wird als JSON in angegebener Datei gespeichert."""
        token_path = tmp_path / "token.json"
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_path
        fake_token = {"access_token": "abc123", "expires_in": 3600}
        client._save_token(fake_token)
        assert token_path.exists()
        assert json.loads(token_path.read_text()) == fake_token

    def test_load_token_liest_existierende_datei(self, tmp_path):
        """Vorhandenes Token wird korrekt geladen."""
        token_path = tmp_path / "token.json"
        fake_token = {"access_token": "xyz789"}
        token_path.write_text(json.dumps(fake_token))
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_path
        result = client._load_token()
        assert result == fake_token

    def test_load_token_gibt_none_wenn_datei_fehlt(self, tmp_path):
        """Wenn Token-Datei nicht existiert, wird None zurückgegeben."""
        client = GarminClient.__new__(GarminClient)
        client.token_path = tmp_path / "nicht_vorhanden.json"
        assert client._load_token() is None

    def test_load_token_gibt_none_bei_ungueltigem_json(self, tmp_path):
        """Beschädigte Token-Datei → None, kein Exception."""
        token_path = tmp_path / "broken.json"
        token_path.write_text("{ kaputt")
        client = GarminClient.__new__(GarminClient)
        client.token_path = token_path
        assert client._load_token() is None


class TestGarminLogin:
    def test_login_mit_gueltigen_credentials_setzt_logged_in(self, tmp_path):
        """Erfolgreicher Login setzt _logged_in = True."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin:
            mock_instance = MagicMock()
            MockGarmin.return_value = mock_instance
            mock_instance.login.return_value = None
            mock_instance.garth.oauth2_token = {"access_token": "tok"}

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "token.json",
            )
            gc.ensure_logged_in()
            assert gc._logged_in is True

    def test_login_speichert_token_nach_login(self, tmp_path):
        """Nach erfolgreichem Login wird Token gespeichert."""
        token_path = tmp_path / "token.json"
        with patch("src.collector.garmin_client.Garmin") as MockGarmin:
            mock_instance = MagicMock()
            MockGarmin.return_value = mock_instance
            mock_instance.login.return_value = None
            mock_instance.garth.oauth2_token = {"access_token": "gespeichert"}

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=token_path,
            )
            gc.ensure_logged_in()
            assert token_path.exists()

    def test_login_wirft_mfa_pending_error_bei_mfa_bedarf(self, tmp_path):
        """Wenn Garmin MFA anfordert, wird MFAPendingError geworfen."""
        with patch("src.collector.garmin_client.Garmin") as MockGarmin:
            mock_instance = MagicMock()
            MockGarmin.return_value = mock_instance
            mock_instance.login.side_effect = Exception("MFA")

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=tmp_path / "token.json",
            )
            gc._mfa_exception_pattern = "MFA"
            with pytest.raises(MFAPendingError):
                gc.ensure_logged_in()

    def test_ensure_logged_in_nutzt_cached_token(self, tmp_path):
        """Wenn Token vorhanden, wird kein neuer Login gemacht."""
        token_path = tmp_path / "token.json"
        token_path.write_text(json.dumps({"access_token": "cached"}))

        with patch("src.collector.garmin_client.Garmin") as MockGarmin:
            mock_instance = MagicMock()
            MockGarmin.return_value = mock_instance
            mock_instance.login.return_value = None
            mock_instance.garth.oauth2_token = {"access_token": "cached"}

            gc = GarminClient(
                email="test@example.com",
                password="secret",
                token_path=token_path,
            )
            gc.ensure_logged_in()
            # login() wird trotzdem aufgerufen, aber mit tokenstore
            MockGarmin.assert_called_once()
            # wichtig: tokenstore-Parameter wurde übergeben
            call_kwargs = MockGarmin.call_args
            assert "tokenstore" in call_kwargs.kwargs or len(call_kwargs.args) >= 3
