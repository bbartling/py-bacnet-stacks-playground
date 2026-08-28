# ANSI/ASHRAE 135-2020 Clause 9 Checklist

Reference: the locally licensed `ASHRAE-bacnet-spec.pdf`, ANSI/ASHRAE Standard 135-2020. Do not copy the PDF into this repository. Verify clause wording against the licensed source before changing a normative claim.

This checklist converts relevant requirements into implementation and test gates. It is not a replacement for the standard or a PICS.

## 9.2 Physical layer

### 9.2.1 Medium

- [ ] Field cable is shielded twisted pair intended for EIA-485.
- [ ] Characteristic impedance is 100-130 ohms for a field installation.
- [ ] Segment topology is daisy-chained with no T connections.
- [ ] Bench documentation distinguishes short lab wire from a compliant field cable claim.

### 9.2.2 Connections, termination and bias

- [ ] Polarity is consistent: plus/non-inverting to plus, minus/inverting to minus.
- [ ] Exactly one 120-ohm +/-5% termination is present at each of the two physical ends.
- [ ] No termination exists at an intermediate node.
- [ ] Power-off A/B resistance is recorded; about 60 ohms is expected from two 120-ohm endpoints in parallel.
- [ ] Network bias is independently verified. The Waveshare's advertised 120-ohm termination is not evidence of bias.
- [ ] At least one and no more than two network-bias sets exist per segment.
- [ ] Any local bias outside the network-bias sets is sufficiently weak according to Clause 9.2.2.
- [ ] Field reference conductors on isolated devices are connected per the permitted three-wire arrangement.
- [ ] Shield is grounded at one point only in a field installation.
- [ ] Any between-building segment has at least 1500 V signal-to-digital-ground isolation plus the required surge/grounding design.

For the two-C-adapter bench, both adapters are endpoints and the C model's 2.5 kV isolation is useful. The product must not assume its fixed onboard termination is appropriate for every installation.

### 9.2.3 UART, rates and direction timing

- [ ] UART is configured as NRZ, one start bit, eight data bits, no parity, one stop bit, least-significant data bit first.
- [ ] 9,600 and 38,400 bps are supported.
- [ ] Optional implemented rates are 19,200, 57,600, 76,800 and 115,200 bps.
- [ ] Rate accuracy and actual adapter support are measured/verified where required.
- [ ] CLI/config rejects unapproved values rather than silently substituting another rate.
- [ ] Hardware auto-direction enables the driver before the first start bit.
- [ ] Hardware auto-direction holds the driver through the final stop bit and releases within the post-drive limit.
- [ ] Receive-to-transmit turnaround is observed.

## 9.3 Frame format

- [ ] Standard preamble is `55 FF`.
- [ ] Header CRC covers frame type, destination, source and length.
- [ ] Standard data frames use the specified data CRC and size boundary.
- [ ] Token/Poll/Reply frame types are handled by masters.
- [ ] Broadcast source is rejected and station addresses are validated.
- [ ] Unknown/reserved/proprietary frame types are handled without parser desynchronization.
- [ ] Parser accepts arbitrary USB read fragmentation and multiple frames per read.
- [ ] Parser bounds memory before allocation/extension.

### Extended MS/TP gate

For 135-2020, routing nodes must support the COBS-encoded BACnet extended data frame types 32 and 33. The reviewed Rust source currently lacks those enum variants and encodes all data with the standard CRC-16 path while allowing up to 1497 bytes.

- [ ] Add types 32/33.
- [ ] Add COBS encoding/decoding.
- [ ] Add CRC-32K generation/verification.
- [ ] Enforce standard and extended length boundaries separately.
- [ ] Add independent golden vectors from current `bacnet-stack` or another conforming implementation.
- [ ] Verify malformed COBS, bad CRC-32K, truncation and maximum-size behavior.
- [ ] Verify real cross-implementation traffic in both directions.
- [ ] Until complete, cap outbound MS/TP APDU/NPDU sizes so oversized standard frames cannot be emitted.

Phase 2 is a non-routing node and may deliberately remain standard-frame-only with an advertised maximum compatible with that choice. Phase 3 cannot claim the same exception.

## 9.5 MS/TP state-machine parameters

Tests must cover at least:

| Parameter | 135-2020 requirement used by this project | Test |
|---|---:|---|
| `Npoll` | 50 token uses | Poll-for-master cadence |
| `Nretry_token` | 1 retry | Missing successor/token recovery |
| `Nmin_octets` | 4 events | Activity detection |
| `Tframe_abort` | 60 bit times minimum; implementation upper bound per clause | Split/truncated/noisy frame at every baud |
| `Tframe_gap` | 20 bit times maximum between transmitted octets | Capture under CPU/USB load |
| `Tno_token` | 500 ms | Initial/returning sole-master behavior |
| `Tpostdrive` | 15 bit times maximum | Logic-analyzer direction release |
| `Treply_delay` | 250 ms maximum | Confirmed request handler response |
| `Treply_timeout` | 255 ms minimum, bounded upper allowance | Missing peer and delayed response |
| `Tslot` | 10 ms | Token generation slot behavior |
| `Tturnaround` | 40 bit times minimum | Receive-to-transmit capture |
| `Tusage_delay` | 15 ms maximum | Token/PFM response start |
| `Tusage_timeout` | 20 ms baseline with allowed implementation ceiling | Token pass acceptance/retry |

The agent must calculate bit-time-derived limits from the selected baud rather than using one microsecond constant for every rate.

## Address and token configuration

- [ ] Phase 2 tester MAC 0 and device MAC 1 are unique.
- [ ] Both are masters and do not exceed Max_Master.
- [ ] Max_Master is <=127.
- [ ] Max_Info_Frames is 1-255 and defaults to 1 for the initial bench.
- [ ] Duplicate-MAC behavior is visible through errors/counters; reliable operation is not claimed.
- [ ] A sole master admits a newly appearing master through Poll For Master.

## Routing-related evidence

- [ ] MS/TP-to-other-LAN and other-LAN-to-MS/TP routing follow Clause 9.7 plus Clause 6 network-layer rules.
- [ ] Router processes Who-Is-Router-To-Network and I-Am-Router-To-Network.
- [ ] Directly connected network numbers are distinct and valid.
- [ ] Hop count is decremented and exhausted packets are dropped.
- [ ] Local, remote and global broadcast forwarding is loop-free.
- [ ] Unknown routes produce the required rejection behavior.
- [ ] Router does not answer Phase 2 application objects.

## Evidence record

Every checked item links to a unit test, integration test, hardware report, capture or decision record. A checkbox without evidence is not a conformance result.

