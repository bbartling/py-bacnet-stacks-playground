# BAS driver catalog (AI / human editable)

Paste this file into ChatGPT or Cursor and ask:
> Keep only the points we need for FDD / trending; set `enabled = false` on the rest.

## Workflow

1. Edit the TOML block at the bottom (or the summary tables).
2. Save as `config/drivers.catalog.md`.
3. Apply: `cargo run --release --bin bas_scan -- --apply-catalog config/drivers.catalog.md`
4. Restart the app: `cargo run --release --bin bacnet_app`

Or edit `config/drivers.toml` directly — it is the live source of truth.

## Scan metadata

```
generated_by = bas_scan
range = 1..4194302
bind = 192.168.204.55
broadcast = 192.168.204.255
devices = 3

```

## Device summary

| enabled | name | instance | host | routed | points (enabled/total) |
| --- | --- | ---: | --- | --- | ---: |
| true | BENS-BENCHTEST-BOX | 5007 | 192.168.204.200:47808 | yes | 59/59 |
| true | BensFakeAhu | 3456789 | 192.168.204.13:47808 | no | 17/17 |
| true | Zone1VAV | 3456790 | 192.168.204.14:47808 | no | 6/6 |

## Device `BENS-BENCHTEST-BOX` (instance 5007)

| enabled | point_name | object_type | object_instance | units |
| --- | --- | --- | ---: | --- |
| true | OA-H | analog-input | 1168 |  |
| true | OA-T | analog-input | 1173 |  |
| true | SSPLATE-T | analog-input | 1179 |  |
| true | DUCT-T | analog-input | 1192 |  |
| true | DUCT-P | analog-input | 9334 |  |
| true | STAT ZN-T | analog-input | 10014 |  |
| true | ACTUATOR-POS | analog-input | 10044 |  |
| true | ACTUATOR-0 | analog-output | 2466 |  |
| true | C06-0-10VDC-O | analog-output | 10032 |  |
| true | C07-0-10VDC-O | analog-output | 10035 |  |
| true | AO9-4-20MA-O | analog-output | 10038 |  |
| true | Priority | analog-value | 10007 |  |
| true | Priority | analog-value | 10010 |  |
| true | STAT ZN WC-ADJ | analog-value | 10011 |  |
| true | Priority | analog-value | 10012 |  |
| true | O1 | analog-value | 10013 |  |
| true | Priority | analog-value | 10015 |  |
| true | O1 | analog-value | 10016 |  |
| true | Priority | analog-value | 10021 |  |
| true | Priority | analog-value | 10025 |  |
| true | Priority | analog-value | 10028 |  |
| true | Priority | analog-value | 10031 |  |
| true | I1 | analog-value | 10033 |  |
| true | Priority | analog-value | 10034 |  |
| true | I1 | analog-value | 10036 |  |
| true | Priority | analog-value | 10037 |  |
| true | I1 | analog-value | 10039 |  |
| true | Priority | analog-value | 10040 |  |
| true | O1 | analog-value | 169012 |  |
| true | Priority | analog-value | 169013 |  |
| true | O1 | analog-value | 169020 |  |
| true | Priority | analog-value | 169021 |  |
| true | O1 | analog-value | 169030 |  |
| true | Priority | analog-value | 169031 |  |
| true | O1 | analog-value | 169040 |  |
| true | Priority | analog-value | 169041 |  |
| true | Priority | analog-value | 237957 |  |
| true | I1 | analog-value | 237958 |  |
| true | O1 | analog-value | 238001 |  |
| true | Priority | analog-value | 238002 |  |
| true | Priority | analog-value | 238198 |  |
| true | CURRENT-S | binary-input | 9429 |  |
| true | BI8-S | binary-input | 10020 |  |
| true | RIBRELAY1- C | binary-output | 10005 |  |
| true | RIBRELAY#2-C | binary-output | 10008 |  |
| true | BO3-C | binary-output | 10023 |  |
| true | C04-DRY-C | binary-output | 10026 |  |
| true | C05-DRY-C | binary-output | 10029 |  |
| true | I2 | binary-value | 10001 |  |
| true | O2 | binary-value | 10002 |  |
| true | O1 | multi-state-value | 10003 |  |
| true | I1 | multi-state-value | 10004 |  |
| true | I1 | multi-state-value | 10006 |  |
| true | I1 | multi-state-value | 10009 |  |
| true | O1 | multi-state-value | 10022 |  |
| true | I1 | multi-state-value | 10024 |  |
| true | I1 | multi-state-value | 10027 |  |
| true | I1 | multi-state-value | 10030 |  |
| true | O1 | multi-state-value | 238197 |  |

## Device `BensFakeAhu` (instance 3456789)

| enabled | point_name | object_type | object_instance | units |
| --- | --- | --- | ---: | --- |
| true | DAP-P | analog-input | 1 |  |
| true | SA-T | analog-input | 2 |  |
| true | MA-T | analog-input | 3 |  |
| true | RA-T | analog-input | 4 |  |
| true | SA-FLOW | analog-input | 5 |  |
| true | OA-T | analog-input | 6 |  |
| true | ELEC-PWR | analog-input | 7 |  |
| true | SF-O | analog-output | 1 |  |
| true | HTG-O | analog-output | 2 |  |
| true | CLG-O | analog-output | 3 |  |
| true | DPR-O | analog-output | 4 |  |
| true | DAP-SP | analog-value | 1 |  |
| true | SAT-SP | analog-value | 2 |  |
| true | OAT-NETWORK | analog-value | 3 |  |
| true | SF-S | binary-input | 1 |  |
| true | SF-C | binary-output | 1 |  |
| true | Occ-Schedule | multi-state-value | 1 |  |

## Device `Zone1VAV` (instance 3456790)

| enabled | point_name | object_type | object_instance | units |
| --- | --- | --- | ---: | --- |
| true | ZoneTemp | analog-input | 1 |  |
| true | VAVFlow | analog-input | 2 |  |
| true | ZoneCoolingSpt | analog-value | 1 |  |
| true | ZoneDemand | analog-value | 2 |  |
| true | VAVFlowSpt | analog-value | 3 |  |
| true | VAVDamperCmd | analog-output | 1 |  |

## Full drivers.toml (apply this block)

```toml
# =============================================================================
# Open-FDD BAS drivers — AI / human editable poll list
# =============================================================================
# HOW TO EDIT (ChatGPT, Cursor, or a text editor):
#   1. Set enabled = false on any device or point you do NOT want polled
#   2. Optionally rename point_name for clearer Feather columns
#   3. Set critical = true on the device that feeds APP-FAULT / duct clone
#   4. Save this file and restart: cargo run --release --bin bacnet_app
#
# Re-scan the BAS (preserves enabled=false when using --merge):
#   cargo run --release --bin bas_scan -- --low 1 --high 4194302 --ephemeral --merge
#
# Companion catalog (tables + same TOML): config/drivers.catalog.md
# All readings append to a single data/feather_store/telemetry.feather
#
# generated_by = bas_scan
# range = 1..4194302
# bind = 192.168.204.55
# broadcast = 192.168.204.255
# devices = 3
# =============================================================================

[[devices]]
name = "BENS-BENCHTEST-BOX"
enabled = true
device_instance = 5007
host = "192.168.204.200"
port = 47808
mstp_network = 2000
mstp_mac = [7]
interval_secs = 10
offset_secs = 0
critical = true

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1168
point_name = "OA-H"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1173
point_name = "OA-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1179
point_name = "SSPLATE-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1192
point_name = "DUCT-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 9334
point_name = "DUCT-P"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 10014
point_name = "STAT ZN-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 10044
point_name = "ACTUATOR-POS"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 2466
point_name = "ACTUATOR-0"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 10032
point_name = "C06-0-10VDC-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 10035
point_name = "C07-0-10VDC-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 10038
point_name = "AO9-4-20MA-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10007
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10010
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10011
point_name = "STAT ZN WC-ADJ"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10012
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10013
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10015
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10016
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10021
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10025
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10028
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10031
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10033
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10034
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10036
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10037
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10039
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 10040
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169012
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169013
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169020
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169021
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169030
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169031
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169040
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 169041
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 237957
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 237958
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 238001
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 238002
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 238198
point_name = "Priority"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-input"
object_instance = 9429
point_name = "CURRENT-S"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-input"
object_instance = 10020
point_name = "BI8-S"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 10005
point_name = "RIBRELAY1- C"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 10008
point_name = "RIBRELAY#2-C"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 10023
point_name = "BO3-C"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 10026
point_name = "C04-DRY-C"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 10029
point_name = "C05-DRY-C"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-value"
object_instance = 10001
point_name = "I2"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-value"
object_instance = 10002
point_name = "O2"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10003
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10004
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10006
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10009
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10022
point_name = "O1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10024
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10027
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 10030
point_name = "I1"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 238197
point_name = "O1"
units = ""


[[devices]]
name = "BensFakeAhu"
enabled = true
device_instance = 3456789
host = "192.168.204.13"
port = 47808
interval_secs = 10
offset_secs = 2
critical = false

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1
point_name = "DAP-P"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 2
point_name = "SA-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 3
point_name = "MA-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 4
point_name = "RA-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 5
point_name = "SA-FLOW"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 6
point_name = "OA-T"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 7
point_name = "ELEC-PWR"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 1
point_name = "SF-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 2
point_name = "HTG-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 3
point_name = "CLG-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 4
point_name = "DPR-O"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 1
point_name = "DAP-SP"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 2
point_name = "SAT-SP"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 3
point_name = "OAT-NETWORK"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-input"
object_instance = 1
point_name = "SF-S"
units = ""

[[devices.points]]
enabled = true
object_type = "binary-output"
object_instance = 1
point_name = "SF-C"
units = ""

[[devices.points]]
enabled = true
object_type = "multi-state-value"
object_instance = 1
point_name = "Occ-Schedule"
units = ""


[[devices]]
name = "Zone1VAV"
enabled = true
device_instance = 3456790
host = "192.168.204.14"
port = 47808
interval_secs = 10
offset_secs = 4
critical = false

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 1
point_name = "ZoneTemp"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-input"
object_instance = 2
point_name = "VAVFlow"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 1
point_name = "ZoneCoolingSpt"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 2
point_name = "ZoneDemand"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-value"
object_instance = 3
point_name = "VAVFlowSpt"
units = ""

[[devices.points]]
enabled = true
object_type = "analog-output"
object_instance = 1
point_name = "VAVDamperCmd"
units = ""


```
