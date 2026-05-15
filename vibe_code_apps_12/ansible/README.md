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

SSH must work non-interactively (SSH key loaded). Example check:

```bash
ssh ben@192.168.204.12 exit
```

## Verify on the Pi

After a successful playbook:

```bash
ssh ben@192.168.204.12 'systemctl is-active bacnet-ds18b20'
ssh ben@192.168.204.12 'journalctl -u bacnet-ds18b20 -n 25 --no-pager'
```
