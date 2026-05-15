# Deploy to Raspberry Pi (`ben@192.168.204.12`)

Inventory defaults live in `inventory.yml` (`ansible_host`, `ansible_user`). Adjust `ansible_user` if your Pi login differs.

From this directory:

```bash
ansible-playbook deploy.yml
```

If Ansible is not installed globally, use the repo-local helper venv (created once):

```bash
cd "$(dirname "$0")/.."   # vibe_code_apps_12
python3 -m venv .ansible_venv
.ansible_venv/bin/pip install -q ansible-core
cd ansible
ansible-playbook deploy.yml
```

SSH should use **SSH keys** (recommended). Quick check:

```bash
ssh ben@192.168.204.12 exit
```

### Password SSH (temporary only)

Prefer **never** committing or pasting passwords into Ansible files.

For a one-shot deploy using your account password interactively:

```bash
ansible-playbook deploy.yml --ask-become-pass
```

If **SSH** is password-based too (no key yet), use:

```bash
ansible-playbook deploy.yml --ask-pass --ask-become-pass
```

`--ask-pass` prompts for SSH; `--ask-become-pass` prompts for `sudo` on the Pi (the playbook installs packages and systemd units).

After the first successful run, install a key so you can drop prompts:

```bash
ssh-copy-id ben@192.168.204.12
```

## Verify on the Pi

After a successful playbook:

```bash
ssh ben@192.168.204.12 'systemctl is-active bacnet-ds18b20'
ssh ben@192.168.204.12 'journalctl -u bacnet-ds18b20 -n 25 --no-pager'
```
