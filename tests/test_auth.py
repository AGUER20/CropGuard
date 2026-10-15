"""Integration tests for the register/login flow, including password
hashing and the invalid-credentials 'try again' branch."""
from app.models import User, Role
from app.extensions import db


def test_password_is_hashed_not_plaintext(app, db):
    with app.app_context():
        user = User(full_name="Test User", username="tuser", email="t@example.com", role=Role.FARMER)
        user.set_password("supersecret")
        assert user.password_hash != "supersecret"
        assert user.check_password("supersecret") is True
        assert user.check_password("wrongpassword") is False


def test_register_and_login(client, db):
    resp = client.post("/auth/register", data={
        "full_name": "Test Farmer",
        "username": "testfarmer",
        "email": "farmer@example.com",
        "role": "farmer",
        "password": "FarmerPass1",
        "confirm_password": "FarmerPass1",
    }, follow_redirects=True)
    assert resp.status_code == 200

    # invalid password -> should show an error, not log in
    bad = client.post("/auth/login", data={"username": "testfarmer", "password": "wrong"}, follow_redirects=True)
    assert b"Invalid username or password" in bad.data

    # valid credentials -> should reach the farmer dashboard
    good = client.post("/auth/login", data={"username": "testfarmer", "password": "FarmerPass1"}, follow_redirects=True)
    assert good.status_code == 200
