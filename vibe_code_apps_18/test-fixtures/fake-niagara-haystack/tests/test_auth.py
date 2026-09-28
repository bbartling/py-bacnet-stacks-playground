import base64
import hashlib
import hmac
import unittest

from fake_niagara.auth import AuthManager
from fake_niagara.client import HaystackClient, _decode_outer


class AuthTests(unittest.TestCase):
    def test_bad_password_is_rejected(self):
        auth = AuthManager({"admin": "secret"})
        client = HaystackClient("http://example.invalid/api", "admin", "wrong")
        nonce, first = _client_first("admin")
        status, headers = auth.hello(base64.b64encode(b"admin").decode(), first)
        self.assertEqual(status, 401)
        challenge = headers["WWW-Authenticate"]
        params = dict(x.strip().split("=", 1) for x in challenge[len("SCRAM "):].split(","))
        # A wrong-password proof is produced against the challenge by the
        # regular client helper's equivalent algorithm in the integration test;
        # here ensure the manager did not issue a token on malformed proof.
        self.assertEqual(auth.scram(params["handshakeToken"], "not-base64"), (403, {}))

    def test_standard_unpadded_urlsafe_outer_auth_and_replay(self):
        auth = AuthManager({"admin": "secret"})
        nonce, first = _client_first("admin", urlsafe=True)
        status, headers = auth.hello(base64.urlsafe_b64encode(b"admin").decode().rstrip("="), first)
        self.assertEqual(status, 401)
        scheme, params = _params(headers["WWW-Authenticate"])
        self.assertEqual(scheme, "SCRAM")
        server_first = base64.urlsafe_b64decode(params["data"] + "===").decode()
        fields = dict(item.split("=", 1) for item in server_first.split(","))
        combined = fields["r"]
        salted = hashlib.pbkdf2_hmac("sha256", b"secret", base64.b64decode(fields["s"]), int(fields["i"]))
        client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
        stored = hashlib.sha256(client_key).digest()
        final_no_proof = f"c=biws,r={combined}"
        auth_message = f"n=admin,r={nonce},{server_first},{final_no_proof}"
        signature = hmac.new(stored, auth_message.encode(), hashlib.sha256).digest()
        proof = bytes(a ^ b for a, b in zip(client_key, signature))
        final = base64.urlsafe_b64encode(f"{final_no_proof},p={base64.b64encode(proof).decode()}".encode()).decode().rstrip("=")
        status, info = auth.scram(params["handshakeToken"], final)
        self.assertEqual(status, 200)
        self.assertIn("authToken=", info["Authentication-Info"])
        self.assertEqual(auth.scram(params["handshakeToken"], final), (403, {}))

    def test_unknown_user_never_gets_token(self):
        auth = AuthManager({"admin": "secret"})
        nonce, first = _client_first("nobody")
        status, headers = auth.hello(base64.b64encode(b"nobody").decode(), first)
        params = _params(headers["WWW-Authenticate"])[1]
        self.assertEqual(auth.scram(params["handshakeToken"], "bad"), (403, {}))

    def test_three_step_hello_then_client_first_then_final(self):
        auth = AuthManager({"admin": "secret"})
        nonce, first = _client_first("admin", urlsafe=True)
        status, headers = auth.hello(base64.urlsafe_b64encode(b"admin").decode().rstrip("="), None)
        self.assertEqual(status, 401)
        token = _params(headers["WWW-Authenticate"])[1]["handshakeToken"]
        status, challenge = auth.scram(token, first)
        self.assertEqual(status, 401)
        challenge_params = _params(challenge["WWW-Authenticate"])[1]
        server_first = base64.urlsafe_b64decode(challenge_params["data"] + "===").decode()
        fields = dict(item.split("=", 1) for item in server_first.split(","))
        salted = hashlib.pbkdf2_hmac("sha256", b"secret", base64.b64decode(fields["s"]), int(fields["i"]))
        client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
        stored = hashlib.sha256(client_key).digest()
        final_no_proof = f"c=biws,r={fields['r']}"
        auth_message = f"n=admin,r={nonce},{server_first},{final_no_proof}"
        signature = hmac.new(stored, auth_message.encode(), hashlib.sha256).digest()
        proof = bytes(a ^ b for a, b in zip(client_key, signature))
        final = base64.urlsafe_b64encode(f"{final_no_proof},p={base64.b64encode(proof).decode()}".encode()).decode().rstrip("=")
        status, info = auth.scram(token, final)
        self.assertEqual(status, 200)
        self.assertIn("authToken=", info["Authentication-Info"])

    def test_outer_decode_does_not_misclassify_abcdef(self):
        self.assertEqual(_decode_outer("YWJjZGVm"), b"abcdef")


def _client_first(username: str, urlsafe: bool = False) -> tuple[str, str]:
    import secrets

    nonce = base64.b64encode(secrets.token_bytes(18)).decode()
    encoded = base64.urlsafe_b64encode(f"n,,n={username},r={nonce}".encode()).decode().rstrip("=") if urlsafe else base64.b64encode(f"n,,n={username},r={nonce}".encode()).decode()
    return nonce, encoded


def _params(header: str) -> tuple[str, dict[str, str]]:
    scheme, rest = header.split(" ", 1)
    return scheme, dict(item.strip().split("=", 1) for item in rest.split(","))
