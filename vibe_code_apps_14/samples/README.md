# BACnet samples (campus lab)

| Script | Role in campus lab |
|--------|-------------------|
| `mini-device-revisited.py` | Building mini on bensserver net **200** |
| `fake_vav.py` | VAV on `192.168.204.14` net **201** |
| `fake_ahu.py` | AHU on `192.168.0.13` net **202** |
| `ipv4-to-ipv4.py` | Interactive router shell (optional) |

Deploy and run via `ansible/deploy_campus_lab.yml` — see [docs/TUTORIAL-CAMPUS-LAB.md](../docs/TUTORIAL-CAMPUS-LAB.md).
