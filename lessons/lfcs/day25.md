## Day 25 – Virtual machines (libvirt)

*LFCS · Operations Deployment*

### Goal

Use libvirt basics (virsh) — on Pi may be limited; know commands.

### Concept

```bash
# on a host with libvirt:
virsh list --all
virsh dominfo <name>
virsh start <name>
virsh shutdown <name>
```

On a Pi 5 you might use libvirt with care; on exam expect **virsh** fluency.

### Why This Matters

Admins manage VMs from CLI.

### Mini examples

- virt-install overview
- storage pools concept

### Micro exercises

1. List virsh commands from `virsh help`
2. Document start/shutdown
3. Note: practice on a PC/VM if Pi lacks hypervisor

### Key takeaway

list → start → console → shutdown.
