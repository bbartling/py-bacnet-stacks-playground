import unittest
try:
    from django.test import Client, TestCase
except Exception:
    # If Django is not installed in this environment we skip these tests. The
    # production environment should have Django installed.
    Client = None  # type: ignore
    TestCase = object  # type: ignore



@unittest.skipIf(Client is None, "Django not available for backend tests")
class BackendTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_serves_react_ui(self):
        """The root path should serve the React index with our nav tabs."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        # ensure basic keywords are present
        content = resp.content.decode('utf-8')
        self.assertIn('<nav', content)
        self.assertIn('Schedule', content)
        # The React UI uses "Overview" instead of "Dashboard"
        self.assertIn('Overview', content)
        self.assertIn('Points', content)
        self.assertIn('Notifications', content)
        self.assertIn('Logic Flow', content)

    def test_points_api_requires_login(self):
        """/api/points should return 401 for anonymous users."""
        resp = self.client.get('/api/points')
        # The API uses JsonResponse with status 401 when unauthorized
        self.assertEqual(resp.status_code, 401)

    def test_status_points_requires_login(self):
        """/api/status/points requires authentication."""
        resp = self.client.get('/api/status/points')
        self.assertEqual(resp.status_code, 401)

    def test_status_devices_requires_login(self):
        """/api/status/devices requires authentication."""
        resp = self.client.get('/api/status/devices')
        self.assertEqual(resp.status_code, 401)

    def test_point_model_has_status_fields(self):
        """Ensure the Point model includes new status flags."""
        from bas.models import Point
        field_names = [f.name for f in Point._meta.get_fields()]
        self.assertIn('disabled', field_names)
        self.assertIn('overridden', field_names)
        self.assertIn('fault', field_names)