from django.contrib import admin
from .models import Session, Attendance

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'id', 'host', 'range_m', 'rotation_seconds', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'collect_name', 'collect_id')
    search_fields = ('title', 'host__email', 'id')
    readonly_fields = ('id', 'code_secret', 'created_at')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('session', 'attendee', 'name', 'id_number', 'distance_m', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('session__title', 'attendee__email', 'name', 'id_number')
    readonly_fields = ('id', 'created_at')
