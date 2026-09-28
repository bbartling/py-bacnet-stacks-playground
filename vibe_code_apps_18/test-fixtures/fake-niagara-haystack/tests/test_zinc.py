import datetime as dt
import unittest

from fake_niagara.zinc import Column, Grid, Marker, Quantity, Ref, decode_grid, encode_grid


class ZincTests(unittest.TestCase):
    def test_round_trip_scalars(self):
        original = Grid(
            {"note": "3.0, demo"},
            ["id", "dis", "ts", "val", "ok", "missing", "marker"],
            [{"id": Ref("p-1"), "dis": "A, B", "ts": dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc), "val": 72.5, "ok": True, "missing": None, "marker": Marker()}],
        )
        decoded = decode_grid(encode_grid(original))
        self.assertEqual(decoded.meta["note"], "3.0, demo")
        self.assertEqual(decoded.rows[0]["id"], Ref("p-1"))
        self.assertEqual(decoded.rows[0]["dis"], "A, B")
        self.assertEqual(decoded.rows[0]["val"], 72.5)
        self.assertTrue(decoded.rows[0]["ok"])
        self.assertIsNone(decoded.rows[0]["missing"])
        self.assertIsInstance(decoded.rows[0]["marker"], Marker)

    def test_empty_grid(self):
        encoded = encode_grid(Grid({}, [], []))
        self.assertEqual(encoded, 'ver:"3.0"\nempty\n')
        self.assertEqual(decode_grid(encoded).cols, [])

    def test_batch_column_metadata_and_units(self):
        grid = Grid({}, ["ts", Column("v0", {"id": Ref("point-1")})], [{"ts": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), "v0": Quantity(72.5, "°F")}])
        encoded = encode_grid(grid)
        self.assertIn("v0 id:@point-1", encoded)
        decoded = decode_grid(encoded)
        self.assertEqual(decoded.cols[1].meta["id"], Ref("point-1"))
        self.assertEqual(decoded.rows[0]["v0"], Quantity(72.5, "°F"))

    def test_datetime_with_haystack_timezone_literal(self):
        decoded = decode_grid('ver:"3.0"\nts\n2026-03-08T00:00:00-06:00 Chicago\n')
        self.assertEqual(decoded.rows[0]["ts"].utcoffset().total_seconds(), -21600)
