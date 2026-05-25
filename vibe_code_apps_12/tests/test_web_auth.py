"""Session auth for Vibe12 web Lambda (single engineer login)."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

_WEB = Path(__file__).resolve().parents[1] / "aws_cloud_pipeline" / "web_lambda"
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))


def _reload_auth(**env: str):
    for key in (
        "VIBE12_AUTH_SECRET",
        "VIBE12_WEB_USER",
        "VIBE12_WEB_PASSWORD",
        "VIBE12_AUTH_TTL_SEC",
    ):
        os.environ.pop(key, None)
    for key, val in env.items():
        os.environ[key] = val
    if "web_auth" in sys.modules:
        del sys.modules["web_auth"]
    import web_auth

    return importlib.reload(web_auth)


class TestWebAuth(unittest.TestCase):
    def test_disabled_when_env_missing(self) -> None:
        wa = _reload_auth()
        self.assertFalse(wa.auth_enabled())
        self.assertTrue(wa.check_credentials("any", "any"))
        self.assertIsNotNone(wa.verify_token(None))

    def test_login_and_token_roundtrip(self) -> None:
        wa = _reload_auth(
            VIBE12_AUTH_SECRET="unit-test-secret-key",
            VIBE12_WEB_USER="engineer",
            VIBE12_WEB_PASSWORD="s3cret",
        )
        self.assertTrue(wa.auth_enabled())
        self.assertTrue(wa.check_credentials("engineer", "s3cret"))
        self.assertFalse(wa.check_credentials("engineer", "wrong"))
        token = wa.issue_token("engineer")
        claims = wa.verify_token(token)
        self.assertIsNotNone(claims)
        assert claims is not None
        self.assertEqual(claims["sub"], "engineer")

    def test_extract_bearer(self) -> None:
        wa = _reload_auth()
        event = {"headers": {"Authorization": "Bearer abc.def"}}
        self.assertEqual(wa.extract_bearer(event), "abc.def")


if __name__ == "__main__":
    unittest.main()
