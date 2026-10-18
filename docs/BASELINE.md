# Baseline

| | |
| --- | --- |
| Name | Vinay Kumar Reddy |
| Student identifier | 23bcs10083 |
| Project name | primecheck |
| Repository | https://github.com/VinnuReddy18/primecheck |
| Baseline commit | `015309b92e7f66d99e80da109777bba9c72ef026` |

## The application

primecheck is a small web service that tells you whether a number is prime. It builds a sieve of Eratosthenes up to one million when the process starts, then answers each query by trial division against those primes, which proves primality for any input up to 10^12. It serves a single page web form and a JSON API.

## The preserved baseline

The commit above is the tip of `main` and stays in the repository history. Every improvement in the pull request is measured against it.

```
git diff 015309b92e7f66d99e80da109777bba9c72ef026..devops --stat
```

At that commit the project was ten tracked files: the FastAPI app, the sieve, two test modules, and pinned requirements. It had three routes, the web page, `/healthz` and `/check`. The sieve was built synchronously at import, so the process accepted no connections for about a second after starting. Input validation rejected negative numbers and anything above the provable range, and 33 tests were run by hand.

## DevOps features that already existed

| Area | At the baseline |
| --- | --- |
| Containerisation | None |
| Orchestration | None |
| Deployment configuration | None. The only path was `uvicorn` on a developer machine |
| CI and CD | None |
| Release control | None. A hardcoded version string, no rollback path |
| Observability | None. No metrics, no structured logging, no tracing. Logging was whatever uvicorn printed |
| Security | Partial. Requirements pinned and `.gitignore` excluded env files and keys. No secret management, image scanning, runtime hardening or network policy |
| Health checks | Partial. A `/healthz` route existed, but nothing consumed it and there was no readiness concept |
| Tests | Present. 33 tests, run by hand |

The test suite and the pinned requirements were the real groundwork. The pull request adds the rest.
