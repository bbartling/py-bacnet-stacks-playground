# FDD rules in this demo

Vibe12 does not maintain its own rule cookbook.

Rules run through the PyPI [`open-fdd`](https://pypi.org/project/open-fdd/) package using the Arrow-native contract:

```python
def apply_faults_arrow(table, cfg, context=None):
    ...
```

For the maintained rule cookbook, see:
https://bbartling.github.io/open-fdd/rule-cookbook/

For PyPI:
https://pypi.org/project/open-fdd/

This demo ships a tiny rule pack (`vibe12_openfdd_cloud_demo_v1`) only to show **AWS IoT Core → DynamoDB → Lambda FDD** execution with readable debug output.
