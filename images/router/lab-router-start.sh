#!/bin/sh
# Start-up script for the lab router container (GNS3 Docker node).
#
# 1. Picks the router profile from $LAB_ROUTER, or from the hostname
#    (GNS3 sets the container hostname to the node name, e.g. "RA").
# 2. Creates VLAN subinterfaces listed in /lab/configs/<router>/vlans.
# 3. On first boot only, installs /lab/configs/<router>/frr.conf.
#    After that, whatever you save with "write memory" is kept
#    (make /etc/frr a persistent directory in the GNS3 template).
# 4. Enables the OSPF and BFD daemons and hands over to FRR's own start script.
# Every start is logged to /var/log/lab-boot.log (used by TC-12).
set -eu

ROUTER="${LAB_ROUTER:-$(hostname)}"
PROFILE="/lab/configs/${ROUTER}"

if [ ! -d "$PROFILE" ]; then
    echo "lab-router: no profile for '${ROUTER}'." >&2
    echo "lab-router: name the GNS3 node RA or RB, or set LAB_ROUTER." >&2
    echo "lab-router: starting FRR with the existing /etc/frr contents." >&2
fi

echo "$(date -u '+%Y/%m/%d %H:%M:%S') UTC lab-router: start (${ROUTER})" >> /var/log/lab-boot.log

sysctl -w net.ipv4.ip_forward=1 >/dev/null

if [ -f "${PROFILE}/vlans" ]; then
    grep -v '^[[:space:]]*#' "${PROFILE}/vlans" | while read -r parent vid; do
        [ -n "${parent}" ] || continue
        sub="${parent}.${vid}"
        if ip link show "${sub}" >/dev/null 2>&1 \
            || ip link add link "${parent}" name "${sub}" type vlan id "${vid}"; then
            ip link set "${parent}" up
            ip link set "${sub}" up
            echo "lab-router: ${sub} ready (VLAN ${vid} on ${parent})"
        else
            echo "lab-router: ERROR could not create ${sub}" >&2
        fi
    done
fi

if [ -f "${PROFILE}/frr.conf" ] && [ ! -f /etc/frr/.lab-initialized ]; then
    cp "${PROFILE}/frr.conf" /etc/frr/frr.conf
    touch /etc/frr/.lab-initialized
    echo "lab-router: installed baseline config for ${ROUTER}"
fi

sed -i -e 's/^ospfd=no/ospfd=yes/' -e 's/^bfdd=no/bfdd=yes/' /etc/frr/daemons

mkdir -p /var/log/frr
chown -R frr:frr /etc/frr /var/log/frr

exec /usr/lib/frr/docker-start
