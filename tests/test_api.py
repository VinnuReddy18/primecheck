from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_index_serves_the_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "primecheck" in res.text


def test_check_prime():
    body = client.get("/check", params={"n": 104729}).json()
    assert body["n"] == 104729
    assert body["prime"] is True
    assert body["elapsed_ms"] >= 0


def test_check_composite():
    body = client.get("/check", params={"n": 104730}).json()
    assert body["prime"] is False


def test_one_is_not_prime():
    assert client.get("/check", params={"n": 1}).json()["prime"] is False


def test_rejects_negative():
    res = client.get("/check", params={"n": -5})
    assert res.status_code == 400
    assert "negative" in res.json()["detail"]


def test_rejects_values_above_the_sieve_range():
    res = client.get("/check", params={"n": 10**12 + 1})
    assert res.status_code == 400


def test_rejects_non_numeric_input():
    assert client.get("/check", params={"n": "abc"}).status_code == 422
