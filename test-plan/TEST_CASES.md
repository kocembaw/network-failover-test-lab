# Test Cases

Twelve manual system test cases, grouped by area. The requirements are in [TEST_PLAN.md](TEST_PLAN.md#3-requirements-under-test).

**Conventions**
- `A1$` is the console of host A1, and `RA#` is the *auxiliary* console of router RA.
- `VM$` is the shell on the machine where the lab containers run (the GNS3 VM), in the repository folder.
- Run every probe on A1 against B1 (`10.2.10.10`) unless a step says otherwise.
- Save evidence under `results/evidence/<run-id>/`. Name files `TC-xx-<what>`, e.g. `TC-07-probe.log` or `TC-07-RA.txt`.
- Fill in **Actual result** and **Status** (Pass / Fail / Blocked) in the run report for each execution. Do not edit the expected results to match what happened.

## Summary

| ID | Title | Area | Req | Priority |
|---|---|---|---|---|
| TC-01 | OSPF adjacencies are established on both WAN links | Connectivity | REQ-01 | High |
| TC-02 | Primary WAN link is preferred | Connectivity | REQ-02 | High |
| TC-03 | Inter-VLAN routing within a site | Connectivity | REQ-01 | Medium |
| TC-04 | End-to-end connectivity between sites | Connectivity | REQ-01, REQ-02 | High |
| TC-05 | 1500-byte packets cross the WAN without fragmentation | Connectivity | REQ-07 | Medium |
| TC-06 | OSPF is not sent on user VLANs | Connectivity | REQ-08 | Medium |
| TC-07 | Failover after primary link loss of carrier | Failover | REQ-03 | High |
| TC-08 | Failover after silent primary link failure | Failover | REQ-03 | High |
| TC-09 | Established TCP session survives failover | Failover | REQ-04 | High |
| TC-10 | Hosts are notified when no path exists | Failover | REQ-06 | Medium |
| TC-11 | Traffic returns to the primary link after restoration | Recovery | REQ-05 | High |
| TC-12 | Site router recovers after reboot without manual steps | Recovery | REQ-09 | High |

---

## Connectivity

### TC-01: OSPF adjacencies are established on both WAN links

**Requirement:** REQ-01 · **Priority:** High

**Preconditions:** All nodes started at least 60 s ago.

**Steps**
1. Start a Wireshark capture on the RA–RB primary link (right-click the link, then *Start capture*). Use the display filter `ospf.msg == 1`.
2. `RA# vtysh -c "show ip ospf neighbor"`
3. `RB# vtysh -c "show ip ospf neighbor"`
4. In Wireshark, open one Hello from each router and note the *Hello Interval* and *Router Dead Interval*.
5. `RA# lab-evidence TC-01` and `RB# lab-evidence TC-01`. Save the output.

**Expected result**
- RA lists neighbour `10.0.0.2` twice, in state `Full/-`, on `eth1` and on `eth2`.
- RB lists neighbour `10.0.0.1` twice, in state `Full/-`, on `eth1` and on `eth2`.
- Hellos from both routers are seen. Hello and Dead intervals are equal on both sides.

---

### TC-02: Primary WAN link is preferred

**Requirement:** REQ-02 · **Priority:** High

**Preconditions:** TC-01 passed.

**Steps**
1. `RA# vtysh -c "show ip route ospf"`
2. `RB# vtysh -c "show ip route ospf"`

**Expected result**
- On RA, `10.2.10.0/24` and `10.2.20.0/24` are selected (`>*`) via `10.255.1.2, eth1`.
- On RB, `10.1.10.0/24` and `10.1.20.0/24` are selected via `10.255.1.1, eth1`.
- No route to a remote site is selected via `eth2`.

---

### TC-03: Inter-VLAN routing within a site

**Requirement:** REQ-01 · **Priority:** Medium

**Preconditions:** TC-01 passed.

**Steps**
1. `A1$ ping -c 5 10.1.20.10`
2. `A1$ traceroute -n 10.1.20.10`
3. `B1$ ping -c 5 10.2.20.10`

**Expected result**
- 0% packet loss in steps 1 and 3.
- Traceroute shows exactly two hops: `10.1.10.1` (RA, VLAN 10 gateway), then `10.1.20.10`.

---

### TC-04: End-to-end connectivity between sites

**Requirement:** REQ-01, REQ-02 · **Priority:** High

**Preconditions:** TC-01 passed.

**Steps**
1. `A1$ ping -c 5 10.2.10.10` and `A1$ ping -c 5 10.2.20.10`
2. `A2$ ping -c 5 10.2.10.10` and `A2$ ping -c 5 10.2.20.10`
3. `A1$ traceroute -n 10.2.10.10`

**Expected result**
- 0% packet loss for all four host pairs.
- Traceroute path: `10.1.10.1` → `10.255.1.2` (RB over the primary link) → `10.2.10.10`.

---

### TC-05: 1500-byte packets cross the WAN without fragmentation

**Requirement:** REQ-07 · **Priority:** Medium · **Technique:** boundary value analysis

**Preconditions:** TC-04 passed.

**Steps**
1. Start a Wireshark capture on the RA–RB primary link.
2. `A1$ ping -c 3 -M do -s 1472 10.2.10.10`. This sends 1472 B of data + 8 B ICMP + 20 B IP = 1500 B, with Don't Fragment set.
3. `A1$ ping -c 3 -M do -s 1473 10.2.10.10`. This is one byte over the limit.
4. In Wireshark, filter `icmp && ip.len == 1500` and inspect one request.

**Expected result**
- Step 2: 0% packet loss.
- Step 3: no packet is sent, and ping reports `message too long, mtu=1500`.
- Step 4: requests are captured with `Total Length: 1500`, the *Don't fragment* flag set, and no IP fragments.

---

### TC-06: OSPF is not sent on user VLANs

**Requirement:** REQ-08 · **Priority:** Medium

**Preconditions:** TC-01 passed.

**Steps**
1. Start Wireshark captures on the SW-A ↔ A1 link and on the SW-B ↔ B1 link. Use the display filter `ospf`.
2. Wait at least 60 s, which is six Hello intervals.
3. As a control, check that the TC-01 capture on the primary WAN link shows OSPF packets during the same time.

**Expected result**
- 0 OSPF packets on both host links.
- OSPF Hellos keep appearing on the WAN link (the control).

---

## Failover

### TC-07: Failover after primary link loss of carrier

**Requirement:** REQ-03 · **Priority:** High

**Preconditions:** TC-02 and TC-04 passed. No failure active (`VM$ ./scripts/inject-failure.sh status`).

**Steps**
1. `A1$ failover-probe run 10.2.10.10 --duration 60 --max-outage 5 --quiet --log /root/TC-07-probe.log`
2. After about 10 s: `VM$ ./scripts/inject-failure.sh hard`
3. When the probe finishes: `RA# lab-evidence TC-07-after` and `RB# lab-evidence TC-07-after`
4. `A1$ traceroute -n 10.2.10.10`
5. `VM$ ./scripts/inject-failure.sh restore`

**Expected result**
- The probe reports a longest outage of ≤ 5 s (`Threshold: 5.0 s -> WITHIN`).
- Traceroute goes via `10.255.2.2` (the backup link).
- RA and RB each show one `Full` neighbour, on `eth2`.

---

### TC-08: Failover after silent primary link failure

**Requirement:** REQ-03 · **Priority:** High

**Preconditions:** TC-07 passed. Wait 60 s after its restore step.

**Steps**
1. Start Wireshark captures on both WAN links (filter `ospf`).
2. `A1$ failover-probe run 10.2.10.10 --duration 90 --max-outage 5 --quiet --log /root/TC-08-probe.log`
3. After about 10 s: `VM$ ./scripts/inject-failure.sh silent`. Alternatively, right-click the primary link in GNS3 and choose *Suspend*, noting the time.
4. Within 5 s of step 3:
   - `RA# ip -br link show eth1`
   - `RA# vtysh -c "show ip ospf neighbor"`
5. When the probe finishes: `RA# lab-evidence TC-08-after`, then `RA# grep AdjChg /var/log/frr/frr.log | tail`
6. `A1$ traceroute -n 10.2.10.10`
7. `VM$ ./scripts/inject-failure.sh restore` (or *Resume* the link).

**Expected result**
- Step 4: `eth1` is still `UP`, which confirms the failure is silent.
- The probe reports a longest outage of ≤ 5 s.
- After failover, traceroute goes via `10.255.2.2`.

---

### TC-09: Established TCP session survives failover

**Requirement:** REQ-04 · **Priority:** High

**Preconditions:** TC-07 passed. No failure active.

**Steps**
1. `B1$ iperf3 -s -1`
2. `A1$ iperf3 -c 10.2.10.10 -t 60 -i 1 | tee /root/TC-09-iperf.log`
3. About 20 s into the transfer: `VM$ ./scripts/inject-failure.sh hard`
4. After iperf3 finishes: `VM$ ./scripts/inject-failure.sh restore`

**Expected result**
- iperf3 runs the full 60 s and ends with `iperf Done.`.
- There is no `Connection reset` or other error.
- Per-second throughput dips at most around the failure, then recovers.

---

### TC-10: Hosts are notified when no path exists

**Requirement:** REQ-06 · **Priority:** Medium · **Type:** negative test

**Preconditions:** No failure active.

**Steps**
1. `A1$ failover-probe run 10.2.10.10 --duration 30 --log /root/TC-10-probe.log`
2. After about 10 s: `VM$ ./scripts/inject-failure.sh isolate`
3. `A1$ traceroute -n 10.2.10.10`
4. `RA# vtysh -c "show ip route 10.2.10.10"`
5. `VM$ ./scripts/inject-failure.sh restore`

**Expected result**
- The probe report lists `ICMP errors received`, with `From 10.1.10.1: Destination Net Unreachable`.
- The first error arrives within 1 s of the injection time in `inject-failure.log`.
- Traceroute stops at `10.1.10.1` with `!N`, and no routing loop (TTL exceeded) occurs.
- RA has no route to `10.2.10.0/24`.

---

## Recovery

### TC-11: Traffic returns to the primary link after restoration

**Requirement:** REQ-05 · **Priority:** High

**Preconditions:** TC-07 passed.

**Steps**
1. `VM$ ./scripts/inject-failure.sh hard`. Wait 30 s and confirm with traceroute that traffic uses `10.255.2.2`.
2. `A1$ failover-probe run 10.2.10.10 --duration 90 --max-outage 1 --quiet --log /root/TC-11-probe.log`
3. After about 10 s: `VM$ ./scripts/inject-failure.sh restore`
4. When the probe finishes:
   - `RA# grep AdjChg /var/log/frr/frr.log | tail`
   - `RA# vtysh -c "show ip route ospf"`
5. `A1$ traceroute -n 10.2.10.10`

**Expected result**
- The neighbour on `eth1` reaches `Full` within 60 s of the restore time. Compare the `-> Full` log line with `inject-failure.log`.
- Remote routes are selected via `10.255.1.2, eth1` again, and traceroute goes via `10.255.1.2`.
- The probe reports a longest outage of ≤ 1 s.

---

### TC-12: Site router recovers after reboot without manual steps

**Requirement:** REQ-09 · **Priority:** High

**Preconditions:** TC-01 passed. `/etc/frr` is a persistent directory in the router template (see the setup guide).

**Steps**
1. `RB# vtysh -c "show running-config"`. Save it as `TC-12-RB-before.txt`.
2. `A1$ failover-probe run 10.2.10.10 --duration 240 --log /root/TC-12-probe.log`
3. After about 10 s, stop RB in GNS3 (right-click, *Stop*). Wait 30 s, then *Start* it.
4. After the probe finishes:
   - `RB# tail -n 1 /var/log/lab-boot.log` gives the router start time (UTC).
   - `RB# vtysh -c "show ip ospf neighbor"`
   - `RB# vtysh -c "show running-config"`. Save it as `TC-12-RB-after.txt`.
5. Compare the two configs: `diff TC-12-RB-before.txt TC-12-RB-after.txt`

**Expected result**
- The last outage in the probe report ends ≤ 120 s after the router start time on RB.
- RB shows `Full` neighbours on `eth1` and `eth2`.
- The running config is identical before and after the reboot, and no commands were typed on RB.
