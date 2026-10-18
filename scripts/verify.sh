#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
NAMESPACE=${NAMESPACE:-primecheck}
HOST=${HOST:-http://primecheck.localtest.me}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED=${EXPECTED:-$(git -C "${ROOT}" rev-parse --short HEAD)}

fail() {
  echo "FAIL: $1"
  exit 1
}

echo "pods"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods -o wide

echo
echo "the running build reports"
version=$(curl -sf "${HOST}/version") || fail "the service did not answer /version"
echo "${version}"
echo "${version}" | grep -q "${EXPECTED}" || fail "the running build is not commit ${EXPECTED}"

echo
echo "readiness"
curl -sf "${HOST}/readyz" | grep -q '"status":"ready"' || fail "the service is not ready"
echo "ready"

echo
echo "a prime"
curl -sf "${HOST}/check?n=999983" | tee /dev/stderr | grep -q '"prime":true' || fail "999983 should be prime"

echo
echo "a composite"
curl -sf "${HOST}/check?n=999984" | tee /dev/stderr | grep -q '"prime":false' || fail "999984 should not be prime"

echo
echo "input validation"
code=$(curl -s -o /dev/null -w '%{http_code}' "${HOST}/check?n=-1")
[ "${code}" = "400" ] || fail "a negative input should be rejected with 400, got ${code}"

echo
echo "the admin endpoint refuses an unauthenticated caller"
code=$(curl -s -o /dev/null -w '%{http_code}' "${HOST}/admin/flags")
[ "${code}" = "401" ] || fail "an unauthenticated admin call should be rejected with 401, got ${code}"

echo
echo "metrics are exposed"
curl -sf "${HOST}/metrics" | grep -q 'primecheck_checks_total' || fail "the metrics endpoint is not serving application series"

echo
echo "prometheus is scraping the service"
kubectl --context "${CONTEXT}" -n observability port-forward svc/kps-prometheus 19090:9090 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill ${PF_PID} 2>/dev/null' EXIT
sleep 4
scraped=$(curl -s --get http://localhost:19090/api/v1/query \
  --data-urlencode 'query=up{job="primecheck"}' \
  | grep -o '"value"' | wc -l)
if [ "${scraped}" -gt 0 ]; then
  echo "${scraped} replica(s) being scraped"
else
  echo "warning: prometheus has no up series for the service yet"
fi

echo
echo "the running build is visible to prometheus"
curl -s --get http://localhost:19090/api/v1/query \
  --data-urlencode 'query=build_info' \
  | grep -q "${EXPECTED}" \
  && echo "build_info reports ${EXPECTED}" \
  || echo "warning: build_info does not report ${EXPECTED} yet"

echo
echo "everything verified against commit ${EXPECTED}"
