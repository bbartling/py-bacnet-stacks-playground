# Reproducible network lab topologies

[Lab guide](LAB_GUIDE.md) · [Course index](INDEX.md)

These are learner-run recipes. They were authored and syntax-reviewed, not applied to your host during the rewrite. Use a disposable Linux VM for namespace/firewall work and a dedicated Pi for physical networking. Names and private prefixes below are examples; first check for collisions. Do not change the interface carrying your only management connection.

## Loopback first

Early UDP/TCP labs can use `127.0.0.1:40000` and `127.0.0.1:40001`, or port zero for OS-assigned ports reported by the program. IPv6 uses `[::1]:40000`. Check `ss -lunt` before choosing a fixed port. Run peers in separate terminals and use their bounded shutdown behavior. A bind on loopback is intentionally not reachable from the LAN.

Two BACnet applications should use distinct bind addresses/hosts as required by their stacks. Do not assume two wildcard listeners can safely share UDP 47808. Loopback aliases and same-host broadcast delivery vary; the namespace topology is a better later experiment for interface/broadcast behavior.

## Namespace lab

```text
course-client                 course-router                  course-server
c0 10.203.1.2/24 ---- r0 10.203.1.1/24
                         r1 10.203.2.1/24 ---- s0 10.203.2.2/24
```

This lab has no host uplink attachment. All routes below live inside namespaces. First inspect `ip netns list` and `ip link`; if any course names already exist, stop and choose fresh names rather than deleting unknown resources. Save your host `ip route` output for comparison.

Run each setup command after reviewing it:

```bash
sudo ip netns add course-client
sudo ip netns add course-router
sudo ip netns add course-server
sudo ip link add course-c type veth peer name course-r0
sudo ip link add course-s type veth peer name course-r1
sudo ip link set course-c netns course-client
sudo ip link set course-r0 netns course-router
sudo ip link set course-s netns course-server
sudo ip link set course-r1 netns course-router
sudo ip -n course-client link set course-c name c0
sudo ip -n course-router link set course-r0 name r0
sudo ip -n course-server link set course-s name s0
sudo ip -n course-router link set course-r1 name r1
sudo ip -n course-client link set lo up
sudo ip -n course-router link set lo up
sudo ip -n course-server link set lo up
sudo ip -n course-client address add 10.203.1.2/24 dev c0
sudo ip -n course-router address add 10.203.1.1/24 dev r0
sudo ip -n course-router address add 10.203.2.1/24 dev r1
sudo ip -n course-server address add 10.203.2.2/24 dev s0
sudo ip -n course-client link set c0 up
sudo ip -n course-router link set r0 up
sudo ip -n course-router link set r1 up
sudo ip -n course-server link set s0 up
sudo ip -n course-client route add 10.203.2.0/24 via 10.203.1.1
sudo ip -n course-server route add 10.203.1.0/24 via 10.203.2.1
```

Before IP forwarding is enabled, each endpoint should reach its adjacent router interface. Across-network traffic is the controlled comparison. Enable forwarding **inside the router namespace only**:

```bash
sudo ip netns exec course-router sysctl -w net.ipv4.ip_forward=1
sudo ip netns exec course-client ping -c 3 10.203.2.2
sudo ip -n course-router route
```

The successful ping also depends on actual firewall policy and routes; a failure is evidence to diagnose, not a reason to flush host rules. Capture router `r0` and `r1` separately in bounded foreground commands, for example:

```bash
sudo ip netns exec course-router timeout --signal=INT 15s tcpdump -i r0 -c 100 -s 2048 -w /tmp/course-r0.pcap 'icmp or udp port 40000'
```

Choose a fresh output path before each capture to avoid overwriting evidence. `timeout` commonly returns 124 when it ends the capture by duration. Limit and stop any test peers you start. A Rust program may be launched with `ip netns exec` using its **absolute binary path**. Namespace entry may require privilege; the program itself should run without root where possible, for example via an explicit local user after entering the namespace. Do not use Cargo build scripts as root.

### BACnet version of the topology

Assign BACnet network number 1001 to the router B/IP port on r0 and 2001 to the port on r1. These numbers are not derived from the IPv4 prefixes. Use explicit local broadcasts `10.203.1.255` and `10.203.2.255` where the stack requires them. The client and device live on opposite sides and use the BACnet router's routed addressing.

For a BACnet-routing proof, disable ordinary IP forwarding in course-router and verify that a direct IP request to the remote device fails. The BACnet router process still has local sockets on both interfaces and can forward NPDUs between its ports. This removes an accidental direct IP bypass:

```bash
sudo ip netns exec course-router sysctl -w net.ipv4.ip_forward=0
```

Use the actual pinned stack/repository runbook to start the router and peers; its internal flags may change. Record both interfaces, network numbers and actual process command lines. Do not infer routing merely from a discovery result.

### Small MTU experiment

Inside this disposable topology, an optional learner experiment can reduce both ends of one veth link to the same supported MTU, then restore the original values. First record `ip -n course-router link show r1` and `ip -n course-server link show s0`. Use the recorded values for rollback. Do not apply these changes to a host Ethernet/Wi-Fi uplink. Protocol-specific packet sizes and fragmentation flags determine the expected outcome; write the prediction before running.

### Teardown

Stop the exact peer/router processes you started, using their normal shutdown paths. Inspect remaining owners:

```bash
sudo ip netns pids course-client
sudo ip netns pids course-router
sudo ip netns pids course-server
```

If any are unknown, investigate rather than killing them automatically. Once no processes remain, remove only the three namespaces created for this run:

```bash
sudo ip netns delete course-client
sudo ip netns delete course-router
sudo ip netns delete course-server
```

Recheck host routes and links. If setup failed halfway through, inventory the partially created course resources and remove only those you own; the recipe intentionally has no destructive “reset everything” command.

## Pi pocket router

Baseline: a dedicated Pi with a supported Wi-Fi AP radio, Ethernet uplink, and a recoverable management path. An external AP on a separate wired LAN is a valid alternative. A one-radio Wi-Fi uplink-plus-AP configuration is an extension requiring verified concurrent-mode support.

| Item | Fill in before setup |
| --- | --- |
| Pi model, OS and kernel | Actual installed values |
| Network manager | NetworkManager **or** an intentionally configured alternative |
| Uplink | Interface and existing route/profile |
| LAN/AP | Separate interface with AP support, or dedicated wired LAN |
| LAN prefix | Non-overlapping private prefix, e.g. 192.168.77.0/24 if free |
| Management recovery | Console, separate wired link or verified other path |
| Clients | Two IP-capable clients; record their interfaces |
| Credential | Unique lab credential; do not commit it |

Inspect `nmcli device status`, `nmcli connection show`, `ip route`, and AP support reported by `iw list`. Verify the regulatory country through the OS-supported configuration. The following recipe assumes NetworkManager actually owns the chosen interface and supports shared mode on this OS. Consult [its current property documentation](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html) and the [Pi configuration guide](https://www.raspberrypi.com/documentation/computers/configuration.html). Do not launch a separate hostapd/dnsmasq stack on that interface at the same time.

### NetworkManager AP profile

Replace the interface/prefix after the worksheet. Check that `course-ap` does not already exist. The commands create and modify a profile, so run them only on the dedicated Pi:

```bash
LAB_AP_IF=wlan0
LAB_LAN_CIDR=192.168.77.1/24
nmcli connection add type wifi ifname "$LAB_AP_IF" con-name course-ap autoconnect no ssid RustBench
nmcli connection modify course-ap 802-11-wireless.mode ap
nmcli connection modify course-ap ipv4.method shared ipv4.addresses "$LAB_LAN_CIDR"
nmcli connection modify course-ap ipv6.method disabled
nmcli connection modify course-ap wifi-sec.key-mgmt wpa-psk
nmcli --ask connection up course-ap
```

With NetworkManager permissions/polkit configured, `--ask` prompts for the Wi-Fi secret if required; use an actual unique strong passphrase. Some installations require administrator authorization or a different supported Wi-Fi security configuration. Check the resulting profile and actual AP operation. Do not put a real password into this document or a public shell transcript.

This baseline explicitly disables IPv6 **on the shared profile**, making the first milestone IPv4-only. Later, design a routed IPv6 prefix/RA/firewall experiment separately; do not assume turning on DHCPv6 supplies a default route or that a ULA grants upstream connectivity. Shared-mode DHCP/DNS/NAT implementation details depend on the NetworkManager/OS version: inspect rather than guess them.

For a **separate wired LAN** instead of AP, use an Ethernet profile on the dedicated LAN NIC with `ipv4.method shared` and an explicit non-overlapping address. Do not apply sharing to the uplink. Multiple LAN USB Ethernet NICs can be attached to a deliberately configured bridge if desired; that is an extension with its own loop and interface-ownership checks.

### Verification and recovery

Join two clients. On each, record address, mask/prefix, gateway, DNS server and lease evidence. Query the advertised resolver explicitly. Reach a local Pi service, then an allowed upstream service. Run your Rust TCP proxy on the intended LAN address; verify that management listeners are not accidentally exposed upstream.

Inspect `nmcli connection show --active`, `ss -lunt`, relevant journal logs and `nft list ruleset` as applicable. Do not flush NetworkManager-generated firewall rules. Test uplink loss while preserving LAN connectivity. Once the profile is verified and recovery is available, choose whether to enable autoconnect:

```bash
nmcli connection modify course-ap connection.autoconnect yes
```

Record a controlled reboot test separately. To stop the lab share, use `nmcli connection down course-ap`. To remove it after the experiment, use `nmcli connection delete course-ap` only after confirming it is the profile you created. Restore any previously recorded LAN-side profile if necessary. Keep the uplink/recovery profile untouched.

USB gadget mode requires a supported Pi controller and data port. Ordinary USB hubs, USB RS-485 adapters and non-network peripherals do not become DHCP clients. Validate hardware before buying anything for this extension.
