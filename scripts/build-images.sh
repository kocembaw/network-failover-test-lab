#!/usr/bin/env bash
# Build the two lab images. Run from anywhere on the machine where GNS3
# runs Docker (normally the GNS3 VM).
#   ./scripts/build-images.sh                 # FRR 10.0.0 (default)
#   FRR_TAG=10.2.1 ./scripts/build-images.sh  # another tag from quay.io/frrouting/frr
set -euo pipefail

cd "$(dirname "$0")/.."

docker build --build-arg "FRR_TAG=${FRR_TAG:-10.0.0}" \
    -f images/router/Dockerfile -t lab-router:latest .
docker build -f images/host/Dockerfile -t lab-host:latest .

echo
docker image ls --format '{{.Repository}}:{{.Tag}}  {{.ID}}  {{.CreatedSince}}' \
    | grep -E '^lab-(router|host):'
