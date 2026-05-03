import unittest
import os
from pathlib import Path
try:
    from django.test import SimpleTestCase
except Exception:
    # Fallback when Django is unavailable. Use unittest.TestCase
    SimpleTestCase = unittest.TestCase  # type: ignore


class FrontendFileTests(SimpleTestCase):
    """Tests against the static React index file.

    We cannot run a full JavaScript unit test suite without Node modules, but
    parsing the HTML ensures that the document renders our navigation tabs and
    includes the React/Babel scripts. This provides confidence that the
    frontend was converted from vanilla JS to React and that the key
    components are present.
    """

    def test_index_contains_required_sections(self):
        # Locate the index.html relative to this test file. We go up three
        # directories to reach the diy-bas project root. If the path does not
        # exist the test will fail.
        base_dir = Path(__file__).resolve().parents[3]
        index_path = base_dir / 'frontend' / 'index.html'
        self.assertTrue(index_path.exists(), f"{index_path} does not exist")
        content = index_path.read_text(encoding='utf-8')
        # check that React and Babel are referenced
        self.assertIn('react.production.min.js', content)
        self.assertIn('@babel/standalone', content)
        # check nav buttons labels; the React UI now uses "Overview" instead of "Dashboard"
        self.assertIn('Schedule', content)
        self.assertIn('Overview', content)
        self.assertIn('Points', content)
        self.assertIn('Notifications', content)
        # integrator nav should include Logic Flow label
        self.assertIn('Logic Flow', content)
        # diagnostics tab should be present for querying point/device statuses
        self.assertIn('Diagnostics', content)