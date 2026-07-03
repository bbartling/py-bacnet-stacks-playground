## Day 1 – Lab setup & LFCS map

*LFCS · Essential Commands*

### Goal

Boot a Raspberry Pi (or VM), know the exam domains, and verify you can run admin commands.

### Concept

LFCS weights: **Operations 25% · Networking 25% · Storage 20% · Essential Commands 20% · Users/Groups 10%**.

Exam is **performance-based** (do tasks on a live Linux system), not multiple choice.

```bash
uname -a
cat /etc/os-release
whoami
sudo -v
```

### Why This Matters

You need a disposable lab (Pi SD card snapshot or VM snapshot) so mistakes are cheap.

### Mini examples

- Take an SD/VM snapshot named `lfcs-day0`
- List the five exam domains from memory

### Micro exercises

1. Run `uname -r` and note your kernel
2. Create `~/lfcs-lab` and `cd` into it
3. Write one sentence: why snapshots matter

### Key takeaway

Practice on a real shell every day. Reading alone will not pass LFCS.
