#!/bin/sh
# Print a timestamped snapshot of the router state for test evidence.
# Usage: lab-evidence [label]        e.g.  lab-evidence TC-07-after
# Copy the output into results/evidence/<run>/<TC>-<router>.txt
LABEL="${1:-snapshot}"

echo "===== $(hostname) | ${LABEL} | $(date -u '+%Y-%m-%d %H:%M:%S') UTC ====="
for cmd in \
    "show interface brief" \
    "show ip ospf neighbor" \
    "show ip route"
do
    echo
    echo "--- ${cmd}"
    vtysh -c "${cmd}"
done
echo
echo "--- kernel link state (ip -br link)"
ip -br link
echo
echo "--- last 20 OSPF log lines"
grep -i ospf /var/log/frr/frr.log 2>/dev/null | tail -n 20
