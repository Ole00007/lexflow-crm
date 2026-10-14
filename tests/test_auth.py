"""Authentication tests."""


def test_login_valid(client):
    resp = client.post("/api/auth/login", json={
        "email": "olesya00007@yahoo.com",
        "password": "Test12345!",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={
        "email": "olesya00007@yahoo.com",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "olesya00007@yahoo.com"})
    assert resp.status_code == 400


def test_me_with_token(client, superadmin_headers):
    resp = client.get("/api/auth/me", headers=superadmin_headers)
    assert resp.status_code == 200
    assert "email" in resp.get_json()


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
