# Course validation and lab status

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md)

The 112 lesson plans are authored. Their exercises require the learner to implement solutions; this rewrite does not claim those future programs have passed tests.

## Offline checks

Run from the repository root:

```bash
python3 lessons/lab-scripts/validate_course.py --rust-examples
bash -n lessons/lab-scripts/capture_pcap.sh
git diff --check
```

The course checker verifies consecutive day files, lesson/review headings, review code-fence absence, local links/anchors, index numbering and public fixture hashes. It compiles complete standard-library Rust snippets in temporary files and runs non-network examples. Socket-binding and resolver examples are compiled only. It does not install dependencies, open sockets, touch hardware or solve the challenges.

Authoring validation used Rust/Cargo **1.98.1**, Python 3 and Linux. The destination appliance keeps its own pinned toolchain. Additional checks inspect the synthetic capture with tcpdump and exercise the capture helper with fake commands so no real capture or privilege change is needed. Validation results on 2026-09-21:

- **112** consecutive lesson files and **16** review briefs passed structural checks.
- **1,424** active-course local links/anchors and **19** public data-fixture hashes passed.
- **26** complete standard-library Rust mini-examples compiled; **24** non-network examples ran successfully. The UDP bind and resolver examples were compile-checked only.
- tcpdump decoded all four synthetic Ethernet records; all three UDP checksums and the TCP checksum were reported valid.
- Modbus MBAP lengths/RTU CRC, BACnet BVLC lengths and DHCP fixed fields passed offline checks.
- **9** capture-helper control/input cases passed with fake sudo/timeout/tcpdump commands. No privilege change or live capture occurred.
- The capture shell script passed `bash -n`; tracked changes passed `git diff --check`.

These checks validate authored material and helper behavior, not future student solutions or physical lab outcomes.

## Live labs still require learner evidence

| Area | Status of this course rewrite |
| --- | --- |
| Standard-library mini examples | Offline compile/run check, excluding execution of socket/resolver examples |
| Synthetic packet/hex fixtures | Offline data and decoder checks; no live exchange claimed |
| Student challenge implementations | Intentionally not supplied or executed |
| Tokio, protocol library and independent-peer integrations | Lesson contracts/reference guidance; learner-run against recorded dependencies |
| Namespace routing and firewall experiments | Authored recipe; not applied to the host |
| Pi WAP, leases, reboot and physical NIC behavior | Learner-run hardware labs |
| RTU/MS/TP electrical, token and baud behavior | Learner-run separate bench or labeled recorded fixtures |
| DIY router source, QEMU, exact-image and flashed Pi gates | Follow that repository’s current contracts; not claimed by this rewrite |

No archive of the old day lessons is retained. No full review solutions are present. Existing older capstone examples are explicitly marked optional reference material; they are not the new course's graded implementations.
