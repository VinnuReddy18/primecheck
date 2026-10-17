#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
NAMESPACE=${NAMESPACE:-primecheck}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TAG=${TAG:-$(git -C "${ROOT}" rev-parse --short HEAD)}
DIGEST=${DIGEST:-}

kubectl --context "${CONTEXT}" apply -f "${ROOT}/deploy/secrets/admin-sealedsecret.yaml"

args=(
  upgrade --install primecheck "${ROOT}/charts/primecheck"
  --namespace "${NAMESPACE}"
  --values "${ROOT}/charts/primecheck/values-kind.yaml"
  --wait --timeout 5m
)

if [ -n "${DIGEST}" ]; then
  args+=(--set image.repository=ghcr.io/vinnureddy18/primecheck)
  args+=(--set image.digest="${DIGEST}")
  args+=(--set image.pullPolicy=IfNotPresent)
else
  args+=(--set image.tag="${TAG}")
fi

helm --kube-context "${CONTEXT}" "${args[@]}"

kubectl --context "${CONTEXT}" -n "${NAMESPACE}" rollout status deploy/primecheck --timeout=5m
