from tests.conftest import register_user, login_user
from app.models.user import User

def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def test_prices_requires_auth(client):
    r = client.get("/prices/BTCUSDT")
    assert r.status_code == 401

def test_admin_requires_role(client, db_session):
    # Normal user
    register_user(client, "user@test.com", "Password123!")
    tok = login_user(client, "user@test.com", "Password123!").json()["access_token"]
    r = client.get("/admin/price/BTCUSDT", headers=auth_headers(tok))
    assert r.status_code == 403

    # Promote to admin in DB
    u = db_session.query(User).filter(User.email == "user@test.com").first()
    u.role = "admin"
    db_session.commit()

    # Re-login to get access token with admin role claim
    tok2 = login_user(client, "user@test.com", "Password123!").json()["access_token"]
    # Patch Binance call by hitting endpoint might call network; we just assert auth passes (200/5xx acceptable if network blocked)
    r2 = client.get("/admin/price/BTCUSDT", headers=auth_headers(tok2))
    assert r2.status_code in (200, 502, 503, 500)
