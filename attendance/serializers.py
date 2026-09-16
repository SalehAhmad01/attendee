from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from .models import Session, Attendance

class SessionCreateSerializer(serializers.ModelSerializer):
    timeout_minutes = serializers.IntegerField(write_only=True, min_value=1, max_value=1440, default=60)
    rotation_seconds = serializers.IntegerField(required=False, default=30, min_value=5, max_value=300)

    class Meta:
        model = Session
        fields = (
            'id',
            'title',
            'range_m',
            'timeout_minutes',
            'rotation_seconds',
            'collect_name',
            'collect_id',
            'id_label',
            'latitude',
            'longitude',
            'expires_at',
            'is_active',
            'created_at',
        )
        read_only_fields = ('id', 'expires_at', 'is_active', 'created_at')

    def create(self, validated_data):
        timeout_minutes = validated_data.pop('timeout_minutes', 60)
        expires_at = timezone.now() + timedelta(minutes=timeout_minutes)
        host = self.context['request'].user
        session = Session.objects.create(
            host=host,
            expires_at=expires_at,
            **validated_data
        )
        return session

class SessionDetailSerializer(serializers.ModelSerializer):
    attendee_count = serializers.SerializerMethodField()
    host_email = serializers.EmailField(source='host.email', read_only=True)

    class Meta:
        model = Session
        fields = (
            'id',
            'title',
            'range_m',
            'rotation_seconds',
            'collect_name',
            'collect_id',
            'id_label',
            'latitude',
            'longitude',
            'expires_at',
            'is_active',
            'created_at',
            'attendee_count',
            'host_email',
        )
        # code_secret is STRICTLY EXCLUDED

    def get_attendee_count(self, obj):
        return obj.attendances.filter(status='present').count()

class AttendanceDetailSerializer(serializers.ModelSerializer):
    attendee_email = serializers.EmailField(source='attendee.email', read_only=True)
    session_title = serializers.CharField(source='session.title', read_only=True)

    class Meta:
        model = Attendance
        fields = (
            'id',
            'session',
            'session_title',
            'attendee',
            'attendee_email',
            'name',
            'id_number',
            'captured_lat',
            'captured_lng',
            'distance_m',
            'status',
            'created_at',
        )
        read_only_fields = fields

class AttendanceSubmitSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=True)
    code = serializers.CharField(required=True, max_length=32)
    latitude = serializers.DecimalField(required=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(required=True, max_digits=9, decimal_places=6)
    mocked = serializers.BooleanField(required=False, default=False)
    name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    id_number = serializers.CharField(required=False, allow_blank=True, max_length=40)
