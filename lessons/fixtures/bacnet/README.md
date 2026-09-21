# Synthetic BACnet fixtures and model events

[Public contracts](../../WIRE_FORMATS.md) · [Day 71](../../day71.md)

Hex files are manually specified **synthetic bytes**, not captured successful transactions:

- `who-is.hex`: complete classic BACnet/IP Original-Broadcast-NPDU, BVLC length 8, NPDU version 1/control 0, unconfirmed Who-Is with no optional range.
- `i-am.hex`: complete Original-Unicast-NPDU, length 20, unconfirmed I-Am: Device instance 123, maximum APDU 1476, no segmentation (enumeration 3), vendor identifier 15. These are fixture values, not an advertisement of an actual device or supported product.
- `who-is-router-npdu.hex`: NPDU bytes **without BVLC**, network-message flag set, Who-Is-Router-To-Network without the optional destination-network parameter. Do not feed it to a whole-datagram decoder.

Validate fields against the selected standard/independent decoder when extending the corpus. Real ReadProperty, segmentation and MS/TP evidence must be captured from an appropriate peer or sourced from pinned upstream tests with provenance. No real MS/TP capture is shipped or claimed here.

`segments.csv` belongs only to the Day 81 teaching model. Start from a continuation snapshot expecting sequence 254 for peer-a/invoke 7, deadline 100 ms. Accepted payload is hex `41 42 43`; time 15 is a duplicate, time 20 is wrong context, and time 40 occurs after completion. This is not an assertion that a new BACnet transfer starts at 254. Additional missing, oversized and expired cases are student-generated test inputs.
