import unittest

from fake_niagara.data import FakeBASData


class DataTests(unittest.TestCase):
    def setUp(self):
        self.data = FakeBASData()

    def test_chicago_dst_ranges_have_real_elapsed_samples(self):
        spring, start, end = self.data.history("point-ahu1-sat", "2026-03-08")
        fall, _, _ = self.data.history("point-ahu1-sat", "2026-11-01")
        self.assertEqual(len(spring), 92)
        self.assertEqual(len(fall), 100)
        self.assertNotEqual(start.utcoffset(), end.utcoffset())

    def test_filters_are_case_insensitive_and_refs_are_refs(self):
        self.assertEqual(len(self.data.read("POINT AND SITEREF==@SITE-MAIN")), 4)
        self.assertEqual(len(self.data.read("POINT AND HIS")), 4)
        self.assertEqual(len(self.data.read("EQUIP AND SITEREF==@SITE-MAIN")), 2)

    def test_history_is_generated_for_older_and_current_dates(self):
        old, _, _ = self.data.history("point-ahu1-sat", "2020-01-02")
        today, _, _ = self.data.history("point-ahu1-sat", "today")
        self.assertEqual(len(old), 96)
        self.assertGreater(len(today), 0)

    def test_cadence_is_utc_aligned_and_values_are_tz_independent(self):
        chicago, _, _ = self.data.history("point-ahu1-sat", "2026-01-01T00:07:00-06:00,2026-01-01T02:07:00-06:00", "America/Chicago")
        utc, _, _ = self.data.history("point-ahu1-sat", "2026-01-01T06:07:00Z,2026-01-01T08:07:00Z", "UTC")
        self.assertEqual(chicago[0]["ts"].minute % 15, 0)
        self.assertEqual([item["val"] for item in chicago], [item["val"] for item in utc])
