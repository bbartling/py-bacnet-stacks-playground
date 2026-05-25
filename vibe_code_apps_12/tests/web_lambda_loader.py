"""Load web_lambda/lambda_function.py in unit tests without installing boto3."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"

_BOTO3_STUB_MODULES = (
    "boto3",
    "boto3.dynamodb",
    "boto3.dynamodb.conditions",
)


def _install_boto3_stub() -> MagicMock:
    """Register fake boto3 modules so patch/import never needs the real package."""
    boto3 = MagicMock()
    boto3.resource.return_value.Table.return_value = MagicMock()

    dynamodb = ModuleType("boto3.dynamodb")
    dynamodb.conditions = ModuleType("boto3.dynamodb.conditions")  # type: ignore[attr-defined]
    dynamodb.conditions.Key = MagicMock(name="Key")  # type: ignore[attr-defined]

    boto3.dynamodb = dynamodb  # type: ignore[attr-defined]

    sys.modules["boto3"] = boto3
    sys.modules["boto3.dynamodb"] = dynamodb
    sys.modules["boto3.dynamodb.conditions"] = dynamodb.conditions
    return boto3


def load_web_lambda(module_name: str = "vibe12_web_lambda") -> ModuleType:
    if str(_WEB) not in sys.path:
        sys.path.insert(0, str(_WEB))

    _install_boto3_stub()

    _purge = (
        "mqtt_routing",
        "lambda_function",
        "timeseries",
        "brick_model",
        "brick_timeseries",
        "telemetry_api",
    )
    for mod in list(sys.modules):
        if mod in _purge:
            del sys.modules[mod]

    spec = importlib.util.spec_from_file_location(module_name, _WEB / "lambda_function.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod
