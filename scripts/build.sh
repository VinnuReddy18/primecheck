#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${CLUSTER:-primecheck}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHA=$(git -C "${ROOT}" rev-parse --short HEAD)
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if [ -n "$(git -C "${ROOT}" status --porcelain)" ]; then
  echo "warning: the working tree is dirty, so the image will not match commit ${SHA} exactly"
fi

docker build \
  --build-arg GIT_SHA="${SHA}" \
  --build-arg BUILD_TIME="${BUILD_TIME}" \
  -t "primecheck:${SHA}" \
  "${ROOT}"

kind load docker-image "primecheck:${SHA}" --name "${CLUSTER}"

echo "${SHA}"
