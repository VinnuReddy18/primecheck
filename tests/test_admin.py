from tests.conftest import ADMIN_TOKEN

HEADERS = {"x-admin-token": ADMIN_TOKEN}


def test_reading_flags_requires_a_token(client):
    assert client.get("/admin/flags").status_code == 401


def test_reading_flags_rejects_a_wrong_token(client):
    assert client.get("/admin/flags", headers={"x-admin-token": "wrong"}).status_code == 401


def test_reading_flags_with_the_right_token(client):
    body = client.get("/admin/flags", headers=HEADERS).json()
    assert body == {"factor_hint": False}


def test_writing_flags_requires_a_token(client):
    assert client.post("/admin/flags", json={"factor_hint": True}).status_code == 401


def test_toggling_the_flag_changes_the_response_body(client):
    before = client.get("/check", params={"n": 104730}).json()
    assert "smallest_factor" not in before

    client.post("/admin/flags", json={"factor_hint": True}, headers=HEADERS)

    after = client.get("/check", params={"n": 104730}).json()
    assert after["smallest_factor"] == 2


def test_toggling_reports_the_previous_value(client):
    body = client.post("/admin/flags", json={"factor_hint": True}, headers=HEADERS).json()
    assert body == {"factor_hint": True, "previous": False}


def test_a_malformed_body_is_rejected(client):
    res = client.post("/admin/flags", json={"factor_hint": "maybe"}, headers=HEADERS)
    assert res.status_code == 422
