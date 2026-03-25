"""Garmin Connect Client — Login, Token-Caching, MFA-Handling."""
import json
import logging
from pathlib import Path
from typing import Optional

from garminconnect import Garmin

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_PATH = Path("/data/garmin_token.json")


class MFAPendingError(Exception):
    """Wird geworfen wenn Garmin MFA-Code anfordert."""


class GarminClient:
    """Kapselt Garmin Connect Login mit Token-Caching.

    Attributes:
        email: Garmin-Account E-Mail.
        password: Garmin-Account Passwort.
        token_path: Pfad zur Token-Cache-Datei.
        _logged_in: True nach erfolgreichem Login.
        _client: garminconnect.Garmin Instanz.
    """

    _mfa_exception_pattern = "MFA"  # Suchstring in Exception-Message

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

    # ------------------------------------------------------------------
    # Token-Verwaltung
    # ------------------------------------------------------------------

    def _save_token(self, token: dict) -> None:
        """Speichert OAuth2-Token als JSON-Datei."""
        self.token_path.write_text(json.dumps(token))
        logger.debug("Garmin Token gespeichert: %s", self.token_path)

    def _load_token(self) -> Optional[dict]:
        """Lädt Token aus Cache-Datei. Gibt None bei Fehler zurück."""
        if not self.token_path.exists():
            return None
        try:
            return json.loads(self.token_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Token-Datei ungültig, ignoriert: %s", exc)
            return None

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
        cached = self._load_token()
        token_path_str = str(self.token_path) if cached else None

        try:
            if token_path_str:
                logger.info("Versuche Login mit gecachtem Token")
                self._client = Garmin(
                    email=self.email,
                    password=self.password,
                    tokenstore=token_path_str,
                )
            else:
                logger.info("Kein Token-Cache — Neu-Login mit Credentials")
                self._client = Garmin(
                    email=self.email,
                    password=self.password,
                )

            self._client.login()
            self._logged_in = True

            # Token nach erfolgreichem Login speichern/aktualisieren
            try:
                token = self._client.garth.oauth2_token
                if token:
                    self._save_token(dict(token))
            except AttributeError:
                logger.debug("Token-Zugriff nicht möglich, wird übersprungen")

            logger.info("Garmin Login erfolgreich")

        except Exception as exc:
            if self._mfa_exception_pattern in str(exc):
                logger.warning("Garmin fordert MFA — Web-UI-Eingabe nötig")
                raise MFAPendingError("MFA-Code erforderlich") from exc
            logger.error("Garmin Login fehlgeschlagen: %s", exc)
            raise RuntimeError(f"Garmin Login Fehler: {exc}") from exc

    def submit_mfa(self, mfa_code: str) -> None:
        """Übermittelt MFA-Code nach MFAPendingError.

        Args:
            mfa_code: 6-stelliger TOTP-Code.

        Raises:
            RuntimeError: MFA-Übermittlung fehlgeschlagen.
        """
        if self._client is None:
            raise RuntimeError("submit_mfa() ohne vorherigen ensure_logged_in() aufgerufen")
        try:
            self._client.login(mfa_code)
            self._logged_in = True
            try:
                token = self._client.garth.oauth2_token
                if token:
                    self._save_token(dict(token))
            except AttributeError:
                pass
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
