# Upstream BACpypes3 sample scripts

Copied from [JoelBender/BACpypes3 `samples/`](https://github.com/JoelBender/BACpypes3/tree/main/samples) for lab use. The **library** is installed via pip (`bacpypes3`); these files are **not** shipped in the PyPI wheel.

| File | Use |
|------|-----|
| `mini-device-revisited.py` | Dual mini BACnet devices (`start_two_minis.sh`) |
| `ipv4-to-ipv4.py` | Interactive IPv4 router shell (`start_ipv4_router.sh`) |

Refresh from upstream when needed:

```bash
curl -fsSL -o samples/mini-device-revisited.py \
  https://raw.githubusercontent.com/JoelBender/BACpypes3/main/samples/mini-device-revisited.py
curl -fsSL -o samples/ipv4-to-ipv4.py \
  https://raw.githubusercontent.com/JoelBender/BACpypes3/main/samples/ipv4-to-ipv4.py
```
