import datetime as dt
import os
import sqlite3
import tempfile
import unittest

from fake_niagara.client import backfill_yesterday
from fake_niagara.zinc import Grid, Quantity, Ref


class StubClient:
    def __init__(self, source, value):
        self.base_url = source
        self.value = value

    def read(self, _filter):
        return Grid({}, ["id"], [{"id": Ref("p-1")}])

    def his_read(self, _point, _range):
        return Grid({}, ["ts", "val"], [{"ts": dt.datetime(2026, 1, 1, 1, tzinfo=dt.timezone.utc), "val": Quantity(self.value, "°F")}])


class BackfillTests(unittest.TestCase):
    def test_corrections_are_upserted_and_sources_are_separate(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
        try:
            first = StubClient("http://one", 70)
            second = StubClient("http://one", 71)
            other_source = StubClient("http://two", 80)
            self.assertEqual(backfill_yesterday(first, path, date=dt.date(2026, 1, 1)), 1)
            self.assertEqual(backfill_yesterday(first, path, date=dt.date(2026, 1, 1)), 0)
            self.assertEqual(backfill_yesterday(second, path, date=dt.date(2026, 1, 1)), 1)
            self.assertEqual(backfill_yesterday(other_source, path, date=dt.date(2026, 1, 1)), 1)
            db = sqlite3.connect(path)
            rows = db.execute("SELECT point_id, ts, value_num, unit, source FROM haystack_history ORDER BY source").fetchall()
            db.close()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][2:], (71.0, "°F", "http://one"))
            self.assertEqual(rows[1][2:], (80.0, "°F", "http://two"))
            self.assertTrue(rows[0][1].endswith("Z"))
        finally:
            os.unlink(path)
