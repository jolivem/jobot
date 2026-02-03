from tests.conftest import register_user, login_user

def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def test_portfolio_crud(client, monkeypatch):
    register_user(client, "p@test.com", "Password123!")
    tok = login_user(client, "p@test.com", "Password123!").json()["access_token"]

    # Add asset
    r = client.post("/portfolio", json={"symbol": "BTCUSDT", "quantity": 0.5}, headers=auth_headers(tok))
    assert r.status_code == 200
    asset = r.json()
    assert asset["symbol"] == "BTCUSDT"
    assert asset["quantity"] == 0.5

    # List assets
    r = client.get("/portfolio", headers=auth_headers(tok))
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Mock price fetch for valuation
    from app.services.binance_price_service import BinancePriceService
    monkeypatch.setattr(BinancePriceService, "get_price", lambda self, symbol: 40000.0)

    r = client.get("/portfolio/valuation", headers=auth_headers(tok))
    assert r.status_code == 200
    val = r.json()
    assert val["total_value"] == 40000.0 * 0.5
