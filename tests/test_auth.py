from tests.conftest import register_user, login_user

def test_register_and_login(client):
    r = register_user(client, "user1@test.com", "Password123!")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "user1@test.com"
    assert data["role"] == "user"

    r = login_user(client, "user1@test.com", "Password123!")
    assert r.status_code == 200
    tok = r.json()
    assert "access_token" in tok
    assert "refresh_token" in tok

def test_refresh_token_rotation(client):
    register_user(client, "user2@test.com", "Password123!")
    r = login_user(client, "user2@test.com", "Password123!")
    tok = r.json()

    r2 = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r2.status_code == 200
    tok2 = r2.json()
    assert tok2["refresh_token"] != tok["refresh_token"]

    # old refresh should now be revoked
    r3 = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r3.status_code == 401
