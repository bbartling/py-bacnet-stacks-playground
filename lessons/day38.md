# Day 38 – Troubleshooting BACnet with Wireshark

## Goal

Learn how to capture and analyse BACnet/IP traffic using `tcpdump` and
Wireshark.  You will run a simple capture script while interacting with
the mini devices from Days 36 and 37, open the resulting PCAP file in
Wireshark, and apply filters to isolate BACnet messages.  This exercise
will help you troubleshoot network issues and verify that your
applications behave as expected.

## Concept

Because BACnet/IP runs over UDP and uses a fixed port (47808)【875468702266391†L28-L30】,
you can capture all BACnet traffic by filtering on that port.  The
Wireshark protocol guide notes that you cannot directly filter on
BACnet while capturing; instead, “capture only the BACnet/IP traffic
over the default port (47808)”【875468702266391†L75-L80】.  Tools like
`tcpdump` or Wireshark’s built‑in capture can write packet capture
files (PCAP) that you can examine later.  Analysing captures helps
diagnose network problems, verify message flow and identify port
conflicts.

## How to Use It

1. **Capture on Linux using tcpdump** – The repository includes a
   helper script `capture_bacnet_pingpong.sh` that wraps `tcpdump`.  To
   capture 60 seconds of BACnet traffic on interface `eth0`:
   ```bash
   sudo bash capture_bacnet_pingpong.sh eth0 60
   ```
   The script saves a PCAP file in the `pcaps/` directory and prints
   the filename.  It uses `tcpdump -i <iface> udp port 47808` to
   capture only BACnet traffic【875468702266391†L75-L80】.

2. **Capture on Windows or macOS with Wireshark** – Install
   [Wireshark](https://www.wireshark.org/) and select the network
   interface connected to your BACnet devices.  Start a capture and
   apply a **display filter** of `bacnet` or `udp.port == 47808` to
   show only BACnet packets.  You can also set a **capture filter**
   `udp port 47808` before starting to limit captured data.

3. **Generate traffic** – While capturing, run your mini device from
   Day 36 and interact with it using your control script, or read the
   schedule from Day 37.  This will generate `ReadProperty` and
   `WriteProperty` messages on the network.  If you are using a
   schedule device, note that the mirror BV updates every few seconds,
   producing regular BACnet traffic.

4. **Analyse the PCAP file** – Open the `.pcap` file in Wireshark.
   Expand the BACnet layer to inspect APDUs (application protocol data
   units).  You should see `Who‑Is`/`I‑Am` messages during device
   discovery, followed by `ReadProperty` and `WriteProperty` requests
   and acknowledgements.  Verify that messages originate from your
   client and target your mini device’s address.  If you see unexpected
   broadcasts (e.g., frequent `Who‑Is` spam), adjust your client code.

## Why This Matters

Network issues are a common source of frustration in building
automation.  Being able to capture and inspect BACnet/IP traffic
quickly reveals misconfigured ports, devices that fail to respond and
incorrect message sequences.  Knowing how to filter on the BACnet
default port【875468702266391†L75-L80】 helps you isolate relevant traffic in
Wireshark.  By analysing PCAP files you can verify that your control
algorithms are sending the expected requests and that the mini devices
respond correctly.

## Mini Examples

* Capture while your control script from Day 36 is running.  Open the
  PCAP and count the number of `WriteProperty` requests.  Do they
  correspond to your control loop’s interval?
* Use Wireshark’s “Follow UDP Stream” feature to view the entire
  conversation between your client and the mini device.
* Apply a display filter of `bacnet.apdu.service == 12` to show only
  `ReadProperty` services.

## Micro Exercises

1. Use `capture_bacnet_pingpong.sh` to capture traffic while both
   mini devices (Day 36 and Day 37) are running simultaneously.  How
   does the traffic differ between the two devices?
2. On Windows, start a Wireshark capture with the display filter
   `bacnet`.  Interact with the schedule device and identify the
   property values being read.
3. Experiment with an incorrect port filter (e.g., `udp port 47809`).
   Does any traffic appear?  Why or why not?
4. Research how to enable **promiscuous mode** on your network
   interface and explain why it might be necessary for capturing
   broadcast packets.

## Key Takeaway

Wireshark and tcpdump are invaluable tools for diagnosing BACnet/IP
networks.  Capture traffic on UDP port 47808【875468702266391†L75-L80】 to
isolate BACnet messages, then analyse the packets to verify that
devices and clients are communicating correctly.  Troubleshooting
network issues early saves time and prevents subtle bugs in your
control algorithms.
