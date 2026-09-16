from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from attendance.models import Session

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial demo users and attendance sessions for development and testing'

    def handle(self, *args, **options):
        self.stdout.write("Seeding Geo-QR demo data...")

        # 1. Host User (Professor)
        host_email = "host@geoqr.edu"
        host, created = User.objects.get_or_create(
            email=host_email,
            defaults={
                'full_name': 'Prof. Katherine Vance',
                'is_staff': True,
            }
        )
        host.set_password("Host1234!")
        host.save()
        status_str = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{status_str} Host: {host_email} (password: Host1234!)"))

        # 2. Student User (Attendee)
        student_email = "student@geoqr.edu"
        student, created = User.objects.get_or_create(
            email=student_email,
            defaults={
                'full_name': 'Marcus Aurelius Chen',
            }
        )
        student.set_password("Student1234!")
        student.save()
        status_str = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{status_str} Attendee: {student_email} (password: Student1234!)"))

        # 3. Active Demo Session
        # Default geofence centre: Oxford Street / University Square
        session_title = "CS302 Distributed Systems (Demo Session)"
        session, created = Session.objects.get_or_create(
            host=host,
            title=session_title,
            defaults={
                'range_m': 60,
                'rotation_seconds': 30,
                'collect_name': True,
                'collect_id': True,
                'id_label': 'UG Student ID',
                'latitude': Decimal("51.517500"),
                'longitude': Decimal("-0.133200"),
                'expires_at': timezone.now() + timedelta(hours=2),
                'is_active': True,
            }
        )
        if not created:
            session.expires_at = timezone.now() + timedelta(hours=2)
            session.is_active = True
            session.save()

        self.stdout.write(self.style.SUCCESS(f"Active Session ID: {session.id} (Range: {session.range_m}m)"))
        self.stdout.write(self.style.SUCCESS("Demo database successfully seeded!"))
