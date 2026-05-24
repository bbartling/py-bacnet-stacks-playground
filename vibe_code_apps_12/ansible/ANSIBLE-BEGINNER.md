# Ansible beginner guide (this folder’s playbook)

Ansible pushes config and software to remote machines over **SSH**. You write a **playbook** (YAML) that lists **tasks**; each task calls a **module** (`copy`, `apt`, `systemd`, …). Variables come from **`inventory`** and **`group_vars`**.

---

## 0. No `git clone` on the Pi (normal path)

This playbook **`copy`**s files from **your laptop or build server** (next to `deploy.yml`) to the Pi. You edit code here, run **`ansible-playbook deploy.yml`**, and the Pi updates. Use **`git pull`** only on **this** machine so Ansible ships the newest files.

---

| File / folder | Role |
|---------------|------|
| **`ansible.cfg`** | Points Ansible at **`inventory.yml`** so you do not pass `-i` every time. |
| **`inventory.yml`** | **Which hosts** to talk to (`ansible_host`, `ansible_user`). |
| **`group_vars/pi_bcn.yml`** | **Variables** — BACnet defaults; GPIO opt-in (`enable_ds18b20_gpio`). |
| **`deploy.yml`** | Playbook: core + `edge_bacnet` always; GPIO files only when opted in. |
| **`templates/vibe12-bacnet-discover.service.j2`** | BACnet Who-Is → CSV (default). |
| **`templates/vibe12-bacnet-read.service.j2`** | BACnet RPM scrape → AWS IoT (installed by default). |
| **`templates/bacnet-ds18b20.service.j2`** | DS18B20 GPIO demo (opt-in only). |

---

## 2. One mental model

1. Ansible SSHs to the host as **`ansible_user`**.
2. Runs each **task** in order.
3. **`become: true`** means “use **sudo** on the remote host” for that task (install packages, write under `/etc`).

---

## 3. Run the deploy

From **`vibe_code_apps_12/ansible`** on bensserver (or your laptop with the repo):

### Recommended — password SSH + sudo (Option A)

Use this when `ssh ben@192.168.204.12` asks for a password or `./deploy.sh -v` fails with **Permission denied**:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --ask-pass --ask-become-pass -v
```

- First prompt: **SSH password** for `ben@192.168.204.12`
- Second prompt: **sudo password** on the Pi (`become`)
- Needs **`sshpass`** on Linux: `sudo apt install sshpass`

With AWS IoT certs, run once before deploy:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./ansible/prepare_aws_iot_certs.sh
```

### After `ssh-copy-id` — no prompts

```bash
./deploy.sh -v
```

**Dry run** (show what would change, no writes):

```bash
./deploy.sh --ask-pass --ask-become-pass --check
```

---

## 4. Override variables without editing files

Values in **`group_vars/pi_bcn.yml`** can be overridden from the CLI with **`-e`**:

```bash
ansible-playbook deploy.yml -e bacnet_bind_address=eth0
ansible-playbook deploy.yml -e site_id=acme -e building_id=tower-a
ansible-playbook deploy.yml -e enable_bacnet_read_driver=true

# Boss Pi bench only:
ansible-playbook deploy.yml -e enable_ds18b20_gpio=true -e enable_ds18b20_service=true
```

---

## 5. Inventory: add another Pi

Edit **`inventory.yml`**:

```yaml
all:
  children:
    pi_bcn:
      hosts:
        bacnet_pi:
          ansible_host: 192.168.204.12
          ansible_user: ben
        other_pi:
          ansible_host: 192.168.204.99
          ansible_user: ben
```

Both hosts get **`group_vars/pi_bcn.yml`** automatically.

Limit to one host:

```bash
ansible-playbook deploy.yml --limit bacnet_pi
```

---

## 6. SSH and sudo

- **Password SSH + sudo (bensserver default):** `./deploy.sh --ask-pass --ask-become-pass -v`
- **Key-based SSH (later):** `ssh-copy-id ben@192.168.204.12`, then `./deploy.sh -v` with no prompts.

---

## 7. When something fails

- Read the **red** task name and message.
- **`unreachable`**: SSH / firewall / wrong IP or user.
- **`failed`** on **`apt`**: sudo or network on the Pi.
- **`failed`** on **`systemd`**: unit syntax or bad **`ExecStart`** path.

Re-run after fixes; Ansible is **idempotent** for many modules (safe to run again).

---

## 8. After you change code, the template, or vars

Re-run **`deploy.yml`**. The playbook does the same thing you would by hand:

- **`daemon_reload`** — pick up changes to **`/etc/systemd/system/bacnet-ds18b20.service`**
- **`restart bacnet-ds18b20`** — load new **`temp_sensor_server.py`** (a running process does not reload Python on its own)

That is normal for deploy playbooks: push files, then **`systemctl daemon-reload`** + **`systemctl restart`**. Ansible’s **`ansible.builtin.systemd`** module runs those as root when **`become: true`** (no need to type **`sudo`** in the playbook).

If you change only app **`.py`** files, a **notify** handler also restarts at the end of the play. Every successful deploy also runs an explicit **restart** task so you do not have to SSH in after copying code.

On the Pi manually (equivalent):

```bash
sudo systemctl daemon-reload
sudo systemctl restart bacnet-ds18b20
```

---

## 9. Learn more

Official intro: [https://docs.ansible.com/ansible/latest/getting_started/index.html](https://docs.ansible.com/ansible/latest/getting_started/index.html)
