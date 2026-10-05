# Test Plan: Network Failover Test Lab

## 1. Purpose

Verify that the two-site network keeps inter-site traffic flowing when the primary WAN link fails, and that it recovers on its own when the link or a router comes back. The plan covers connectivity, failover and recovery. All tests are manual and system-level, with simple tools to inject failures and measure outages.

## 2. System under test

| Item | Value |
|---|---|
| Topology | 2 sites, 1 router each (RA, RB), 2 VLANs per site, primary + backup WAN link. See [README](../README.md#topology) |
| Routing | OSPFv2, single area 0. WAN links point-to-point, cost 10 (primary) and 100 (backup). Default timers (Hello 10 s, Dead 40 s) |
| Routers | FRRouting in Docker (`images/router`) |
| Hosts | Alpine Linux in Docker (`images/host`): A1, A2, B1, B2 |
| Emulator | GNS3 with the GNS3 VM |

Record the exact versions for every run in the run report: GNS3, FRR (`vtysh -c "show version"`) and the image IDs.

## 3. Requirements under test

| ID | Requirement |
|---|---|
| REQ-01 | Every host can reach every other host, within its site and across sites. |
| REQ-02 | Inter-site traffic uses the primary WAN link while it is available. |
| REQ-03 | After any failure of the primary WAN link, inter-site traffic is restored over the backup link within **5 s**. |
| REQ-04 | Established TCP sessions survive a WAN failover. |
| REQ-05 | After the primary link is restored, traffic returns to it automatically within **60 s**, losing no more than **1 s** of traffic. |
| REQ-06 | When no path exists between sites, hosts are told so immediately (ICMP Destination Unreachable) instead of traffic being dropped silently. |
| REQ-07 | 1500-byte IP packets are delivered end to end without fragmentation. |
| REQ-08 | Routing protocol traffic is not sent on user VLANs. |
| REQ-09 | A site router recovers full connectivity after a reboot within **120 s**, without manual intervention. |

## 4. Approach

- **Level and type.** System testing of the whole lab, black-box from the hosts' point of view (ping, traceroute, iperf3) plus white-box observation on the routers (OSPF state, routing tables, logs).
- **Failure injection.** `scripts/inject-failure.sh` creates repeatable faults and logs a millisecond timestamp for each one:
  - `hard`: primary link down on both routers (loss of carrier).
  - `silent`: primary link drops all IP traffic while both interfaces stay up, like a faulty carrier switch. GNS3's *Suspend link* is an alternative.
  - `isolate`: both WAN links down.
  - `restore`: clears all of the above.
- **Measurement.** `failover-probe` on host A1 sends a ping every 100 ms to B1 and reports every gap in the replies. Resolution is 0.1 s.
- **Evidence.** For every executed test, keep:
  - the probe log;
  - the router state (`lab-evidence`);
  - a Wireshark capture where the test case asks for one;
  - the `inject-failure.log` entries.

  See [docs/evidence.md](../docs/evidence.md).

## 5. Entry and exit criteria

**Entry**
- Lab built as in [docs/setup-gns3.md](../docs/setup-gns3.md), all nodes running for at least 60 s.
- TC-01 passes. It is the smoke test: without OSPF adjacencies no other test is meaningful.

**Exit**
- All 12 test cases executed and their status recorded in a run report.
- Every failed test case is linked to a defect (GitHub Issue).
- Every fix is verified by re-running the failed test case and the regression set (TC-01, TC-02, TC-04, TC-07).

## 6. Traceability

| Requirement | Test cases |
|---|---|
| REQ-01 | TC-01, TC-03, TC-04 |
| REQ-02 | TC-02, TC-04 |
| REQ-03 | TC-07, TC-08 |
| REQ-04 | TC-09 |
| REQ-05 | TC-11 |
| REQ-06 | TC-10 |
| REQ-07 | TC-05 |
| REQ-08 | TC-06 |
| REQ-09 | TC-12 |

## 7. Defect management

Defects are tracked as GitHub Issues using the *Defect* template (`.github/ISSUE_TEMPLATE/defect.md`).

| Severity | Meaning |
|---|---|
| Critical | Loss of inter-site connectivity with no recovery |
| Major | A requirement is not met, e.g. failover slower than required |
| Minor | Requirement met, but behaviour is suboptimal or poorly observable |

Each defect records the steps to reproduce, the expected and actual results, evidence, root cause analysis, the fix, and the retest result.

## 8. Risks and limitations

- **Emulation, not hardware.** Timings in containers are not representative of production equipment. The results show protocol behaviour, not hardware performance.
- **Silent failures are emulated.** They are produced with packet filtering on the routers (or GNS3 link suspension), not by real faulty equipment.
- **ICMP rate limiting.** Linux rate-limits ICMP error messages, so only some lost probes produce a Destination Unreachable reply.
- **Measurement resolution.** Outage measurement resolution is 0.1 s, and gaps shorter than one probe interval are not visible.
