"""Small helpers for isolated Studio page state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import MutableMapping
from typing import Any

DEPENDENT_PREFIXES = ("hypothesis_lab.", "ecm_easy.")
_SOURCE_SIGNATURE_KEY = "_studio.source_signature"


def namespaced_key(namespace: str, name: str) -> str:
    """Return a stable Streamlit key scoped to one page."""

    return f"{namespace.strip('.')}.{name.strip('.')}"


def _source_signature(profile: Any, bundle: Any) -> str:
    payload = {
        "profile": profile,
        "bundle": getattr(bundle, "building_id", None),
        "bundle_files": [str(item) for item in getattr(bundle, "files", ())],
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def invalidate_dependent_state(
    state: MutableMapping[str, Any],
    *,
    profile: Any = None,
    bundle: Any = None,
) -> bool:
    """Clear derived new-page state when the profile or bundle changes."""

    signature = _source_signature(profile, bundle)
    previous = state.get(_SOURCE_SIGNATURE_KEY)
    state[_SOURCE_SIGNATURE_KEY] = signature
    if previous is None or previous == signature:
        return False
    for key in list(state):
        if key.startswith(DEPENDENT_PREFIXES):
            del state[key]
    return True
