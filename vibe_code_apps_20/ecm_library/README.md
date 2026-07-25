# Deprecated ECM library shim

`ecm_library` is retained only for import compatibility. It is not an ECM
registry and must not receive new measure metadata.

The canonical registry is [`../wattlab/measures/catalog.yaml`](../wattlab/measures/catalog.yaml).
For example, `ECM-OCC-STANDBY-DCV` is defined there and is available through
`wattlab.ecm.get_ecm`, packages, Studio Easy Buttons, and agent scenarios.
