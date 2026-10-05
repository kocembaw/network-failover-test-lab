# Recording a test run and its evidence

## Before the run

1. Pick a run ID, e.g. `RUN-2026-10-12`. Copy [`results/RUN_TEMPLATE.md`](../results/RUN_TEMPLATE.md) to `results/RUN-2026-10-12.md`.
2. Fill in the environment table: GNS3 version, FRR version (`RA# vtysh -c "show version"`), image IDs (`VM$ docker image ls lab-*`).
3. On the GNS3 VM, start from a clean fault log: `VM$ rm -f inject-failure.log`.

## During the run

| Evidence | How |
|---|---|
| Outage measurements | `failover-probe run ... --log /root/TC-xx-probe.log` on A1. The report at the end is the key result, so copy it into the run report. |
| Fault injection times | Written automatically to `inject-failure.log` by `inject-failure.sh` |
| Router state | `RA# lab-evidence TC-xx-after`, copied into `TC-xx-RA.txt` |
| OSPF adjacency changes | `RA# grep AdjChg /var/log/frr/frr.log` |
| Packet captures | GNS3: right-click the link, *Start capture*. Save from Wireshark as `TC-xx-<link>.pcapng`. |

All timestamps are UTC: the probe report, `inject-failure.log`, `lab-evidence`, `lab-boot.log` and the FRR logs in the containers. That lets you line up the fault, the OSPF reaction and the traffic loss on one timeline.

## After the run

1. Collect the logs: `VM$ ./scripts/fetch-evidence.sh RUN-2026-10-12`
2. Copy `results/evidence/RUN-2026-10-12/` from the VM to your clone, e.g. `scp -r gns3@<VM IP>:network-failover-test-lab/results/evidence/RUN-2026-10-12 results/evidence/`. Add the `.pcapng` files you saved from Wireshark.
3. For every failed test case, open a GitHub Issue with the *Defect* template and link it in the run report.
4. Commit the run report and the evidence together.

## Useful Wireshark techniques

| Goal | How |
|---|---|
| Show only OSPF Hellos | display filter `ospf.msg == 1` |
| Show only OSPF LS Updates (topology changes) | `ospf.msg == 4` |
| Find the longest gap in ping replies | filter `icmp.type == 0`, then *View → Time Display Format → Seconds Since Previous Displayed Packet*, then sort the *Time* column descending |
| See when the last Hello crossed a link before a failure | filter `ospf.msg == 1`, then look at the last packet's absolute time (*View → Time Display Format → UTC Date and Time of Day*) |
| Confirm no fragmentation | `icmp && ip.len == 1500`, then check the *Don't fragment* flag; `ip.flags.mf == 1` should show nothing |

## Root cause analysis checklist (for failed test cases)

1. **Timeline:** when was the fault injected, when did OSPF react (`AdjChg`), and when did traffic recover?
2. **Which router noticed first, and why?** Carrier loss, or the dead timer expiring?
3. **What did each router believe during the outage?** Use the routing table and neighbour state captured during the outage.
4. **What is the smallest config change that would make the requirement pass?** Apply it, re-run the failed test, then re-run the regression set (TC-01, TC-02, TC-04, TC-07).
