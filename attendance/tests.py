from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Session, Attendance
from .utils import haversine_m, is_code_valid, current_window, code_for_window

User = get_user_model()

class MathAndCryptoHelperTests(APITestCase):
    def test_haversine_known_coordinates(self):
        """
        Verify Haversine formula against a known real-world benchmark:
        London Big Ben (51.5007, -0.1246) to London Eye (51.5033, -0.1195)
        Expected distance is ~463 metres.
        """
        lat1, lon1 = 51.5007, -0.1246
        lat2, lon2 = 51.5033, -0.1195
        dist = haversine_m(lat1, lon1, lat2, lon2)
        self.assertAlmostEqual(dist, 463.0, delta=20.0)

        # Same point should have 0 distance
        self.assertEqual(haversine_m(51.5007, -0.1246, 51.5007, -0.1246), 0.0)

    def test_is_code_valid_windows(self):
        """Verify code validity across current, previous, and expired windows."""
        secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        rotation_seconds = 30
        now_ts = 1700000000.0  # arbitrary fixed timestamp

        w_now = current_window(rotation_seconds, at=now_ts)
        current_code = code_for_window(secret, w_now)
        previous_code = code_for_window(secret, w_now - 1)
        older_code = code_for_window(secret, w_now - 2)
        future_code = code_for_window(secret, w_now + 1)

        # Current window -> valid
        self.assertTrue(is_code_valid(secret, rotation_seconds, current_code, at=now_ts))
        # Previous window -> valid (clock skew tolerance)
        self.assertTrue(is_code_valid(secret, rotation_seconds, previous_code, at=now_ts))
        # Two windows ago -> expired / invalid
        self.assertFalse(is_code_valid(secret, rotation_seconds, older_code, at=now_ts))
        # Future window -> invalid
        self.assertFalse(is_code_valid(secret, rotation_seconds, future_code, at=now_ts))
        # Corrupt code -> invalid
        self.assertFalse(is_code_valid(secret, rotation_seconds, "badcode", at=now_ts))
        self.assertFalse(is_code_valid(secret, rotation_seconds, "", at=now_ts))


class AttendanceAPITests(APITestCase):
    def setUp(self):
        # Create Host and Attendee users
        self.host = User.objects.create_user(
            email="prof@geoqr.edu",
            password="HostPassword123!",
            full_name="Professor Davis"
        )
        self.attendee = User.objects.create_user(
            email="student@geoqr.edu",
            password="StudentPassword123!",
            full_name="Alex Turner"
        )
        self.other_user = User.objects.create_user(
            email="other@geoqr.edu",
            password="OtherPassword123!",
            full_name="Other User"
        )

        # Base location: Campus Lecture Hall (51.507400, -0.127800)
        self.base_lat = Decimal("51.507400")
        self.base_lng = Decimal("-0.127800")

        # Standard active session with 50m geofence
        self.session = Session.objects.create(
            host=self.host,
            title="CS101 Intro to Algorithms",
            range_m=50,
            rotation_seconds=30,
            collect_name=True,
            collect_id=True,
            id_label="Student ID",
            latitude=self.base_lat,
            longitude=self.base_lng,
            expires_at=timezone.now() + timedelta(minutes=60),
            is_active=True
        )

    def test_4_create_session_secret_absent(self):
        """Test 4: Create session -> 201, code_secret absent from response"""
        self.client.force_authenticate(user=self.host)
        payload = {
            "title": "Data Structures Lecture 4",
            "range_m": 45,
            "timeout_minutes": 90,
            "rotation_seconds": 30,
            "collect_name": True,
            "collect_id": True,
            "id_label": "UG Number",
            "latitude": "51.508000",
            "longitude": "-0.128000",
        }
        response = self.client.post(reverse('session-list-create'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session", response.data)
        # MUST NOT leak code_secret
        self.assertNotIn("code_secret", response.data["session"])
        self.assertEqual(response.data["session"]["title"], "Data Structures Lecture 4")
        self.assertEqual(response.data["session"]["range_m"], 45)

    def test_5_host_fetches_qr_and_non_host_forbidden(self):
        """Test 5: Host fetches /qr -> returns code; non-host -> 403"""
        qr_url = reverse('session-qr', kwargs={'pk': self.session.id})

        # Host fetches QR -> 200
        self.client.force_authenticate(user=self.host)
        response = self.client.get(qr_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("code", response.data)
        self.assertIn("rotation_seconds", response.data)
        self.assertIn("server_time", response.data)
        self.assertIn("expires_at", response.data)
        self.assertEqual(len(response.data["code"]), 8)

        # Non-host attendee fetches QR -> 403
        self.client.force_authenticate(user=self.attendee)
        non_host_resp = self.client.get(qr_url)
        self.assertEqual(non_host_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(non_host_resp.data["error"]["code"], "FORBIDDEN")

    def test_6_attendance_valid_code_inside_geofence(self):
        """Test 6: Attendance with valid code inside geofence -> 201 present"""
        self.client.force_authenticate(user=self.attendee)
        valid_code = self.session.get_current_qr_code()

        payload = {
            "session_id": str(self.session.id),
            "code": valid_code,
            "latitude": "51.507410",  # ~1 metre away from lecture hall
            "longitude": "-0.127810",
            "mocked": False,
            "name": "Alex Turner",
            "id_number": "UG2023-9988",
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("attendance", response.data)
        self.assertEqual(response.data["attendance"]["status"], "present")
        self.assertEqual(response.data["attendance"]["name"], "Alex Turner")
        self.assertEqual(response.data["attendance"]["id_number"], "UG2023-9988")

    def test_7_attendance_outside_geofence(self):
        """Test 7: Attendance with valid code outside geofence -> 403 OUTSIDE_GEOFENCE"""
        self.client.force_authenticate(user=self.attendee)
        valid_code = self.session.get_current_qr_code()

        # 51.512000 is ~500m away (range is 50m)
        payload = {
            "session_id": str(self.session.id),
            "code": valid_code,
            "latitude": "51.512000",
            "longitude": "-0.127800",
            "mocked": False,
            "name": "Alex Turner",
            "id_number": "UG2023-9988",
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "OUTSIDE_GEOFENCE")
        self.assertIn("detail", response.data["error"])
        self.assertGreater(response.data["error"]["detail"]["distance_m"], 50)

    def test_8_attendance_invalid_or_old_code(self):
        """Test 8: Attendance with an old/invalid code -> 422 INVALID_CODE"""
        self.client.force_authenticate(user=self.attendee)

        payload = {
            "session_id": str(self.session.id),
            "code": "deadbeef",  # Invalid fake code
            "latitude": str(self.base_lat),
            "longitude": str(self.base_lng),
            "mocked": False,
            "name": "Alex Turner",
            "id_number": "UG2023-9988",
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["error"]["code"], "INVALID_CODE")

    def test_9_attendance_after_session_expiry_or_ended(self):
        """Test 9: Attendance after expires_at -> 410 SESSION_CLOSED"""
        # Create an already expired session
        expired_session = Session.objects.create(
            host=self.host,
            title="Past Lecture",
            range_m=100,
            rotation_seconds=30,
            latitude=self.base_lat,
            longitude=self.base_lng,
            expires_at=timezone.now() - timedelta(minutes=5),
            is_active=True
        )

        self.client.force_authenticate(user=self.attendee)
        payload = {
            "session_id": str(expired_session.id),
            "code": expired_session.get_current_qr_code(),
            "latitude": str(self.base_lat),
            "longitude": str(self.base_lng),
            "mocked": False,
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["error"]["code"], "SESSION_CLOSED")

    def test_10_duplicate_attendance_same_session(self):
        """Test 10: Duplicate attendance (same user + session) -> 409 ALREADY_MARKED"""
        self.client.force_authenticate(user=self.attendee)
        valid_code = self.session.get_current_qr_code()

        payload = {
            "session_id": str(self.session.id),
            "code": valid_code,
            "latitude": str(self.base_lat),
            "longitude": str(self.base_lng),
            "mocked": False,
            "name": "Alex Turner",
            "id_number": "UG2023-9988",
        }

        # First submission -> 201
        first_resp = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(first_resp.status_code, status.HTTP_201_CREATED)

        # Second submission -> 409
        second_resp = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(second_resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second_resp.data["error"]["code"], "ALREADY_MARKED")

    def test_11_mocked_location_rejected(self):
        """Test 11: Attendance with mocked=True -> 400 MOCK_LOCATION"""
        self.client.force_authenticate(user=self.attendee)
        valid_code = self.session.get_current_qr_code()

        payload = {
            "session_id": str(self.session.id),
            "code": valid_code,
            "latitude": str(self.base_lat),
            "longitude": str(self.base_lng),
            "mocked": True,  # Android mock location enabled!
            "name": "Alex Turner",
            "id_number": "UG2023-9988",
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "MOCK_LOCATION")

    def test_12_missing_required_fields(self):
        """Test 12: Missing required name/id when collection is on -> 400 MISSING_FIELDS"""
        self.client.force_authenticate(user=self.attendee)
        valid_code = self.session.get_current_qr_code()

        # Omit both name and id_number when session requires both
        payload = {
            "session_id": str(self.session.id),
            "code": valid_code,
            "latitude": str(self.base_lat),
            "longitude": str(self.base_lng),
            "mocked": False,
            "name": "",
            "id_number": "",
        }
        response = self.client.post(reverse('attendance-submit'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "MISSING_FIELDS")
