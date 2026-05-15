# Cheat sheet: SSH password login on Raspberry Pi OS (for Ansible `--ask-pass`)

Use this only **temporarily**. Prefer **SSH keys** (`ssh-copy-id`) and turn password auth **off** again when done.

---

## 1. On the Pi (local keyboard, screen, or existing session)

### Backup and edit sshd config

```bash
sudo cp -a /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d)
sudo nano /etc/ssh/sshd_config
```

### Set or uncomment these lines (Bookworm / common defaults)

```
PasswordAuthentication yes
KbdInteractiveAuthentication yes
```

Optional: keep keys **and** passwords (normal while you migrate):

```
PubkeyAuthentication yes
```

Avoid enabling **root** password login:

```
PermitRootLogin no
```

Save, then test config and restart SSH:

```bash
sudo sshd -t && sudo systemctl restart ssh
```

On some images the unit is `ssh.service`; if `restart ssh` fails:

```bash
sudo systemctl restart sshd
```

---

## 2. From your other machine (sanity check)

```bash
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no ben@192.168.204.12
```

You should get a **password** prompt. Exit with `exit`.

---

## 3. Run Ansible with passwords

From `vibe_code_apps_12/ansible` on a machine that has **Ansible + sshpass** (password over OpenSSH):

```bash
# Debian/Ubuntu: sudo apt install ansible-core sshpass
ansible-playbook deploy.yml --ask-pass --ask-become-pass -v
```

- **`--ask-pass`** → SSH password for `ben`.
- **`--ask-become-pass`** → `sudo` password on the Pi (if `ben` is not passwordless sudo).

If **`ben`** has **passwordless sudo**, you can omit `--ask-become-pass`:

```bash
ansible-playbook deploy.yml --ask-pass -v
```

---

## 4. After deploy: switch back to keys-only (recommended)

### On your laptop / build machine

```bash
ssh-copy-id ben@192.168.204.12
ssh ben@192.168.204.12 exit    # should not ask for password
```

### On the Pi again

```bash
sudo nano /etc/ssh/sshd_config
```

Set:

```
PasswordAuthentication no
```

```bash
sudo sshd -t && sudo systemctl restart ssh
```

---

## 5. Troubleshooting

| Problem | Things to check |
|--------|------------------|
| Still “Permission denied (publickey)” | Client is not offering password: try OpenSSH line in §2; on Pi run `sudo grep -E '^PasswordAuthentication|^KbdInteractiveAuthentication|^#?' /etc/ssh/sshd_config` |
| Ansible never asks for password | Install **`sshpass`**; or use **Paramiko** only if server allows password (**yours did not** until you change sshd). |
| Restart locked you out | Physical/console access: restore `sshd_config.bak.*` or set `PasswordAuthentication yes` from SD card on another PC (extreme). |

---

## 6. Optional: allow only user `ben`

In `sshd_config`:

```
AllowUsers ben
```

Restart `ssh` after editing.
