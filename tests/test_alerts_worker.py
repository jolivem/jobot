from tests.conftest import register_user, login_user

def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def test_alert_triggers_and_creates_event(client, monkeypatch):
    register_user(client, "a@test.com", "Password123!")
    tok = login_user(client, "a@test.com", "Password123!").json()["access_token"]

    # Create alert: trigger when price above 100
    r = client.post("/alerts", json={"symbol": "BTCUSDT", "target_price": 100.0, "direction": "above"}, headers=auth_headers(tok))
    assert r.status_code == 200

    # Patch Binance price to trigger
    from app.services.binance_price_service import BinancePriceService
    monkeypatch.setattr(BinancePriceService, "get_price", lambda self, symbol: 150.0)

    # Run worker task synchronously
    from app.workers.tasks import check_price_alerts
    check_price_alerts()

    # Events should exist
    r2 = client.get("/alerts/events", headers=auth_headers(tok))
    assert r2.status_code == 200
    events = r2.json()
    assert len(events) >= 1
    assert events[0]["symbol"] == "BTCUSDT"
