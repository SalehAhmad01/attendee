from django.urls import path
from .views import (
    SessionListCreateView,
    SessionDetailView,
    SessionQRView,
    SessionEndView,
    SessionAttendanceListView,
    AttendanceSubmitView,
    MyAttendanceListView,
)

urlpatterns = [
    # Sessions
    path('sessions', SessionListCreateView.as_view(), name='session-list-create'),
    path('sessions/', SessionListCreateView.as_view(), name='session-list-create-slash'),
    path('sessions/<uuid:pk>', SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<uuid:pk>/', SessionDetailView.as_view(), name='session-detail-slash'),
    path('sessions/<uuid:pk>/qr', SessionQRView.as_view(), name='session-qr'),
    path('sessions/<uuid:pk>/qr/', SessionQRView.as_view(), name='session-qr-slash'),
    path('sessions/<uuid:pk>/end', SessionEndView.as_view(), name='session-end'),
    path('sessions/<uuid:pk>/end/', SessionEndView.as_view(), name='session-end-slash'),
    path('sessions/<uuid:pk>/attendance', SessionAttendanceListView.as_view(), name='session-attendance-list'),
    path('sessions/<uuid:pk>/attendance/', SessionAttendanceListView.as_view(), name='session-attendance-list-slash'),

    # Attendance
    path('attendance', AttendanceSubmitView.as_view(), name='attendance-submit'),
    path('attendance/', AttendanceSubmitView.as_view(), name='attendance-submit-slash'),
    path('attendance/mine', MyAttendanceListView.as_view(), name='attendance-mine'),
    path('attendance/mine/', MyAttendanceListView.as_view(), name='attendance-mine-slash'),
]
