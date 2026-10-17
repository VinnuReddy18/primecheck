import json
import logging

from app.observability import JsonFormatter


def test_metrics_endpoint_is_prometheus_formatted(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]


def test_metrics_expose_the_application_series(client):
    client.get("/check", params={"n": 7919})
    body = client.get("/metrics").text
    assert "primecheck_checks_total" in body
    assert "http_request_duration_seconds_bucket" in body
    assert "primecheck_sieve_primes" in body
    assert "build_info" in body


def test_check_counter_is_labelled_by_outcome(client):
    client.get("/check", params={"n": 7919})
    client.get("/check", params={"n": 7918})
    body = client.get("/metrics").text
    assert 'primecheck_checks_total{result="prime"}' in body
    assert 'primecheck_checks_total{result="composite"}' in body


def test_ready_gauge_is_one_once_warm(client):
    body = client.get("/metrics").text
    assert "primecheck_ready 1.0" in body


def test_version_endpoint_reports_build_metadata(client):
    body = client.get("/version").json()
    assert set(body) == {"version", "git_sha", "build_time"}


def test_log_records_are_json():
    record = logging.LogRecord("primecheck", logging.INFO, "", 0, "check completed", (), None)
    record.n = 7919
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "check completed"
    assert payload["level"] == "INFO"
    assert payload["service"] == "primecheck"
    assert payload["n"] == 7919


def test_log_records_carry_the_exception_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "primecheck", logging.ERROR, "", 0, "failed", (), sys.exc_info()
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
