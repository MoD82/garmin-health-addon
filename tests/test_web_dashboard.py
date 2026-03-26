import pytest


def test_dashboard_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_dashboard_has_recommendation_card(client):
    """Empfehlung-Emoji ist vorhanden."""
    resp = client.get("/")
    assert any(x in resp.text for x in ["🛑", "🚶", "🚴", "💪", "⚡", "🔥", "🏆"])


def test_dashboard_has_fitness_widgets(client):
    """CTL/ATL Widgets sind vorhanden."""
    resp = client.get("/")
    assert "Fitness" in resp.text or "CTL" in resp.text


def test_dashboard_has_form_widget(client):
    resp = client.get("/")
    assert "Form" in resp.text or "TSB" in resp.text
