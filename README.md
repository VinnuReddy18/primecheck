# primecheck

A web service that tells you whether a number is prime, running on Kubernetes.

It builds a sieve of Eratosthenes up to one million at startup, then answers queries by trial division against those primes. That proves primality for any input up to 10^12.

## Prerequisites

Docker, kind, kubectl, Helm 3.16 or newer, Python 3.12. About 6 GB of free memory.

## Build and deploy

```
./scripts/cluster-up.sh
./scripts/build.sh
./scripts/deploy.sh
./scripts/verify.sh
```

`cluster-up.sh` creates a three node kind cluster and installs ingress-nginx, metrics-server, the sealed secrets controller, kube-prometheus-stack and Jaeger. It is safe to re-run. The first run takes about ten minutes, mostly pulling images.

Then open http://primecheck.localtest.me. `localtest.me` resolves to 127.0.0.1, so no hosts file entry is needed.

To deploy a published image by digest instead of a local build:

```
DIGEST=sha256:... ./scripts/deploy.sh
```

Without Kubernetes: `pip install -r requirements-dev.txt`, then `pytest` and `uvicorn app.main:app --port 8000`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | The web page |
| GET | `/check?n=` | Test one number |
| GET | `/healthz` | Liveness |
| GET | `/readyz` | Readiness, true once the sieve is warm |
| GET | `/version` | The commit this image was built from |
| GET | `/metrics` | Prometheus exposition |
| GET | `/admin/flags` | Read the feature flag, needs `x-admin-token` |
| POST | `/admin/flags` | Toggle it, needs `x-admin-token` |

```
curl -s "http://primecheck.localtest.me/check?n=999983"
{"n":999983,"prime":true,"elapsed_ms":1.237}
```

## Observability

| What | Where |
| --- | --- |
| Grafana | `kubectl -n observability port-forward svc/kps-grafana 3000:80` |
| Prometheus | `kubectl -n observability port-forward svc/kps-prometheus 9090:9090` |
| Jaeger | `kubectl -n observability port-forward svc/jaeger-query 16686:16686` |

Grafana allows anonymous viewers, so no login is needed.

## Alert response

Each alert in `charts/primecheck/templates/prometheusrule.yaml` links here.

| Alert | First response |
| --- | --- |
| `PrimecheckHighErrorRate` | Break `http_requests_total` down by route and status. Errors on one route point at the last release, so roll back. Errors spread across routes point at a dependency |
| `PrimecheckHighLatency` | Compare the `primality` span against the request span in Jaeger. If the computation is fast and the request is slow, the time is in transport or node pressure, not the algorithm |
| `PrimecheckWarmingTooLong` | `primecheck_ready` is still 0 past startup. Check `SIEVE_LIMIT` in the ConfigMap against the container memory limit, and check for `OOMKilled` |
| `PrimecheckNoReadyReplicas` | Full outage. Run `./scripts/rollback.sh`, then read the failed rollout's pod events |
| `PrimecheckAutoscalerAtCeiling` | The HPA is pinned at `maxReplicas`. Raise it if the nodes have room, otherwise the ceiling is correct and the load needs shedding |

## Recovering from a bad release

```
./scripts/rollback.sh
```

Rollouts use `maxUnavailable: 0`, so a new pod must pass readiness before an old one is removed. A broken release stalls instead of taking the service down.

## Known limitations

The cluster is local, so the final deploy is run by an operator after the release workflow's approval gate rather than from inside the pipeline. CI deploys to a throwaway cluster of its own and verifies there. Ingress TLS uses the controller's self signed certificate. Jaeger stores traces in memory. There is no log aggregation.

## Baseline and evidence

The starting point is preserved on `main`. See [docs/BASELINE.md](docs/BASELINE.md) for what it contained and [docs/EVIDENCE.md](docs/EVIDENCE.md) for what the finished system was observed doing.
