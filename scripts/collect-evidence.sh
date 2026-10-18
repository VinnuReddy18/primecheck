#!/usr/bin/env bash
set -uo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
NAMESPACE=${NAMESPACE:-primecheck}
HOST=${HOST:-http://primecheck.localtest.me}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=${OUT:-"${ROOT}/docs/evidence"}
SHA=$(git -C "${ROOT}" rev-parse --short HEAD)

mkdir -p "${OUT}"

kubectl --context "${CONTEXT}" -n observability port-forward svc/kps-prometheus 19090:9090 >/dev/null 2>&1 &
PROM_PID=$!
kubectl --context "${CONTEXT}" -n observability port-forward svc/jaeger-query 16686:16686 >/dev/null 2>&1 &
JAEGER_PID=$!
trap 'kill ${PROM_PID} ${JAEGER_PID} 2>/dev/null' EXIT
sleep 5

{
  echo "collected at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repository commit ${SHA}"
  echo ""
  echo "===== cluster nodes ====="
  kubectl --context "${CONTEXT}" get nodes -o wide
  echo ""
  echo "===== workloads ====="
  kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get all -o wide
  echo ""
  echo "===== configuration and policy ====="
  kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get cm,secret,sa,netpol,ingress,pdb
  echo ""
  echo "===== pod security context as admitted ====="
  kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\n  securityContext: "}{.spec.securityContext}{"\n  container:       "}{.spec.containers[0].securityContext}{"\n  image:           "}{.spec.containers[0].image}{"\n  node:            "}{.spec.nodeName}{"\n"}{end}'
  echo ""
  echo "===== namespace pod security standard ====="
  kubectl --context "${CONTEXT}" get ns "${NAMESPACE}" -o jsonpath='{.metadata.labels}'
  echo ""
  echo ""
  echo "===== helm releases ====="
  helm --kube-context "${CONTEXT}" list -A
  echo ""
  echo "===== primecheck release history ====="
  helm --kube-context "${CONTEXT}" -n "${NAMESPACE}" history primecheck
} > "${OUT}/cluster-state.txt" 2>&1

{
  echo "===== the running build ====="
  curl -s "${HOST}/version"
  echo ""
  echo ""
  echo "===== readiness ====="
  curl -s "${HOST}/readyz"
  echo ""
  echo ""
  echo "===== a prime ====="
  curl -s "${HOST}/check?n=999983"
  echo ""
  echo ""
  echo "===== a composite ====="
  curl -s "${HOST}/check?n=999984"
  echo ""
  echo ""
  echo "===== a rejected input ====="
  curl -s -w "\nHTTP %{http_code}\n" "${HOST}/check?n=-1"
  echo ""
  echo "===== an unauthenticated admin call ====="
  curl -s -w "\nHTTP %{http_code}\n" "${HOST}/admin/flags"
  echo ""
  echo "===== the request id travels with the response ====="
  curl -s -D - -o /dev/null "${HOST}/check?n=7919" | grep -i 'x-request-id'
} > "${OUT}/user-journey.txt" 2>&1

{
  echo "===== application metric series ====="
  curl -s "${HOST}/metrics" | grep -E '^(primecheck_|build_info|http_requests_total|http_request_duration_seconds_count)' | head -40
} > "${OUT}/metrics-sample.txt" 2>&1

{
  echo "queried through the prometheus api"
  echo ""
  for q in \
    'up{job="primecheck"}' \
    'build_info' \
    'primecheck:availability_ratio:rate5m' \
    'primecheck:request_error_ratio:rate5m' \
    'primecheck:request_latency_p95:rate5m' \
    'sum(primecheck_ready)' \
    'max(primecheck_sieve_primes)' \
    'sum by (result) (primecheck_checks_total)' \
    'sum by (route,status) (http_requests_total)'
  do
    echo "----- ${q}"
    curl -s --get http://localhost:19090/api/v1/query --data-urlencode "query=${q}" \
      | python -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print('  no response'); raise SystemExit
for r in d.get('data',{}).get('result',[]):
    labels={k:v for k,v in r['metric'].items() if k not in ('__name__','endpoint','container','instance','pod','service','job','namespace')}
    print('  ', labels if labels else '{}', '=', r['value'][1])
" 2>/dev/null
    echo ""
  done
  echo "===== alerting rules loaded ====="
  curl -s http://localhost:19090/api/v1/rules | python -c "
import json,sys
d=json.load(sys.stdin)
for g in d.get('data',{}).get('groups',[]):
    if 'primecheck' not in g['name']:
        continue
    print(g['name'])
    for r in g['rules']:
        kind = r.get('type')
        print('   ', kind, r.get('name'), 'state=' + str(r.get('state','n/a')))
" 2>/dev/null
} > "${OUT}/prometheus.txt" 2>&1

{
  echo "===== services reporting traces ====="
  curl -s http://localhost:16686/api/services
  echo ""
  echo ""
  echo "===== a recent trace ====="
  curl -s "http://localhost:16686/api/traces?service=primecheck&limit=1" | python -c "
import json,sys
d=json.load(sys.stdin)
for t in d.get('data',[])[:1]:
    print('traceID', t['traceID'])
    for s in sorted(t['spans'], key=lambda s: s['startTime']):
        print('  %-28s %8d us' % (s['operationName'], s['duration']))
" 2>/dev/null
} > "${OUT}/tracing.txt" 2>&1

{
  echo "===== structured application logs ====="
  kubectl --context "${CONTEXT}" -n "${NAMESPACE}" logs -l app.kubernetes.io/name=primecheck \
    --tail=25 --prefix 2>&1
} > "${OUT}/logs-sample.txt" 2>&1

kill ${PROM_PID} ${JAEGER_PID} 2>/dev/null
trap - EXIT

echo "evidence written to ${OUT}"
ls -1 "${OUT}"
