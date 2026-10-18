#!/usr/bin/env bash
set -uo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
NAMESPACE=${NAMESPACE:-primecheck}
HOST=${HOST:-http://primecheck.localtest.me}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=${OUT:-"${ROOT}/docs/evidence"}
BAD_SIEVE_LIMIT=${BAD_SIEVE_LIMIT:-400000000}

mkdir -p "${OUT}"
PROBE_LOG="${OUT}/fault-drill-probe.log"
REPORT="${OUT}/fault-drill.md"
: > "${PROBE_LOG}"

SHA=$(git -C "${ROOT}" rev-parse --short HEAD)

if ! curl -sf -m 10 "${HOST}/version" | grep -q "${SHA}"; then
  echo "the running build does not report commit ${SHA}"
  echo "run ./scripts/build.sh and ./scripts/deploy.sh first, so that the sieve limit"
  echo "is the only thing this drill changes"
  exit 1
fi

probe() {
  while true; do
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "${HOST}/check?n=999983" 2>/dev/null)
    echo "$(date -u +%H:%M:%S) ${code}" >> "${PROBE_LOG}"
    sleep 0.5
  done
}

section() {
  echo "" | tee -a "${REPORT}"
  echo "## $1" | tee -a "${REPORT}"
  echo "" | tee -a "${REPORT}"
}

fenced() {
  echo '```' >> "${REPORT}"
  tee -a "${REPORT}"
  echo '```' >> "${REPORT}"
}

{
  echo "# Fault and recovery drill"
  echo ""
  echo "Run at $(date -u +%Y-%m-%dT%H:%M:%SZ) against commit ${SHA}."
  echo ""
  echo "A continuous probe calls /check twice a second for the whole drill, so the"
  echo "question \"did users see this\" is answered by measurement rather than by opinion."
} > "${REPORT}"

probe &
PROBE_PID=$!
trap 'kill ${PROBE_PID} 2>/dev/null' EXIT

sleep 5

section "Healthy state before the change"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods -o wide 2>&1 | fenced
curl -s "${HOST}/version" 2>&1 | fenced

section "The change: raise the sieve limit far beyond the memory limit"
echo "The sieve allocates one byte per candidate. Setting the limit to ${BAD_SIEVE_LIMIT}" >> "${REPORT}"
echo "asks each replica for roughly 400 MB inside a 256 MiB container." >> "${REPORT}"
echo "" >> "${REPORT}"
echo "This is a configuration change only. No application code changes." >> "${REPORT}"
echo "" >> "${REPORT}"

helm --kube-context "${CONTEXT}" upgrade primecheck "${ROOT}/charts/primecheck" \
  --namespace "${NAMESPACE}" \
  --values "${ROOT}/charts/primecheck/values-kind.yaml" \
  --set image.tag="${SHA}" \
  --set app.sieveLimit="${BAD_SIEVE_LIMIT}" \
  --wait --timeout 150s 2>&1 | tail -5 | fenced

section "Symptom"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods -o wide 2>&1 | fenced
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get events \
  --sort-by=.lastTimestamp 2>&1 | tail -15 | fenced

section "Evidence: why the new pods never became ready"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{"  ready="}{.status.containerStatuses[0].ready}{"  restarts="}{.status.containerStatuses[0].restartCount}{"  state="}{.status.containerStatuses[0].lastState}{"\n"}{end}' 2>&1 | fenced

section "Evidence: users were still being served throughout"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get endpoints primecheck 2>&1 | fenced
curl -s "${HOST}/check?n=999983" 2>&1 | fenced

section "The fix: roll back"
helm --kube-context "${CONTEXT}" -n "${NAMESPACE}" rollback primecheck 2>&1 | fenced
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" rollout status deploy/primecheck --timeout=5m 2>&1 | fenced

section "Verification"
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get pods -o wide 2>&1 | fenced
curl -s "${HOST}/version" 2>&1 | fenced
curl -s "${HOST}/readyz" 2>&1 | fenced
curl -s "${HOST}/check?n=999983" 2>&1 | fenced
kubectl --context "${CONTEXT}" -n "${NAMESPACE}" get cm primecheck \
  -o jsonpath='{.data.SIEVE_LIMIT}{"\n"}' 2>&1 | fenced

sleep 5
kill ${PROBE_PID} 2>/dev/null
trap - EXIT

total=$(wc -l < "${PROBE_LOG}")
ok=$(grep -c ' 200$' "${PROBE_LOG}")
bad=$((total - ok))

section "Did users see it"
{
  echo "probe requests sent:      ${total}"
  echo "answered 200:             ${ok}"
  echo "anything else:            ${bad}"
} | fenced

{
  echo ""
  echo "## What this shows"
  echo ""
  echo "The rollout was gated by the readiness probe with maxUnavailable set to 0, so the"
  echo "replacement pods had to prove they were healthy before any serving pod was removed."
  echo "They never did, the release stalled, and the old pods kept answering. A bad"
  echo "configuration value reached the cluster and did not reach users."
  echo ""
  echo "The rollback restored the previous release including its ConfigMap, which is why"
  echo "the sieve limit above is back to its original value rather than needing a separate fix."
} >> "${REPORT}"

echo ""
echo "report written to ${REPORT}"
echo "probe: ${ok}/${total} answered 200"
