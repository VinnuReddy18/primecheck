#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${CLUSTER:-primecheck}
CONTEXT="kind-${CLUSTER}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! kind get clusters | grep -qx "${CLUSTER}"; then
  kind create cluster --config "${ROOT}/kind/cluster.yaml"
fi

kubectl --context "${CONTEXT}" create namespace primecheck --dry-run=client -o yaml \
  | kubectl --context "${CONTEXT}" apply -f -
kubectl --context "${CONTEXT}" label namespace primecheck \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted --overwrite

kubectl --context "${CONTEXT}" create namespace observability --dry-run=client -o yaml \
  | kubectl --context "${CONTEXT}" apply -f -

helm --kube-context "${CONTEXT}" repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
helm --kube-context "${CONTEXT}" repo add metrics-server https://kubernetes-sigs.github.io/metrics-server >/dev/null 2>&1 || true
helm --kube-context "${CONTEXT}" repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets >/dev/null 2>&1 || true
helm --kube-context "${CONTEXT}" repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm --kube-context "${CONTEXT}" repo update >/dev/null

helm --kube-context "${CONTEXT}" upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.hostPort.enabled=true \
  --set "controller.nodeSelector.ingress-ready=true" \
  --set controller.admissionWebhooks.enabled=false \
  --wait --timeout 5m

helm --kube-context "${CONTEXT}" upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --set "args={--kubelet-insecure-tls}" \
  --wait --timeout 5m

helm --kube-context "${CONTEXT}" upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system \
  --set fullnameOverride=sealed-secrets-controller \
  --wait --timeout 5m

helm --kube-context "${CONTEXT}" upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace observability \
  --values "${ROOT}/deploy/observability/kube-prometheus-stack.yaml" \
  --wait --timeout 10m

kubectl --context "${CONTEXT}" apply -f "${ROOT}/deploy/observability/jaeger.yaml"
kubectl --context "${CONTEXT}" -n observability rollout status deploy/jaeger --timeout=5m

kubectl --context "${CONTEXT}" -n observability create configmap primecheck-dashboard \
  --from-file=primecheck.json="${ROOT}/dashboards/primecheck.json" \
  --dry-run=client -o yaml \
  | kubectl --context "${CONTEXT}" label --local -f - grafana_dashboard=1 -o yaml --dry-run=client \
  | kubectl --context "${CONTEXT}" apply -f -

echo "cluster ${CLUSTER} is ready"
