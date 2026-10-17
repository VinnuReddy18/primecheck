#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
NAMESPACE=${NAMESPACE:-primecheck}
REVISION=${1:-}

helm --kube-context "${CONTEXT}" -n "${NAMESPACE}" history primecheck

if [ -z "${REVISION}" ]; then
  helm --kube-context "${CONTEXT}" -n "${NAMESPACE}" rollback primecheck
else
  helm --kube-context "${CONTEXT}" -n "${NAMESPACE}" rollback primecheck "${REVISION}"
fi

kubectl --context "${CONTEXT}" -n "${NAMESPACE}" rollout status deploy/primecheck --timeout=5m
