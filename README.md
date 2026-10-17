# primecheck

A small web service that tells you whether a number is prime.

It builds a sieve of Eratosthenes up to one million at startup, then answers queries by trial division against those primes. That makes any number up to 10^12 provable, because the square root of 10^12 is one million and the sieve already holds every prime below it.

## Running it

Requires Python 3.12 or newer.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Open http://localhost:8000 in a browser, or call the API directly.

```
curl "http://localhost:8000/check?n=104729"
{"n":104729,"prime":true,"elapsed_ms":0.6}
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | The web page |
| GET | `/healthz` | Liveness check |
| GET | `/check?n=` | Test one number |

## Tests

```
pip install -r requirements-dev.txt
pytest
```

## Known limitations

The sieve is built synchronously at import, so the process does not accept connections for the first second or so after it starts. Numbers above 10^12 are rejected rather than tested, because the sieve cannot prove primality beyond the square of its limit.
