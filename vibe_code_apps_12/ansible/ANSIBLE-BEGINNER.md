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
| **`group_vars/pi_bcn.yml`** | **Variables** for the `pi_bcn` group (paths, BACnet IDs, `bacnet_display_units`, …). |
| **`deploy.yml`** | The **playbook**: ordered tasks (mkdir, copy files, apt, venv, pip, systemd, checks). |
| **`templates/bacnet-ds18b20.service.j2`** | A **Jinja2** template: `{{ variable }}` is filled from vars when copied to the Pi. |

---

## 2. One mental model

1. Ansible SSHs to the host as **`ansible_user`**.
2. Runs each **task** in order.
3. **`become: true`** means “use **sudo** on the remote host” for that task (install packages, write under `/etc`).

---

## 3. Run the deploy

From **`vibe_code_apps_12/ansible`**:

```bash
ansible-playbook deploy.yml
```

Verbose:

```bash
ansible-playbook deploy.yml -v
```

**Dry run** (show what would change, no writes):

```bash
ansible-playbook deploy.yml --check
```

---

## 4. Override variables without editing files

Values in **`group_vars/pi_bcn.yml`** can be overridden from the CLI with **`-e`**:

```bash
ansible-playbook deploy.yml -e bacnet_display_units=celsius
ansible-playbook deploy.yml -e bacnet_bind_address=eth0
ansible-playbook deploy.yml -e ansible_user=pi
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

- **Key-based SSH** is easiest: `ssh-copy-id user@host`, then `ansible-playbook` needs no password.
- **Password SSH + sudo**: `ansible-playbook deploy.yml --ask-pass --ask-become-pass` (needs **`sshpass`** on Linux for `--ask-pass`).

---

## 7. When something fails

- Read the **red** task name and message.
- **`unreachable`**: SSH / firewall / wrong IP or user.
- **`failed`** on **`apt`**: sudo or network on the Pi.
- **`failed`** on **`systemd`**: unit syntax or bad **`ExecStart`** path.

Re-run after fixes; Ansible is **idempotent** for many modules (safe to run again).

---

## 8. After you change the template or vars

Re-run **`deploy.yml`**. If only the unit file changed, Ansible updates **`/etc/systemd/system/bacnet-ds18b20.service`** and the handler runs **`daemon_reload`**; the playbook also **starts** the service so new flags (e.g. **`--display-units`**) apply.

On the Pi manually:

```bash
sudo systemctl daemon-reload
sudo systemctl restart bacnet-ds18b20
```

---

## 9. Learn more

Official intro: [https://docs.ansible.com/ansible/latest/getting_started/index.html](https://docs.ansible.com/ansible/latest/getting_started/index.html)
