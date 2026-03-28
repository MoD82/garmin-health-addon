"""Garmin Connect Client — Login, Token-Caching, MFA-Handling."""
import logging
from pathlib import Path
from typing import Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)

# Verzeichnis für garth dump/load (oauth1_token.json + oauth2_token.json)
DEFAULT_TOKEN_PATH = Path("/data/garmin_tokens")


class MFAPendingError(Exception):
    """Wird geworfen wenn Garmin MFA-Code anfordert."""


class GarminClient:
    """Kapselt Garmin Connect Login mit Token-Caching.

    Attributes:
        email: Garmin-Account E-Mail.
        password: Garmin-Account Passwort.
        token_path: Verzeichnis für Token-Cache (garth dump/load).
        _logged_in: True nach erfolgreichem Login.
        _client: garminconnect.Garmin Instanz.
        _mfa_state: client_state von garth.sso.login() bei MFA-Pending.
    """

    def __init__(
        self,
        email: str,
        password: str,
        token_path: Path = DEFAULT_TOKEN_PATH,
    ) -> None:
        self.email = email
        self.password = password
        self.token_path = token_path
        self._logged_in = False
        self._client: Optional[Garmin] = None
        self._mfa_state: Optional[dict] = None

    # ------------------------------------------------------------------
    # Token-Verwaltung
    # ------------------------------------------------------------------

    def _has_token(self) -> bool:
        """Prüft ob Token-Cache-Verzeichnis mit beiden garth-Dateien existiert."""
        return (
            (self.token_path / "oauth1_token.json").exists()
            and (self.token_path / "oauth2_token.json").exists()
        )

    def _save_token(self, garth_client) -> None:
        """Speichert Tokens via garth.dump() in token_path-Verzeichnis."""
        garth_client.dump(str(self.token_path))
        logger.debug("Garmin Token gespeichert: %s", self.token_path)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def ensure_logged_in(self) -> None:
        """Stellt sicher dass ein aktiver Garmin-Login besteht.

        Versucht zuerst Token aus Cache zu laden. Bei MFA-Anforderung
        wird MFAPendingError geworfen — der Web-UI-Flow übernimmt dann.

        Raises:
            MFAPendingError: Garmin fordert MFA-Code an.
            RuntimeError: Login schlägt aus anderen Gründen fehl.
        """
        try:
            self._client = Garmin(email=self.email, password=self.password)

            if self._has_token():
                logger.info("Versuche Login mit gecachtem Token")
                self._client.login(tokenstore=str(self.token_path))
            else:
                logger.info("Kein Token-Cache — Neu-Login mit Credentials")
                from garth import sso as _sso

                result = _sso.login(
                    self.email,
                    self.password,
                    client=self._client.garth,
                    return_on_mfa=True,
                )
                if result[0] == "needs_mfa":
                    self._mfa_state = result[1]
                    logger.warning("Garmin fordert MFA — Web-UI-Eingabe nötig")
                    raise MFAPendingError("MFA-Code erforderlich")

                # Tokens in garth-Client setzen
                self._client.garth.oauth1_token, self._client.garth.oauth2_token = result
                # Profile laden (entspricht garminconnect.Garmin.login())
                self._client.display_name = self._client.garth.profile["displayName"]
                self._client.full_name = self._client.garth.profile["fullName"]
                settings = self._client.garth.connectapi(
                    self._client.garmin_connect_user_settings_url
                )
                self._client.unit_system = settings["userData"]["measurementSystem"]

            self._logged_in = True
            # Token nach erfolgreichem Login speichern/aktualisieren
            self._save_token(self._client.garth)
            logger.info("Garmin Login erfolgreich")

        except MFAPendingError:
            raise
        except Exception as exc:
            logger.error("Garmin Login fehlgeschlagen: %s", exc)
            raise RuntimeError(f"Garmin Login Fehler: {exc}") from exc

    def submit_mfa(self, mfa_code: str) -> None:
        """Übermittelt MFA-Code nach MFAPendingError.

        Args:
            mfa_code: 6-stelliger TOTP-Code.

        Raises:
            RuntimeError: MFA-Übermittlung fehlgeschlagen.
        """
        if self._client is None or self._mfa_state is None:
            raise RuntimeError("submit_mfa() ohne MFA-Pending-State aufgerufen")
        try:
            from garth import sso as _sso

            oauth1, oauth2 = _sso.resume_login(self._mfa_state, mfa_code)
            self._client.garth.oauth1_token = oauth1
            self._client.garth.oauth2_token = oauth2
            # Profile laden
            self._client.display_name = self._client.garth.profile["displayName"]
            self._client.full_name = self._client.garth.profile["fullName"]
            settings = self._client.garth.connectapi(
                self._client.garmin_connect_user_settings_url
            )
            self._client.unit_system = settings["userData"]["measurementSystem"]
            self._logged_in = True
            self._mfa_state = None
            self._save_token(self._client.garth)
            logger.info("MFA erfolgreich — Garmin Login abgeschlossen")
        except Exception as exc:
            logger.error("MFA-Fehler: %s", exc)
            raise RuntimeError(f"MFA fehlgeschlagen: {exc}") from exc

    @property
    def api(self) -> Garmin:
        """Gibt die Garmin-API-Instanz zurück.

        Raises:
            RuntimeError: Falls nicht eingeloggt.
        """
        if not self._logged_in or self._client is None:
            raise RuntimeError("Nicht eingeloggt — ensure_logged_in() zuerst aufrufen")
        return self._client

    def test_connection(self) -> dict:
        """Ruft ensure_logged_in() auf und gibt strukturiertes Ergebnis zurück.

        Returns:
            dict mit Feldern:
              - success: bool
              - error_type: "rate_limited"|"invalid_credentials"|"mfa_required"|"network"|"unknown"|None
              - message: str (für Anzeige im UI)
        """
        try:
            self.ensure_logged_in()
            return {
                "success": True,
                "error_type": None,
                "message": "✅ Erfolgreich verbunden — Token gespeichert",
            }
        except MFAPendingError:
            return {
                "success": False,
                "error_type": "mfa_required",
                "message": "MFA erforderlich — nutze die MFA-Eingabe auf der Manuell-Seite",
            }
        except RuntimeError as exc:
            msg = str(exc)
            if "429" in msg:
                return {
                    "success": False,
                    "error_type": "rate_limited",
                    "message": "Garmin blockiert zu viele Anfragen — bitte 2 Stunden warten",
                }
            if "401" in msg or "credentials" in msg or "password" in msg:
                return {
                    "success": False,
                    "error_type": "invalid_credentials",
                    "message": "Falscher Benutzername oder Passwort",
                }
            if "ConnectionError" in msg or "Network" in msg or "timeout" in msg or "Timeout" in msg:
                return {
                    "success": False,
                    "error_type": "network",
                    "message": "Keine Verbindung zu Garmin — Internet prüfen",
                }
            return {
                "success": False,
                "error_type": "unknown",
                "message": f"Verbindungsfehler: {msg}",
            }
