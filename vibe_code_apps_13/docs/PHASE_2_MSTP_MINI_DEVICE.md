# Phase 2 - MS/TP-Only Mini Device

## Objective

Port the application behavior of Rusty's `mini-device-revisited` example from BACnet/IP to native MS/TP. This binary is a BACnet MS/TP device on one USB adapter. It has no BACnet/IP capabilities.

## Upstream source map

Reviewed example:

```text
examples/rust/samples/mini-device-revisited
```

Keep/adapt:

- `ObjectDatabase` construction;
- Device object identity and `object-list`;
- Analog Input 1 simulated/read-only;
- Binary Input 1 simulated/read-only;
- Analog Value 2 commandable/priority array;
- Binary Value 2 commandable/priority array;
- Who-Is/I-Am behavior through the active transport;
- ReadProperty, ReadPropertyMultiple and WriteProperty handling;
- simulation task and clean shutdown;
- structured logging.

Remove completely:

- `NetworkConfig`, NIC detection and subnet broadcast derivation;
- `socket2`, UDP preflight and listener-killing code;
- B/IP MAC encoding and B/IP builder;
- the B/IP client self-check and `discover_probe` UDP binary;
- address, broadcast, UDP port, announcement-over-IP and packet-socket flags;
- any claim that YABE/IP discovery can see this device directly.

## Required source spike

The reviewed server example calls `BACnetServer::bip_builder()`. Before implementing the device:

1. inspect the pinned server construction API;
2. determine whether it can accept `MstpTransport<TokioSerialPort>` generically;
3. if not, add the smallest generic transport constructor/builder while retaining the existing APDU dispatcher and object/service handlers;
4. add a loopback/fake-transport server test before real serial;
5. upstream the transport-generic change if practical.

Do not duplicate the server dispatcher and do not put B/IP inside the device as a shortcut.

## Bench topology

```text
mstp-probe, MAC 0        mstp-mini-device, MAC 1
Waveshare C adapter A    Waveshare C adapter B
          A+ ============== A+
          B- ============== B-
         REF ============== REF
```

Both endpoints are masters. Initial `Max_Master=10` and `Max_Info_Frames=1`.

## Device object model

| Object | Instance | Access | Behavior |
|---|---:|---|---|
| Device | 123001 | Read/required control | Identity and object list |
| Analog Input | 1 | Read-only | Deterministic simulated temperature |
| Binary Input | 1 | Read-only | Deterministic simulated state |
| Analog Value | 2 | Commandable | Priority array, priority 8-16 test |
| Binary Value | 2 | Commandable | Priority array, priority 8-16 test |

Use vendor ID 999 only as a clearly labeled lab placeholder. Standard-frame-only operation uses a maximum compatible with the MS/TP standard-frame path (initially 480 APDU). Segmentation and extended frames are not claimed in Phase 2 unless separately implemented/tested.

## CLI contract

```text
mstp-mini-device \
  --serial /dev/serial/by-id/... \
  --baud 38400 \
  --mac 1 \
  --max-master 10 \
  --max-info-frames 1 \
  --device-instance 123001 \
  --name "Rust MS/TP Mini Device" \
  --vendor-id 999 \
  --log info
```

Accepted baud values are the shared six-value policy; default 38,400. Validate `mac <= max_master <= 127`, `max_info_frames >= 1`, a unique device instance and an existing by-id tty.

Forbidden CLI names include `--address`, `--broadcast`, `--port`, `--interface`, `--bbmd` and `--foreign-device`.

## Test probe

Add `apps/mstp-probe` or a hardware-test binary using adapter A and MAC 0. Its scripted acceptance sequence:

1. allow token discovery to stabilize;
2. Who-Is instance 123001 and verify I-Am;
3. read Device Object_Name and Object_List;
4. read AI:1 and BI:1 Present_Value;
5. RPM several properties;
6. command AV:2 to 75.0 at priority 8 and read back;
7. relinquish priority 8 with BACnet NULL and verify fallback;
8. command/read/relinquish BV:2;
9. request a missing object and verify Object/Unknown_Object;
10. write AI:1 and verify write-access denial;
11. complete 500 repeated reads with invoke/result/latency reporting.

## IP exclusion gate

CI must fail if Phase 2 source or its normal dependency feature set introduces IP transport/socket code. At minimum run a maintained guard such as:

```bash
rg -n "BipTransport|bip_builder|UdpSocket|socket2|DEFAULT_BACNET_PORT|SocketAddr|--address|--broadcast|47808" apps/mstp-mini-device
```

Review dependency features too; absence of a string is not sufficient if B/IP is pulled into the executable by default features.

## Hardware/recovery matrix

- device first/probe second;
- probe first/device second;
- either station becomes sole master and admits the returning station;
- duplicate MAC is clearly diagnosed;
- baud mismatch never yields a false successful transaction;
- USB unplug/replug has a documented fail-fast or reopen policy;
- CPU/log load;
- one-hour standard traffic soak;
- each accepted baud tested if it will be claimed.

## Exit checklist

- [ ] Phase 1 gate passed and its helpers/tests remain green.
- [ ] Device executable contains no B/IP/UDP/IP interface.
- [ ] Two real masters exchange token.
- [ ] Who-Is/I-Am, RP, RPM, WP, priority/relinquish and negative cases pass.
- [ ] Object_List enumerates the Device + four points.
- [ ] Standard-frame/APDU limit is enforced without truncation.
- [ ] Restart and sole-master admission tests pass.
- [ ] 500-read report and one-hour soak pass.
- [ ] Phase 2 behavior is documented as MS/TP-only.

