#!/usr/bin/env python3
"""
Garmin Token Helper — einmalig auf dem PC ausführen.

Öffnet einen Browser, du loggst dich bei Garmin Connect ein
(inkl. MFA), und die OAuth-Tokens werden als garmin_tokens.json
gespeichert. Diese Datei dann im Addon unter "Token-Import" einfügen.

Installation:
    pip install playwright
    playwright install chromium

Ausführen:
    python garmin_token_helper.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path


def check_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Playwright nicht installiert. Bitte ausführen:")
        print()
        print("    pip install playwright")
        print("    playwright install chromium")
        print()
        sys.exit(1)


def normalize_oauth1(raw: dict) -> dict:
    return {
        "oauth_token": raw.get("oauth_token", ""),
        "oauth_token_secret": raw.get("oauth_token_secret", ""),
        "mfa_token": raw.get("mfa_token"),
        "mfa_expiration_timestamp": raw.get("mfa_expiration_timestamp"),
        "domain": raw.get("domain", "garmin.com"),
    }


def normalize_oauth2(raw: dict) -> dict:
    result = dict(raw)
    if "expires_at" not in result and "expires_in" in result:
        result["expires_at"] = time.time() + float(result["expires_in"])
    return result


async def main():
    check_playwright()
    from playwright.async_api import async_playwright

    oauth1_data: dict | None = None
    oauth2_data: dict | None = None

    print("=" * 55)
    print("  Garmin Token Helper")
    print("=" * 55)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        async def on_response(response):
            nonlocal oauth1_data, oauth2_data
            url = response.url
            try:
                if "oauth-service/oauth/preauthorized" in url and response.status == 200:
                    raw = await response.json()
                    if "oauth_token" in raw:
                        oauth1_data = normalize_oauth1(raw)
                        print("✓ OAuth1 Token erhalten")
                elif "oauth-service/oauth/exchange" in url and response.status == 200:
                    raw = await response.json()
                    if "access_token" in raw:
                        oauth2_data = normalize_oauth2(raw)
                        print("✓ OAuth2 Token erhalten")
            except Exception:
                pass

        context.on("response", on_response)
        page = await context.new_page()

        print()
        print("Browser öffnet sich...")
        print("→ Garmin Connect einloggen (E-Mail, Passwort, MFA)")
        print("→ Fenster NICHT schließen bis 'Tokens erhalten'")
        print()

        await page.goto("https://connect.garmin.com/signin")

        # Warte bis beide Tokens da sind (max. 3 Minuten)
        for i in range(180):
            await asyncio.sleep(1)
            if oauth1_data and oauth2_data:
                print()
                print("✅ Beide Tokens erhalten — Browser kann geschlossen werden.")
                await asyncio.sleep(2)
                break
            if i == 179:
                print()
                print("⚠ Timeout nach 3 Minuten — bitte erneut versuchen.")

        try:
            await browser.close()
        except Exception:
            pass

    if not oauth1_data or not oauth2_data:
        print()
        print("❌ Tokens unvollständig:")
        print(f"   OAuth1: {'✓' if oauth1_data else '✗'}")
        print(f"   OAuth2: {'✓' if oauth2_data else '✗'}")
        print()
        print("Tipps:")
        print("  - Vollständig einloggen (auch MFA abschließen)")
        print("  - Warten bis Garmin Connect geladen ist")
        sys.exit(1)

    result = {
        "oauth1_token": oauth1_data,
        "oauth2_token": oauth2_data,
    }

    out = Path("garmin_tokens.json")
    out.write_text(json.dumps(result, indent=2))

    print()
    print(f"💾 Gespeichert: {out.absolute()}")
    print()
    print("Nächste Schritte:")
    print("  1. Inhalt der garmin_tokens.json kopieren")
    print("  2. Im HA Addon → Manuell → Token-Import einfügen")
    print("  3. 'Token importieren' klicken")
    print()


if __name__ == "__main__":
    asyncio.run(main())
