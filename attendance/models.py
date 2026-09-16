import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from .utils import generate_code_secret, current_window, code_for_window

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_sessions'
    )
    title = models.CharField(max_length=120)
    range_m = models.PositiveIntegerField(help_text="Geofence radius in metres")
    rotation_seconds = models.PositiveIntegerField(default=30, help_text="QR refresh window")
    collect_name = models.BooleanField(default=True)
    collect_id = models.BooleanField(default=True)
    id_label = models.CharField(max_length=40, default="ID / UG number")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    code_secret = models.CharField(max_length=64, default=generate_code_secret)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.id})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def get_current_qr_code(self) -> str:
        """Returns the rotating code for the current window."""
        window = current_window(self.rotation_seconds)
        return code_for_window(self.code_secret, window)

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('rejected', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='attendances')
    attendee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendances')
    name = models.CharField(max_length=100, blank=True, default='')
    id_number = models.CharField(max_length=40, blank=True, default='')
    captured_lat = models.DecimalField(max_digits=9, decimal_places=6)
    captured_lng = models.DecimalField(max_digits=9, decimal_places=6)
    distance_m = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='present')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'attendee')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.attendee.email} - {self.session.title} ({self.status})"
