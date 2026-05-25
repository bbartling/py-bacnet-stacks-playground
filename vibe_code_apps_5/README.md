Here’s a clean `README.md` you can drop next to `discover_basrtb_mstp.py`.

````markdown
# BACpypes3 MS/TP Discovery Through BASRT-B Router

This script uses **BACpypes3** to discover BACnet devices on an **MS/TP trunk** through a **BACnet/IP-to-MS/TP router**, such as a Contemporary Controls BASRT-B.

The script does **not** talk directly to RS-485/MS/TP from the computer. Instead, it sends a BACnet `Who-Is` request over BACnet/IP to the router, and the router forwards the request to the MS/TP network.

Example network:

```text
Laptop / PC
192.168.204.18/24
        |
        | BACnet/IP
        |
BASRT-B Router
192.168.204.200
        |
        | MS/TP Network 2000
        |
MS/TP Device
MAC Address 7
Device Instance 5007
````

Example discovered device address:

```text
2000:7@192.168.204.200
```

This means:

```text
2000              BACnet MS/TP network number
7                 MS/TP MAC address
192.168.204.200   BACnet/IP router address
```

---

## Install

```bash
pip install bacpypes3
```

---

## Example Command

```bash
python discover_basrtb_mstp.py \
  --address 192.168.204.18/24 \
  --network 1 \
  --instance 599999 \
  --route-aware \
  --router-ip 192.168.204.200 \
  --mstp-net 2000 \
  --timeout 15
```

Windows PowerShell version:

```powershell
python discover_basrtb_mstp.py `
  --address 192.168.204.18/24 `
  --network 1 `
  --instance 599999 `
  --route-aware `
  --router-ip 192.168.204.200 `
  --mstp-net 2000 `
  --timeout 15
```

---

# Arguments

## `--address`

Example:

```bash
--address 192.168.204.18/24
```

This is the **local IP address of your laptop, Raspberry Pi, or computer running the script**.

Do **not** use the router IP here.

Use the IP address of the machine running Python.

Example:

```text
Laptop IP:       192.168.204.18
Subnet:          /24
BACpypes3 arg:   --address 192.168.204.18/24
```

The `/24` means the subnet mask is:

```text
255.255.255.0
```

---

## `--network`

Example:

```bash
--network 1
```

This is the BACnet network number for the **BACnet/IP side** of your BACnet setup.

In the BASRT-B web page, this matches:

```text
BACnet/IP Network: 1
```

This tells BACpypes3 what BACnet network your local BACnet/IP interface is on.

---

## `--instance`

Example:

```bash
--instance 599999
```

This is the **temporary BACnet device instance** used by your Python BACpypes3 application.

Your Python script acts like a BACnet device while it is running, so it needs its own unique device instance.

Use something high and unique to avoid conflicts.

Good example:

```text
599999
```

Avoid using:

```text
0
5007
```

Because your BASRT-B router is using instance `0`, and your discovered MS/TP device is using instance `5007`.

Duplicate BACnet device instances can cause weird discovery behavior.

---

## `--route-aware`

Example:

```bash
--route-aware
```

This tells BACpypes3 that it should handle routed BACnet addresses.

This is important because the MS/TP device is not directly on the BACnet/IP network. It is behind the BASRT-B router.

Without route-aware addressing, BACpypes3 may not correctly understand addresses like:

```text
2000:7@192.168.204.200
```

---

## `--router-ip`

Example:

```bash
--router-ip 192.168.204.200
```

This is the **BACnet/IP address of the BASRT-B router**.

From the router configuration page:

```text
IP Address: 192.168.204.200
```

The script uses this router as the path to reach the MS/TP trunk.

---

## `--mstp-net`

Example:

```bash
--mstp-net 2000
```

This is the BACnet network number for the **MS/TP trunk** behind the router.

From the BASRT-B configuration page:

```text
MS/TP Network: 2000
```

The script sends a remote BACnet broadcast to:

```text
2000:*@192.168.204.200
```

That means:

```text
Send Who-Is to all devices on MS/TP network 2000 through router 192.168.204.200
```

---

## `--timeout`

Example:

```bash
--timeout 15
```

This is how many seconds the script waits for `I-Am` responses after sending `Who-Is`.

MS/TP is slower than BACnet/IP, so a longer timeout is helpful.

Recommended values:

```text
5 seconds      Fast IP networks only
10 seconds     Small MS/TP trunks
15 seconds     Good default for MS/TP discovery
30 seconds     Larger or slower MS/TP trunks
```

For your bench test, this worked:

```bash
--timeout 15
```

---

## `--low-limit`

Example:

```bash
--low-limit 5000
```

Optional.

This limits discovery to BACnet device instances greater than or equal to this number.

For example:

```bash
--low-limit 5000 --high-limit 5010
```

This discovers only devices from:

```text
device,5000 through device,5010
```

If omitted, the default is:

```text
0
```

---

## `--high-limit`

Example:

```bash
--high-limit 5010
```

Optional.

This limits discovery to BACnet device instances less than or equal to this number.

If omitted, the default is:

```text
4194303
```

That is the maximum valid BACnet device instance number.

---

## `--local-too`

Example:

```bash
--local-too
```

Optional.

This also performs a normal local BACnet/IP broadcast on the IP network.

Use this if you want to discover:

```text
BACnet/IP devices on the local subnet
AND
MS/TP devices behind the router
```

Without this flag, the script focuses on the MS/TP trunk behind the BASRT-B.

---

# Example Output

```text
Discovering MS/TP devices at: 2000:*@192.168.204.200

Found 1 device(s)
--------------------------------------------------------------------------------
Device Instance: 5007
BACnet Address:  2000:7@192.168.204.200
Object ID:       device,5007
Object Name:     BENS BENCHTEST BOX
Description:     CTRL 6UI, 2BI, 3BO, 2AO, 4CO
Vendor ID:       5
Max APDU:        480
Segmentation:    segmented-both
--------------------------------------------------------------------------------
```

---

# How to Read the Output

## `Device Instance`

```text
Device Instance: 5007
```

This is the BACnet device object instance number.

The full BACnet object identifier is:

```text
device,5007
```

---

## `BACnet Address`

```text
BACnet Address: 2000:7@192.168.204.200
```

This is the routed BACnet address.

Breakdown:

```text
2000              MS/TP network number
7                 MS/TP MAC address
192.168.204.200   BASRT-B router IP address
```

So this device is:

```text
MS/TP MAC 7 on BACnet network 2000, reachable through router 192.168.204.200
```

---

## `Object Name`

```text
Object Name: BENS BENCHTEST BOX
```

This is the BACnet `objectName` property from the device object.

---

## `Description`

```text
Description: CTRL 6UI, 2BI, 3BO, 2AO, 4CO
```

This is the BACnet `description` property from the device object.

---

## `Vendor ID`

```text
Vendor ID: 5
```

This is the BACnet vendor identifier.

Vendor ID `5` is Johnson Controls.

---

## `Max APDU`

```text
Max APDU: 480
```

This is the largest APDU size the device says it can accept.

For MS/TP devices, this is often smaller than BACnet/IP devices.

---

## `Segmentation`

```text
Segmentation: segmented-both
```

This describes whether the device supports BACnet message segmentation.

Possible values may include:

```text
no-segmentation
segmented-transmit
segmented-receive
segmented-both
```

---

# Working BASRT-B Example

For this BASRT-B configuration:

```text
Router IP Address:       192.168.204.200
BACnet/IP Network:       1
BACnet/IP UDP Port:      BAC0 / 47808
MS/TP Network:           2000
MS/TP Baudrate:          38400
```

And this laptop:

```text
Laptop IP Address:       192.168.204.18
Subnet:                  255.255.255.0
```

Use:

```bash
python discover_basrtb_mstp.py \
  --address 192.168.204.18/24 \
  --network 1 \
  --instance 599999 \
  --route-aware \
  --router-ip 192.168.204.200 \
  --mstp-net 2000 \
  --timeout 15
```

---

# Troubleshooting

## No devices found

Check that:

```text
The laptop can ping the router IP
The BASRT-B IP address is correct
The MS/TP network number is correct
The baud rate matches the MS/TP trunk
The MS/TP polarity is correct
The MS/TP device has power
The MS/TP MAC address is valid
The MS/TP trunk has proper termination
```

Try a longer timeout:

```bash
--timeout 30
```

---

## Router is found but MS/TP devices are not

Check the BASRT-B MS/TP settings:

```text
MS/TP Network
MS/TP Baudrate
Max Masters
MS/TP MAC
MS/TP wiring polarity
Termination
Biasing
```

For a normal MS/TP trunk, `Max Masters` is often set to `127`.

---

## Duplicate device instance problems

Every BACnet device should have a unique device instance.

If your router is:

```text
device,0
```

And your Python script also uses:

```bash
--instance 0
```

That is a problem.

Use a unique testing instance instead:

```bash
--instance 599999
```

---

# Quick Mental Model

BACnet/IP local broadcast:

```text
*
```

Remote MS/TP broadcast through a BACnet router:

```text
2000:*@192.168.204.200
```

Specific MS/TP device through router:

```text
2000:7@192.168.204.200
```

Meaning:

```text
Network 2000
MS/TP MAC 7
Via router 192.168.204.200
```
