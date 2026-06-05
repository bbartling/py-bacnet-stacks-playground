"""Compatibility shim — Rule Lab engine lives in PyPI ``open_fdd.playground.rule_lab``.

VIBE12 tests and legacy imports use ``playground_core``; ``lambda_function`` imports
``open_fdd.playground.rule_lab`` directly.
"""

from open_fdd.playground.rule_lab import *  # noqa: F403
