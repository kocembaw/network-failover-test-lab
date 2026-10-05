#!/usr/bin/env bash
# Inject and clear WAN failures in the lab, with a millisecond timestamp
# you can line up against the failover-probe log.
#
# Run it where the lab containers run: inside the GNS3 VM, or on your Linux
# machine if GNS3 runs Docker locally. Routers are found by hostname, which
# GNS3 sets to the node name (RA, RB). Override with RA_CONTAINER / RB_CONTAINER
# (container ID or name) if your nodes are named differently.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: inject-failure.sh <action>

  hard     primary WAN link (eth1) down on RA and RB: both routers lose carrier
  silent   primary WAN link drops all IP traffic, interfaces stay up
           (like a faulty carrier switch or media converter)
  isolate  primary and backup WAN links (eth1, eth2) down on both routers
  restore  clear every failure above
  status   WAN interface state, fault rules and OSPF neighbours on both routers

Every action is appended to inject-failure.log (override with LAB_FAULT_LOG).
EOF
}

ROUTERS=(RA RB)
LOG_FILE="${LAB_FAULT_LOG:-inject-failure.log}"
declare -A CID

find_container() {
    local name=$1 id
    for id in $(docker ps -q); do
        if [[ "$(docker inspect -f '{{.Config.Hostname}}' "$id")" == "$name" ]]; then
            echo "$id"
            return 0
        fi
    done
    echo "inject-failure: no running container with hostname '$name'." >&2
    echo "inject-failure: start the GNS3 node and make sure it is named '$name'." >&2
    return 1
}

on_router() {   # on_router RA "command ..."
    local r=$1; shift
    docker exec "${CID[$r]}" sh -c "$*"
}

wait_all() {    # wait for background jobs, fail if any of them failed
    local pid rc=0
    for pid in "$@"; do wait "$pid" || rc=1; done
    if [[ $rc -ne 0 ]]; then
        echo "inject-failure: command failed on at least one router (see above)" >&2
        exit 1
    fi
}

on_both() {     # run the same command on both routers at the same moment
    local r pids=()
    for r in "${ROUTERS[@]}"; do on_router "$r" "$*" & pids+=($!); done
    wait_all "${pids[@]}"
}

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S.%3N') UTC] $*" | tee -a "$LOG_FILE"
}

# nftables rules that drop every IP packet on eth1 while the link stays up
SILENT_RULESET='table inet lab_fault {
    chain drop_in  { type filter hook input   priority -10; policy accept; iifname "eth1" drop; }
    chain drop_out { type filter hook output  priority -10; policy accept; oifname "eth1" drop; }
    chain drop_fwd { type filter hook forward priority -10; policy accept; iifname "eth1" drop; oifname "eth1" drop; }
}'

action="${1:-}"
case "$action" in
    hard|silent|isolate|restore|status) ;;
    *) usage; exit 2 ;;
esac

for r in "${ROUTERS[@]}"; do
    override="${r}_CONTAINER"
    CID[$r]="${!override:-$(find_container "$r")}"
done

case "$action" in
    hard)
        log "INJECT hard: eth1 down on RA and RB"
        on_both "ip link set eth1 down"
        ;;
    silent)
        log "INJECT silent: eth1 drops all IP traffic on RA and RB (link stays up)"
        pids=()
        for r in "${ROUTERS[@]}"; do
            printf '%s\n' "$SILENT_RULESET" | docker exec -i "${CID[$r]}" nft -f - &
            pids+=($!)
        done
        wait_all "${pids[@]}"
        ;;
    isolate)
        log "INJECT isolate: eth1 and eth2 down on RA and RB"
        on_both "ip link set eth1 down; ip link set eth2 down"
        ;;
    restore)
        log "RESTORE: eth1/eth2 up and fault rules removed on RA and RB"
        on_both "ip link set eth1 up; ip link set eth2 up; nft delete table inet lab_fault 2>/dev/null || true"
        ;;
    status)
        for r in "${ROUTERS[@]}"; do
            echo "===== $r"
            on_router "$r" "ip -br link show eth1; ip -br link show eth2"
            if on_router "$r" "nft list table inet lab_fault >/dev/null 2>&1"; then
                echo "fault rules: ACTIVE (silent failure on eth1)"
            else
                echo "fault rules: none"
            fi
            docker exec "${CID[$r]}" vtysh -c "show ip ospf neighbor"
        done
        ;;
esac
