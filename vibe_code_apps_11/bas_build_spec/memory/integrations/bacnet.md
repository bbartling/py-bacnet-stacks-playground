# BACnet lab memory (per building / site)

Human fills bind and discovery sign-off before automation enables on-wire drivers.

## Sign-off checklist

- [ ] Local NIC bind documented (not field device IP)
- [ ] `point_discovery.py` run with expected I-Am / object-list output
- [ ] Validated BACpypes3 CLI args recorded (`--name`, `--instance`, `--address`; optional `--debug`)
- [ ] Device instance + pduSource inventory recorded below
- [ ] BUILD_CHECKPOINTS.md updated under Done recently

## Validated SimpleArgumentParser args (AI copies these)

| Field | Value |
|-------|-------|
| `--name` | |
| `--instance` | |
| `--address` | |

Template: `bas_build_spec/bacnet_scripts_example/human_validated_args.env.example`

## Inventory

*(Append after each validated discovery run.)*
