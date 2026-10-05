#!/usr/bin/env bash
# Copy test evidence out of the lab containers into results/evidence/<run-id>/.
# Run on the machine where the lab containers run (normally the GNS3 VM).
#
#   ./scripts/fetch-evidence.sh RUN-2026-10-12
#
# Collects:
#   - every *.log in /root on hosts A1, A2, B1, B2 (probe and iperf3 logs)
#   - a lab-evidence snapshot, frr.log and lab-boot.log from RA and RB
#   - inject-failure.log from the current directory, if present
set -euo pipefail

RUN_ID="${1:-}"
if [[ -z "$RUN_ID" ]]; then
    echo "Usage: $0 <run-id>   e.g. $0 RUN-$(date -u +%Y-%m-%d)" >&2
    exit 2
fi

cd "$(dirname "$0")/.."
DEST="results/evidence/${RUN_ID}"
mkdir -p "$DEST"

container_of() {
    local name=$1 id
    for id in $(docker ps -q); do
        if [[ "$(docker inspect -f '{{.Config.Hostname}}' "$id")" == "$name" ]]; then
            echo "$id"
            return 0
        fi
    done
    return 1
}

for host in A1 A2 B1 B2; do
    if ! cid=$(container_of "$host"); then
        echo "skip $host (not running)"
        continue
    fi
    for f in $(docker exec "$cid" sh -c 'ls /root/*.log 2>/dev/null' || true); do
        docker cp "${cid}:${f}" "${DEST}/$(basename "$f")"
        echo "copied ${host}:${f}"
    done
done

for router in RA RB; do
    if ! cid=$(container_of "$router"); then
        echo "skip $router (not running)"
        continue
    fi
    docker exec "$cid" lab-evidence "${RUN_ID}-final" > "${DEST}/${router}-state.txt"
    docker cp "${cid}:/var/log/frr/frr.log" "${DEST}/${router}-frr.log" 2>/dev/null || true
    docker cp "${cid}:/var/log/lab-boot.log" "${DEST}/${router}-boot.log" 2>/dev/null || true
    echo "collected ${router} state and logs"
done

if [[ -f inject-failure.log ]]; then
    cp inject-failure.log "${DEST}/inject-failure.log"
    echo "copied inject-failure.log"
fi

echo
echo "Evidence in ${DEST}:"
ls -1 "$DEST"
