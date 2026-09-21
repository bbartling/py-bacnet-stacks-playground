# Day 36 — A bounded binary codec

[Previous: Day 35](day35.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 37](day37.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–35, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Encode and decode a small teaching format with explicit length and byte order.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day36/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Binary fields describe bits, not Rust memory layout. Network byte order generally means big-endian where specified; protocol rules always win. A declared length is untrusted input. Check available bytes and arithmetic before creating slices or allocating. A successful round trip proves internal agreement, so also compare a manually specified known-answer fixture.

## Tiny example

```rust
fn main() {
    let field = u16::from_be_bytes([0x12, 0x34]);
    println!("decimal={field}, wire={:02x?}", field.to_be_bytes());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement the teaching codec in [WIRE_FORMATS.md](WIRE_FORMATS.md#teaching-envelope): version, kind, payload length and opaque bytes. The header is four bytes and payload length excludes it.
- Support only version 1, kinds 1 and 2, and payloads up to 256 bytes. Reject trailing bytes for the single-message decoder.
- Return a typed invalid/truncated/unsupported outcome; do not use struct transmutation or unsafe pointer casts.

## Experiment

Use fixture bytes for a valid message, then truncate at every byte position and mutate the length field. Decide whether each case is incomplete or invalid under a complete-datagram contract.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Known-answer encoding matches the documented bytes.
- Length zero and maximum length have tests.
- An unsupported version does not decode as a valid message.

## Optional Python companion

Use struct.pack/unpack to independently produce a header, without implementing the Rust decoder for it.

## Stretch and reflection

How would a streaming decoder distinguish “need more data” from final truncated input?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 35](day35.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 37](day37.md)
