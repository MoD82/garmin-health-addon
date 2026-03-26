import pytest


def test_trends_returns_200(client):
    resp = client.get("/trends")
    assert resp.status_code == 200


def test_trends_contains_pmc_chart(client):
    resp = client.get("/trends")
    assert "PMC" in resp.text or "Fitness" in resp.text or "svg" in resp.text.lower()


def test_trends_days_param(client):
    for days in [30, 90, 180, 365]:
        resp = client.get(f"/trends?days={days}")
        assert resp.status_code == 200


def test_trends_contains_weekly_volume(client):
    resp = client.get("/trends")
    assert "Wochenvolumen" in resp.text or "Volumen" in resp.text
