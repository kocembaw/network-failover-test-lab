# Building the lab in GNS3

This guide takes you from a fresh GNS3 install to a running lab of 8 nodes.

## Requirements

- **GNS3 GUI 2.2.x with the GNS3 VM**, running in VMware Workstation Player, VirtualBox or Hyper-V. On Linux, GNS3 can run Docker locally instead of in the VM.
- **Wireshark** on the machine with the GNS3 GUI. It is used for link captures.
- **Internet access from the GNS3 VM**, to build the images.
- About 1 GB of free RAM in the GNS3 VM. All nodes are containers.

## 1. Build the images on the GNS3 VM

Open a shell on the GNS3 VM. In its console menu choose *Shell*, or connect over SSH: `ssh gns3@<VM IP>`, password `gns3`.

```bash
git clone https://github.com/kocembaw/network-failover-test-lab.git   # sudo apt-get install -y git, if missing
cd network-failover-test-lab
./scripts/build-images.sh
```

You should end up with `lab-router:latest` and `lab-host:latest`. Keep this shell open: you will also use it to run `inject-failure.sh` and `fetch-evidence.sh`.

## 2. Create two Docker templates

In GNS3, go to *Edit → Preferences → Docker containers → New*. Choose *Run this Docker container on the GNS3 VM*, then *Existing image*.

| Setting | lab-router | lab-host |
|---|---|---|
| Image | `lab-router:latest` | `lab-host:latest` |
| Adapters | 3 | 1 |
| Start command | *(leave empty)* | *(leave empty)* |
| Console type | telnet | telnet |
| Auxiliary console type | telnet | *(default)* |
| Persistent directories (*Advanced* tab) | `/etc/frr` | *(none)* |

The `/etc/frr` persistent directory keeps router config across node restarts. TC-12 depends on it.

## 3. Add nodes and name them exactly

Drag the following nodes onto the canvas and rename them **before the first start**. Use these names:

| Node | Template |
|---|---|
| RA, RB | lab-router |
| A1, A2, B1, B2 | lab-host |
| SW-A, SW-B | built-in *Ethernet switch* |

The names matter:
- GNS3 sets the container hostname to the node name.
- The router start script picks its config by hostname.
- `inject-failure.sh` and `fetch-evidence.sh` find containers by hostname.

## 4. Configure the switches

Right-click SW-A, choose *Configure*, and set the first three ports. Repeat for SW-B.

| Port | Type | VLAN | Connects to |
|---|---|---|---|
| 0 | dot1q | 1 | router `eth0` (trunk) |
| 1 | access | 10 | host in VLAN 10 |
| 2 | access | 20 | host in VLAN 20 |

## 5. Cable the topology

| From | To | Purpose |
|---|---|---|
| RA eth0 | SW-A port 0 | Site A trunk |
| A1 eth0 | SW-A port 1 | VLAN 10 |
| A2 eth0 | SW-A port 2 | VLAN 20 |
| RB eth0 | SW-B port 0 | Site B trunk |
| B1 eth0 | SW-B port 1 | VLAN 10 |
| B2 eth0 | SW-B port 2 | VLAN 20 |
| RA eth1 | RB eth1 | WAN primary |
| RA eth2 | RB eth2 | WAN backup |

Tip: add text labels on the canvas for the two WAN links (*primary*, *backup*). The capture steps in the test cases refer to them.

## 6. Give the hosts their addresses

For each host, right-click it, choose *Edit network configuration*, and replace the contents with the matching file from [`configs/hosts/`](../configs/hosts/). For example, A1 gets:

```
auto eth0
iface eth0 inet static
	address 10.1.10.10
	netmask 255.255.255.0
	gateway 10.1.10.1
```

The routers need no manual configuration. On first start, each one creates its VLAN subinterfaces and loads `configs/RA/frr.conf` or `configs/RB/frr.conf`.

## 7. Start and check

Start all nodes and wait about 60 s for OSPF to converge.

**Which console to use**
- **Routers:** right-click the node and choose *Auxiliary console*. That gives you a shell. The main console only shows FRR's own output.
- **Hosts:** double-click the node. The main console is a shell.

Then check:

```
RA# hostname                               -> RA
RA# vtysh -c "show ip ospf neighbor"       -> 10.0.0.2 Full/- on eth1 and on eth2
A1$ ping -c 3 10.2.10.10                   -> 0% packet loss
VM$ ./scripts/inject-failure.sh status     -> both routers found, fault rules: none
```

If all four checks pass, the lab is ready for TC-01.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Router console shows `no profile for 'lab-router-1'` | The node was started before it was renamed. Stop it, rename it to RA/RB, and start it again. Alternatively, set `LAB_ROUTER=RA` in the node's environment variables. |
| `vtysh` says `failed to connect to any daemons` | FRR did not start. Check the node console log for `lab-router:` messages. |
| No OSPF neighbour on one link | Check the cabling (eth1–eth1, eth2–eth2) and that both interfaces are `UP`: `ip -br link`. |
| A1 cannot reach 10.1.10.1 | Check the switch port VLANs, check that RA's `eth0` is on the dot1q port, and check A1's network configuration. |
| `inject-failure.sh: no running container with hostname 'RA'` | Run the script on the GNS3 VM, not on your PC. Make sure the node is named RA, or set `RA_CONTAINER=<container id>`. |
| `Permission denied` when running a script | The executable bit was lost (e.g. the repo was committed from Windows). Run `chmod +x scripts/*.sh` |
| Image build fails on `quay.io/frrouting/frr:10.0.0` | Pick a current tag at quay.io/repository/frrouting/frr and run `FRR_TAG=<tag> ./scripts/build-images.sh`. |
