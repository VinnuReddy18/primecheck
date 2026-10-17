from app.main import tester


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_readyz_reports_a_warm_sieve(client):
    body = client.get("/readyz").json()
    assert body["status"] == "ready"
    assert body["primes"] > 0


def test_index_serves_the_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "primecheck" in res.text


def test_check_prime(client):
    body = client.get("/check", params={"n": 104729}).json()
    assert body["n"] == 104729
    assert body["prime"] is True
    assert body["elapsed_ms"] >= 0


def test_check_composite(client):
    assert client.get("/check", params={"n": 104730}).json()["prime"] is False


def test_one_is_not_prime(client):
    assert client.get("/check", params={"n": 1}).json()["prime"] is False


def test_rejects_negative(client):
    res = client.get("/check", params={"n": -5})
    assert res.status_code == 400
    assert "negative" in res.json()["detail"]


def test_rejects_values_above_the_sieve_range(client):
    res = client.get("/check", params={"n": tester.max_n + 1})
    assert res.status_code == 400


def test_rejects_non_numeric_input(client):
    assert client.get("/check", params={"n": "abc"}).status_code == 422


def test_every_response_carries_a_request_id(client):
    res = client.get("/check", params={"n": 7})
    assert res.headers["x-request-id"]


def test_an_inbound_request_id_is_echoed_back(client):
    res = client.get("/check", params={"n": 7}, headers={"x-request-id": "abc123"})
    assert res.headers["x-request-id"] == "abc123"
