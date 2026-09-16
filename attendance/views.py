from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal

from .models import Session, Attendance
from .serializers import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    AttendanceDetailSerializer,
    AttendanceSubmitSerializer,
)
from .utils import is_code_valid, haversine_m

class SessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SessionCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid session parameters.",
                        "detail": serializer.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        session = serializer.save()
        return Response(
            {"session": SessionDetailSerializer(session).data},
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        mine = request.query_params.get('mine')
        if mine == 'host':
            sessions = Session.objects.filter(host=request.user)
        else:
            sessions = Session.objects.filter(is_active=True, expires_at__gt=timezone.now())

        serializer = SessionDetailSerializer(sessions, many=True)
        return Response({"sessions": serializer.data}, status=status.HTTP_200_OK)

class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = Session.objects.get(pk=pk)
        except (Session.DoesNotExist, ValueError):
            return Response(
                {
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "Session not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        data = SessionDetailSerializer(session).data
        return Response(
            {
                "session": data,
                "attendee_count": session.attendances.filter(status='present').count(),
            },
            status=status.HTTP_200_OK,
        )

class SessionQRView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = Session.objects.get(pk=pk)
        except (Session.DoesNotExist, ValueError):
            return Response(
                {
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "Session not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Host only permission
        if session.host != request.user:
            return Response(
                {
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Only the host can retrieve the rotating QR code.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not session.is_active or session.is_expired:
            return Response(
                {
                    "error": {
                        "code": "SESSION_CLOSED",
                        "message": "Session is inactive or expired.",
                    }
                },
                status=status.HTTP_410_GONE,
            )

        return Response(
            {
                "code": session.get_current_qr_code(),
                "rotation_seconds": session.rotation_seconds,
                "server_time": timezone.now().isoformat(),
                "expires_at": session.expires_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

class SessionEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            session = Session.objects.get(pk=pk)
        except (Session.DoesNotExist, ValueError):
            return Response(
                {
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "Session not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if session.host != request.user:
            return Response(
                {
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Only the host can end this session.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        session.is_active = False
        session.save(update_fields=['is_active'])

        return Response(
            {"session": SessionDetailSerializer(session).data},
            status=status.HTTP_200_OK,
        )

class SessionAttendanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = Session.objects.get(pk=pk)
        except (Session.DoesNotExist, ValueError):
            return Response(
                {
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "Session not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if session.host != request.user:
            return Response(
                {
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Only the host can view attendees.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        attendances = session.attendances.all()
        serializer = AttendanceDetailSerializer(attendances, many=True)
        return Response({"attendees": serializer.data}, status=status.HTTP_200_OK)

class AttendanceSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        submit_serializer = AttendanceSubmitSerializer(data=request.data)
        if not submit_serializer.is_valid():
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid request payload.",
                        "detail": submit_serializer.errors,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = submit_serializer.validated_data
        session_id = data['session_id']
        code = data['code']
        captured_lat = float(data['latitude'])
        captured_lng = float(data['longitude'])
        is_mocked = data.get('mocked', False)
        name = data.get('name', '').strip()
        id_number = data.get('id_number', '').strip()

        # Step 1: Session exists?
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "The requested attendance session does not exist.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Step 2: is_active and now < expires_at?
        if not session.is_active or session.is_expired:
            return Response(
                {
                    "error": {
                        "code": "SESSION_CLOSED",
                        "message": "This attendance session is expired or has been ended by the host.",
                    }
                },
                status=status.HTTP_410_GONE,
            )

        # Step 3: is_code_valid?
        if not is_code_valid(session.code_secret, session.rotation_seconds, code):
            return Response(
                {
                    "error": {
                        "code": "INVALID_CODE",
                        "message": "The scanned QR code is expired or invalid. Please scan the current code.",
                    }
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Step 4: mocked == true?
        if is_mocked:
            return Response(
                {
                    "error": {
                        "code": "MOCK_LOCATION",
                        "message": "Mock/fake locations are strictly forbidden.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 5: Required fields present per collect_name / collect_id?
        missing_fields = []
        if session.collect_name and not name:
            missing_fields.append("name")
        if session.collect_id and not id_number:
            missing_fields.append(f"id_number ({session.id_label})")

        if missing_fields:
            return Response(
                {
                    "error": {
                        "code": "MISSING_FIELDS",
                        "message": f"Missing required fields: {', '.join(missing_fields)}",
                        "detail": {"missing": missing_fields},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Step 6: Compute distance_m; > range_m?
        host_lat = float(session.latitude)
        host_lng = float(session.longitude)
        distance_m = haversine_m(host_lat, host_lng, captured_lat, captured_lng)

        if distance_m > session.range_m:
            return Response(
                {
                    "error": {
                        "code": "OUTSIDE_GEOFENCE",
                        "message": "You are outside the class location.",
                        "detail": {
                            "distance_m": round(distance_m, 2),
                            "range_m": session.range_m,
                        },
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Step 7: Duplicate (session, attendee)?
        if Attendance.objects.filter(session=session, attendee=request.user).exists():
            return Response(
                {
                    "error": {
                        "code": "ALREADY_MARKED",
                        "message": "You have already recorded attendance for this session.",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Step 8: Save status="present" -> 201
        attendance = Attendance.objects.create(
            session=session,
            attendee=request.user,
            name=name if session.collect_name else '',
            id_number=id_number if session.collect_id else '',
            captured_lat=Decimal(str(round(captured_lat, 6))),
            captured_lng=Decimal(str(round(captured_lng, 6))),
            distance_m=Decimal(str(round(distance_m, 2))),
            status='present',
        )

        return Response(
            {"attendance": AttendanceDetailSerializer(attendance).data},
            status=status.HTTP_201_CREATED,
        )

class MyAttendanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = Attendance.objects.filter(attendee=request.user)
        serializer = AttendanceDetailSerializer(records, many=True)
        return Response({"records": serializer.data}, status=status.HTTP_200_OK)
