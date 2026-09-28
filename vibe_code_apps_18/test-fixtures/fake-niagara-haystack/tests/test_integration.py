import datetime as dt
import base64
import hashlib
import hmac
import os
import sqlite3
import tempfile
import urllib.error
import urllib.request
import unittest

from fake_niagara.client import HaystackClient, backfill_yesterday
from fake_niagara.server import FakeHaystackServer, ServerConfig
from fake_niagara.zinc import Quantity, Ref


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeHaystackServer(ServerConfig("127.0.0.1", 0, "/api", "admin", "demo", True))
        self.server.start()
        self.client = HaystackClient(f"http://127.0.0.1:{self.server.address[1]}/api", "admin", "demo")

    def tearDown(self):
        self.client.close()
        self.server.shutdown()

    def test_scram_read_single_batch_and_backfill(self):
        about = self.client.about()
        self.assertEqual(about.rows[0]["productName"], "Fake Niagara 4")
        self.assertEqual(self.client.formats().rows[0]["mime"], "text/zinc")
        points = self.client.read("point and his")
        self.assertEqual(len(points.rows), 4)
        selected = self.client.read_by_ids(["point-ahu1-sat", "point-vav1-zone"])
        self.assertEqual(len(selected.rows), 2)
        point_id = points.rows[0]["id"]
        self.assertIsInstance(point_id, Ref)
        day = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
        history = self.client.his_read(point_id.value, day.isoformat())
        self.assertEqual(len(history.rows), 96)
        batch = self.client.his_read_batch([(row["id"].value, "yesterday") for row in points.rows[:2]])
        self.assertEqual(len(batch.rows), 96)
        self.assertEqual([column.name for column in batch.cols], ["ts", "v0", "v1"])
        self.assertEqual(batch.cols[1].meta["id"], Ref("point-ahu1-sat"))
        self.assertIsInstance(batch.rows[0]["v0"], Quantity)
        ordered = self.client.read_by_ids(["point-vav1-zone", "does-not-exist", "point-ahu1-sat"])
        self.assertEqual(ordered.rows[0]["id"], Ref("point-vav1-zone"))
        self.assertIsNone(ordered.rows[1]["id"])
        self.assertEqual(ordered.rows[2]["id"], Ref("point-ahu1-sat"))
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
        try:
            self.assertEqual(backfill_yesterday(self.client, path, date=day), 384)
            self.assertEqual(backfill_yesterday(self.client, path, date=day), 0)
            db = sqlite3.connect(path)
            self.assertEqual(db.execute("select count(*) from haystack_history").fetchone()[0], 384)
            db.close()
        finally:
            os.unlink(path)

    def test_batch_fall_back_join_uses_utc_instants(self):
        batch = self.client.his_read_batch([("point-ahu1-sat", "2026-11-01"), ("point-vav1-zone", "2026-11-01")])
        self.assertEqual(len(batch.rows), 100)
        self.assertEqual(len({row["ts"].astimezone(dt.timezone.utc) for row in batch.rows}), 100)

    def test_hisread_limits_return_error_grid(self):
        self.client.close()
        self.server.shutdown()
        self.server = FakeHaystackServer(ServerConfig("127.0.0.1", 0, "/api", "admin", "demo", True, max_history_days=1, max_history_samples=20, max_batch_points=1))
        self.server.start()
        self.client = HaystackClient(f"http://127.0.0.1:{self.server.address[1]}/api", "admin", "demo")
        with self.assertRaises(RuntimeError):
            self.client.his_read("point-ahu1-sat", "2026-01-01")
        with self.assertRaises(RuntimeError):
            self.client.his_read_batch([("point-ahu1-sat", "today"), ("point-vav1-zone", "today")])

    def test_live_http_three_step_standard_scram(self):
        url = f"http://127.0.0.1:{self.server.address[1]}/api/about"
        nonce = base64.b64encode(b"123456789012345678").decode().rstrip("=")
        first = base64.urlsafe_b64encode(f"n,,n=admin,r={nonce}".encode()).decode().rstrip("=")
        username = base64.urlsafe_b64encode(b"admin").decode().rstrip("=")
        request = urllib.request.Request(url, headers={"Authorization": f"HELLO username={username}"})
        try:
            urllib.request.urlopen(request)
        except urllib.error.HTTPError as response:
            self.assertEqual(response.code, 401)
            hello = response.headers["WWW-Authenticate"]
        scheme, values = hello.split(" ", 1)
        params = dict(item.strip().split("=", 1) for item in values.split(","))
        request = urllib.request.Request(url, headers={"Authorization": f"SCRAM handshakeToken={params['handshakeToken']}, data={first}"})
        try:
            urllib.request.urlopen(request)
        except urllib.error.HTTPError as response:
            self.assertEqual(response.code, 401)
            challenge = response.headers["WWW-Authenticate"]
        _, values = challenge.split(" ", 1)
        params = dict(item.strip().split("=", 1) for item in values.split(","))
        server_first = base64.urlsafe_b64decode(params["data"] + "===").decode()
        fields = dict(item.split("=", 1) for item in server_first.split(","))
        salted = hashlib.pbkdf2_hmac("sha256", b"demo", base64.b64decode(fields["s"]), int(fields["i"]))
        client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
        stored = hashlib.sha256(client_key).digest()
        final_no_proof = f"c=biws,r={fields['r']}"
        auth_message = f"n=admin,r={nonce},{server_first},{final_no_proof}"
        signature = hmac.new(stored, auth_message.encode(), hashlib.sha256).digest()
        proof = bytes(a ^ b for a, b in zip(client_key, signature))
        final = base64.urlsafe_b64encode(f"{final_no_proof},p={base64.b64encode(proof).decode()}".encode()).decode().rstrip("=")
        request = urllib.request.Request(url, headers={"Authorization": f"SCRAM handshakeToken={params['handshakeToken']}, data={final}"})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("authToken=", response.headers["Authentication-Info"])
