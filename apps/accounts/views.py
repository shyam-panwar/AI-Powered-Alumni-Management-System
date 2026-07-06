from django.utils import timezone
from datetime import timedelta
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

try:
    from django_ratelimit.decorators import ratelimit
    from django_ratelimit.exceptions import Ratelimited
    HAS_RATELIMIT = True
except ImportError:
    HAS_RATELIMIT = False

from .models import EmailOTP
from .serializers import (
    UserRegistrationSerializer,
    OTPVerificationSerializer,
    LoginRequestSerializer,
    LoginOTPSerializer,
    UserProfileSerializer,
)
from .validators import generate_otp


class RegisterView(APIView):
    """
    POST /api/accounts/register/
    Register a new user and send OTP to their email.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {'message': 'OTP sent to your email. Please verify to complete registration.'},
            status=status.HTTP_201_CREATED,
        )

    if HAS_RATELIMIT:
        post = method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=False))(post)


class VerifyRegistrationOTPView(APIView):
    """
    POST /api/accounts/verify-otp/
    Verify the registration OTP and activate the account.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {'message': 'Email verified successfully. You can now log in.'},
            status=status.HTTP_200_OK,
        )


class LoginRequestView(APIView):
    """
    POST /api/accounts/login/
    Validate credentials and send a login OTP.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = serializer.save()
        
        # --- DEMO MODE BYPASS ---
        if isinstance(result, dict) and 'access' in result:
            response = Response(result, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=result['access'],
                httponly=True,
                secure=not django_settings.DEBUG,
                samesite='Lax'
            )
            return response

        # --- DEV MODE: include OTP in response so devs don't need real email ---
        response_data = {'message': 'OTP sent to your registered email.'}
        if django_settings.DEBUG:
            email = request.data.get('email', '').strip().lower()
            dev_otp = (
                EmailOTP.objects
                .filter(email=email, purpose=EmailOTP.LOGIN, is_used=False)
                .order_by('-created_at')
                .values_list('otp_code', flat=True)
                .first()
            )
            if dev_otp:
                response_data['dev_otp'] = dev_otp

        return Response(response_data, status=status.HTTP_200_OK)

    if HAS_RATELIMIT:
        post = method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=False))(post)


class LoginVerifyOTPView(APIView):
    """
    POST /api/accounts/login/verify/
    Verify login OTP and return JWT tokens + set httponly cookie.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_data = serializer.save()
        response = Response(token_data, status=status.HTTP_200_OK)

        # Set httponly cookie so JWTAuthMiddleware can read it for page-level auth
        response.set_cookie(
            key='access_token',
            value=token_data['access'],
            httponly=True,
            secure=not request.META.get('SERVER_NAME', '').startswith('localhost'),
            samesite='Lax',
            max_age=60 * 60,  # 1 hour — matches ACCESS_TOKEN_LIFETIME
        )
        return response


class ResendOTPView(APIView):
    """
    POST /api/accounts/resend-otp/
    Resend OTP with a 60-second rate limit.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        purpose = request.data.get('purpose', '').strip()

        if not email or not purpose:
            return Response(
                {'message': 'email and purpose are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_purposes = [EmailOTP.REGISTRATION, EmailOTP.LOGIN, EmailOTP.VERIFY]
        if purpose not in valid_purposes:
            return Response(
                {'message': f'purpose must be one of: {", ".join(valid_purposes)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate-limit: reject if an OTP was sent in the last 60 seconds
        one_minute_ago = timezone.now() - timedelta(seconds=60)
        recent_otp = EmailOTP.objects.filter(
            email=email,
            purpose=purpose,
            created_at__gte=one_minute_ago,
        ).exists()

        if recent_otp:
            return Response(
                {'message': 'Please wait 60 seconds before requesting a new OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Find the user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'message': 'No account found with this email.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Invalidate all previous unused OTPs for this email + purpose
        EmailOTP.objects.filter(
            email=email, purpose=purpose, is_used=False
        ).update(is_used=True)

        # Create and send new OTP
        otp_code = generate_otp()
        EmailOTP.objects.create(
            user=user,
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        from .tasks import send_otp_email
        try:
            from .tasks import send_otp_email_task
            send_otp_email_task.delay(user.id, email, otp_code, purpose)
        except Exception:
            send_otp_email(user.id, email, otp_code, purpose)

        return Response(
            {'message': 'A new OTP has been sent to your email.'},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/accounts/logout/
    Blacklist the refresh token and clear the httponly cookie.
    Accepts unauthenticated requests so stale/expired tokens don't block logout.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass  # Already expired/blacklisted — that's fine, just clear and go

        response = Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        return response


class MeView(APIView):
    """
    GET /api/accounts/me/
    Return the authenticated user's profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── Template / Page Views ──────────────────────────────────────────────────────

from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.conf import settings as django_settings


class HomeView(TemplateView):
    template_name = 'home.html'

    def dispatch(self, request, *args, **kwargs):
        from utils.auth_helpers import get_user_from_token, get_dashboard_url
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if user:
            return redirect(get_dashboard_url(user))
        return super().dispatch(request, *args, **kwargs)


class ChooseRoleView(TemplateView):
    template_name = 'accounts/choose_role.html'


class RegisterPageView(TemplateView):
    template_name = 'accounts/register.html'


class VerifyOTPPageView(TemplateView):
    template_name = 'accounts/verify_otp.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # In DEBUG mode, surface the latest OTP so devs don't need real email
        if django_settings.DEBUG:
            email = self.request.GET.get('email', '').strip().lower()
            purpose = self.request.GET.get('purpose', 'registration')
            if email:
                otp = (
                    EmailOTP.objects
                    .filter(email=email, purpose=purpose, is_used=False)
                    .order_by('-created_at')
                    .first()
                )
                ctx['dev_otp'] = otp.otp_code if otp else None
        return ctx


class LoginPageView(TemplateView):
    template_name = 'accounts/login.html'


class ProfileEditPageView(TemplateView):
    template_name = 'accounts/profile_edit.html'


# ── JWT-protected page mixin ──────────────────────────────────────────────────

class JWTLoginRequiredMixin:
    """Validates httponly access_token cookie; redirects to login if missing/invalid."""

    def dispatch(self, request, *args, **kwargs):
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next={request.path}')
        # Redirect to profile setup if profile not complete (skip for setup page itself)
        if not user.is_profile_complete and request.path not in ('/profile/setup/', '/auth/login/', '/auth/logout/'):
            return redirect('/profile/setup/')
        request.user = user
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user'] = self.request.user
        ctx['user_role'] = self.request.user.role
        return ctx


class ProfileSetupPageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile_setup.html'

    def dispatch(self, request, *args, **kwargs):
        # Bypass the profile-complete redirect for this view specifically
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next={request.path}')
        request.user = user
        return TemplateView.dispatch(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user'] = self.request.user
        ctx['user_role'] = self.request.user.role
        return ctx


class EditProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/edit_profile.html'


class BrowseAlumniPageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/browse_alumni.html'

    def dispatch(self, request, *args, **kwargs):
        # Redirect old /alumni/ URL to the new /connect/ page
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next=/connect/')
        return redirect('/connect/')


class PublicAlumniProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/alumni_profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['alumni_user_id'] = kwargs.get('user_id')
        return ctx


class StudentProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/student_profile.html'

    def dispatch(self, request, *args, **kwargs):
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next={request.path}')
        if user.role != 'student':
            return redirect(f'/dashboard/{user.role}/')
        request.user = user
        return TemplateView.dispatch(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user'] = self.request.user
        ctx['user_role'] = 'student'
        return ctx


class PublicStudentProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/public_student_profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['student_id'] = self.kwargs.get('user_id')
        from utils.auth_helpers import get_user_from_token
        token = self.request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        ctx['viewer_role'] = user.role if user else ''
        return ctx


# ── Student Profile Section Views ─────────────────────────────────────────────

from django.http import Http404, HttpResponse
from django.contrib.auth import get_user_model
from .models import (
    StudentEducation, StudentProject, StudentInternship,
    StudentCertification, StudentAward, StudentCompetitiveExam,
    StudentLanguage, StudentEmployment,
)
from .serializers import (
    StudentEducationSerializer, StudentProjectSerializer,
    StudentInternshipSerializer, StudentCertificationSerializer,
    StudentAwardSerializer, StudentCompetitiveExamSerializer,
    StudentLanguageSerializer, StudentEmploymentSerializer,
    FullStudentProfileSerializer,
)
from utils.permissions import IsStudent


def _make_list_view(Model, Serializer):
    """Factory that returns a list+create APIView class for a given model."""
    class ListView(APIView):
        permission_classes = [IsAuthenticated, IsStudent]

        def get(self, request):
            qs = Model.objects.filter(user=request.user)
            return Response(Serializer(qs, many=True).data)

        def post(self, request):
            s = Serializer(data=request.data)
            if s.is_valid():
                s.save(user=request.user)
                return Response(s.data, status=status.HTTP_201_CREATED)
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    return ListView


def _make_detail_view(Model, Serializer):
    """Factory that returns a retrieve+patch+delete APIView class."""
    class DetailView(APIView):
        permission_classes = [IsAuthenticated, IsStudent]

        def _get_obj(self, pk, user):
            try:
                return Model.objects.get(pk=pk, user=user)
            except Model.DoesNotExist:
                raise Http404

        def get(self, request, pk):
            return Response(Serializer(self._get_obj(pk, request.user)).data)

        def patch(self, request, pk):
            obj = self._get_obj(pk, request.user)
            s = Serializer(obj, data=request.data, partial=True)
            if s.is_valid():
                s.save()
                return Response(s.data)
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

        def delete(self, request, pk):
            self._get_obj(pk, request.user).delete()
            return Response({'message': 'Deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

    return DetailView


StudentEducationListView   = _make_list_view(StudentEducation,   StudentEducationSerializer)
StudentEducationDetailView = _make_detail_view(StudentEducation, StudentEducationSerializer)

StudentProjectListView   = _make_list_view(StudentProject,   StudentProjectSerializer)
StudentProjectDetailView = _make_detail_view(StudentProject, StudentProjectSerializer)

StudentInternshipListView   = _make_list_view(StudentInternship,   StudentInternshipSerializer)
StudentInternshipDetailView = _make_detail_view(StudentInternship, StudentInternshipSerializer)

StudentCertificationListView   = _make_list_view(StudentCertification,   StudentCertificationSerializer)
StudentCertificationDetailView = _make_detail_view(StudentCertification, StudentCertificationSerializer)

StudentAwardListView   = _make_list_view(StudentAward,   StudentAwardSerializer)
StudentAwardDetailView = _make_detail_view(StudentAward, StudentAwardSerializer)

StudentCompetitiveExamListView   = _make_list_view(StudentCompetitiveExam,   StudentCompetitiveExamSerializer)
StudentCompetitiveExamDetailView = _make_detail_view(StudentCompetitiveExam, StudentCompetitiveExamSerializer)

StudentLanguageListView   = _make_list_view(StudentLanguage,   StudentLanguageSerializer)
StudentLanguageDetailView = _make_detail_view(StudentLanguage, StudentLanguageSerializer)

StudentEmploymentListView   = _make_list_view(StudentEmployment,   StudentEmploymentSerializer)
StudentEmploymentDetailView = _make_detail_view(StudentEmployment, StudentEmploymentSerializer)


class FullStudentProfileView(APIView):
    """GET /api/accounts/profile/student/full/ or /api/accounts/profile/student/full/<user_id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        User = get_user_model()
        if user_id:
            try:
                target = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            target = request.user

        if target.role != 'student':
            return Response({'error': 'Not a student'}, status=status.HTTP_404_NOT_FOUND)

        return Response(FullStudentProfileSerializer(target).data)


# ── Connect Page View ─────────────────────────────────────────────────────────

class ConnectPageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'connect/connect.html'

    def dispatch(self, request, *args, **kwargs):
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next={request.path}')
        # Alumni and faculty redirect to their own dashboard
        if user.role in ('alumni', 'faculty'):
            return redirect(f'/dashboard/{user.role}/')
        request.user = user
        return TemplateView.dispatch(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user'] = self.request.user
        ctx['user_role'] = 'student'
        return ctx


# ── Alumni Profile Page View ──────────────────────────────────────────────────

class AlumniProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/alumni_profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['alumni_user_id'] = kwargs.get('user_id')
        return ctx


# ── Faculty Profile Page View ─────────────────────────────────────────────────

class FacultyProfilePageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/faculty_profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['faculty_user_id'] = kwargs.get('user_id')
        return ctx


# ── My Network / Connections Page ────────────────────────────────────────────

class ConnectionsPageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/connections.html'


# ── Alumni Profile Page View (placeholder for /profile/alumni/) ───────────────

class AlumniProfileSelfPageView(JWTLoginRequiredMixin, TemplateView):
    template_name = 'accounts/alumni_profile_self.html'

    def dispatch(self, request, *args, **kwargs):
        from utils.auth_helpers import get_user_from_token
        token = request.COOKIES.get('access_token', '')
        user = get_user_from_token(token)
        if not user:
            return redirect(f'/auth/login/?next={request.path}')
        if user.role != 'alumni':
            return redirect(f'/dashboard/{user.role}/')
        return redirect('/profile/edit/')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user'] = self.request.user
        ctx['user_role'] = 'alumni'
        return ctx


# ── Faculty Profile Self Page View (placeholder for /profile/faculty/) ────────

class FacultyEditProfilePageView(TemplateView):
    template_name = 'accounts/faculty_edit_profile.html'

    def dispatch(self, request, *args, **kwargs):
        token = request.COOKIES.get('access_token')
        from utils.auth_helpers import get_user_from_token
        user = get_user_from_token(token)
        if not user or user.role != 'faculty':
            from django.shortcuts import redirect
            return redirect(f'/auth/login/?next={request.path}')
        request.portal_user = user
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = self.request.COOKIES.get('access_token')
        from utils.auth_helpers import get_user_from_token
        user = get_user_from_token(token)
        ctx['user_role'] = 'faculty'
        return ctx


# ── Faculty List API ──────────────────────────────────────────────────────────

class FacultyListView(APIView):
    """GET /api/accounts/faculty/ — paginated list of verified faculty"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import FacultyProfile
        from .serializers import FacultyPublicSerializer

        qs = FacultyProfile.objects.select_related('user').filter(
            user__is_verified=True, user__is_active=True, user__role='faculty'
        ).order_by('-user__date_joined')

        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(department__icontains=search) |
                Q(designation__icontains=search)
            )

        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = 12
        total = qs.count()
        start = (page - 1) * page_size
        profiles = qs[start:start + page_size]

        results = []
        for p in profiles:
            u = p.user
            pic_url = u.profile_pic.url if u.profile_pic else None
            results.append({
                'user_id': u.id,
                'full_name': u.full_name,
                'first_name': u.first_name,
                'profile_pic': pic_url,
                'college': u.college,
                'batch_year': u.batch_year,
                'department': p.department,
                'designation': p.designation,
                'subjects': p.subjects_taught,
                'bio': p.bio,
                'average_rating': float(p.average_rating),
            })

        return Response({
            'results': results,
            'total': total,
            'page': page,
            'has_next': (start + page_size) < total,
        })


# ── Public Faculty Profile API ────────────────────────────────────────────────

# ── DEV ONLY: Role Switcher ───────────────────────────────────────────────────

from django.views import View


# ── Public Faculty Profile API ────────────────────────────────────────────────

class PublicFacultyProfileView(APIView):
    """GET /api/accounts/faculty/{user_id}/ — public faculty profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id, role='faculty', is_verified=True, is_active=True)
            from .models import FacultyProfile
            profile = user.faculty_profile
        except (User.DoesNotExist, Exception):
            return Response({'detail': 'Faculty not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Track profile view
        from .profile_views import _record_profile_view
        _record_profile_view(request.user, user)

        pic_url = user.profile_pic.url if user.profile_pic else None
        return Response({
            'user_id': user.id,
            'full_name': user.full_name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'profile_pic': pic_url,
            'college': user.college,
            'batch_year': user.batch_year,
            'department': profile.department,
            'designation': profile.designation,
            'subjects': profile.subjects_taught,
            'bio': profile.bio,
            'employee_id': profile.employee_id,
        })

class FacultyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'faculty':
            return Response({'error': 'Faculty only.'}, status=403)
        try:
            profile = request.user.faculty_profile
        except Exception:
            from apps.accounts.models import FacultyProfile
            profile = FacultyProfile.objects.create(user=request.user)

        # Build profile pic URL
        pic_url = None
        if request.user.profile_pic:
            try:
                pic_url = request.build_absolute_uri(request.user.profile_pic.url)
            except Exception:
                pass

        data = {
            'id': profile.id,
            'user_id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone', '') or '',
            'location': getattr(request.user, 'location', '') or '',
            'gender': getattr(request.user, 'gender', '') or '',
            'profile_pic': pic_url,

            # Professional
            'college_name': profile.college_name,
            'department': profile.department,
            'designation': profile.designation,
            'employee_id': profile.employee_id,
            'years_of_experience': profile.years_of_experience,
            'teaching_mode': profile.teaching_mode,

            # Academic
            'subjects_taught': profile.subjects_taught or [],
            'specialization': profile.specialization,
            'highest_qualification': profile.highest_qualification,
            'qualification_university': profile.qualification_university,
            'research_publications_count': profile.research_publications_count,

            # Skills
            'technical_skills': profile.technical_skills or [],
            'soft_skills': profile.soft_skills or [],
            'tools_technologies': profile.tools_technologies or [],
            'languages_known': profile.languages_known or [],

            # Sessions
            'available_for_sessions': profile.available_for_sessions,
            'session_types_offered': profile.session_types_offered or [],
            'preferred_session_mode': profile.preferred_session_mode,
            'office_hours': profile.office_hours,
            'max_students_per_session': profile.max_students_per_session,
            'preferred_session_duration': profile.preferred_session_duration,

            # Social
            'linkedin_url': profile.linkedin_url,
            'google_scholar_url': profile.google_scholar_url,
            'researchgate_url': profile.researchgate_url,
            'personal_website': profile.personal_website,
            'college_staff_page_url': profile.college_staff_page_url,

            # Bio
            'bio': profile.bio,

            # Bank
            'bank_details': profile.bank_details or {},
            'bank_verified': profile.bank_verified,

            # Stats
            'wallet_balance': str(profile.wallet_balance),
            'total_earned': str(profile.total_earned),
            'profile_completeness_score': profile.profile_completeness_score,
        }
        return Response(data)

    def patch(self, request):
        if request.user.role != 'faculty':
            return Response({'error': 'Faculty only.'}, status=403)
        try:
            profile = request.user.faculty_profile
        except Exception:
            from apps.accounts.models import FacultyProfile
            profile = FacultyProfile.objects.create(user=request.user)

        data = request.data

        # Update User model fields
        user_fields_changed = False
        if 'first_name' in data:
            request.user.first_name = data['first_name'].strip()
            user_fields_changed = True
        if 'last_name' in data:
            request.user.last_name = data['last_name'].strip()
            user_fields_changed = True
        if 'phone' in data and hasattr(request.user, 'phone'):
            request.user.phone = data['phone'].strip()
            user_fields_changed = True
        if 'location' in data and hasattr(request.user, 'location'):
            request.user.location = data['location'].strip()
            user_fields_changed = True
        if 'gender' in data and hasattr(request.user, 'gender'):
            request.user.gender = data['gender'].strip()
            user_fields_changed = True
        if user_fields_changed:
            request.user.save()

        # Update FacultyProfile fields
        profile_fields = [
            'college_name', 'department', 'designation', 'employee_id',
            'years_of_experience', 'teaching_mode', 'subjects_taught',
            'specialization', 'highest_qualification', 'qualification_university',
            'research_publications_count', 'technical_skills', 'soft_skills',
            'tools_technologies', 'languages_known', 'available_for_sessions',
            'session_types_offered', 'preferred_session_mode', 'office_hours',
            'max_students_per_session', 'preferred_session_duration',
            'linkedin_url', 'google_scholar_url', 'researchgate_url',
            'personal_website', 'college_staff_page_url', 'bio',
        ]
        for field in profile_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    value = value.strip()
                setattr(profile, field, value)

        profile.save()  # triggers completeness recalculation

        return Response({
            'message': 'Profile updated successfully.',
            'profile_completeness_score': profile.profile_completeness_score,
        })

class FacultyBankDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'faculty':
            return Response({'error': 'Faculty only.'}, status=403)
        try:
            bd = request.user.faculty_profile.bank_details or {}
        except Exception:
            bd = {}
        # Mask account number for display
        masked = {}
        if bd:
            masked = bd.copy()
            acc = bd.get('account_number', '')
            if len(acc) > 4:
                masked['account_number'] = 'X' * (len(acc) - 4) + acc[-4:]
        return Response({'bank_details': masked, 'has_bank_details': bool(bd.get('account_number'))})

    def patch(self, request):
        if request.user.role != 'faculty':
            return Response({'error': 'Faculty only.'}, status=403)

        required_fields = ['account_holder_name', 'bank_name', 'account_number', 'ifsc_code']
        for field in required_fields:
            if not request.data.get(field, '').strip():
                return Response({'error': f'{field} is required.'}, status=400)

        acc = request.data.get('account_number', '').strip()
        confirm = request.data.get('confirm_account_number', '').strip()
        if confirm and acc != confirm:
            return Response({'error': 'Account numbers do not match.'}, status=400)

        bank_data = {
            'account_holder_name': request.data.get('account_holder_name', '').strip(),
            'bank_name': request.data.get('bank_name', '').strip(),
            'account_number': acc,
            'ifsc_code': request.data.get('ifsc_code', '').strip().upper(),
            'account_type': request.data.get('account_type', 'savings'),
        }

        try:
            profile = request.user.faculty_profile
            profile.bank_details = bank_data
            profile.save(update_fields=['bank_details'])
            return Response({'message': 'Bank details saved successfully.'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

from rest_framework.parsers import MultiPartParser, FormParser
class ProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if 'profile_pic' not in request.FILES:
            return Response({'error': 'No image file provided.'}, status=400)

        image = request.FILES['profile_pic']

        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if image.content_type not in allowed_types:
            return Response({'error': 'Only JPEG, PNG and WebP images are allowed.'}, status=400)

        # Validate file size (max 5MB)
        if image.size > 5 * 1024 * 1024:
            return Response({'error': 'Image must be under 5MB.'}, status=400)

        request.user.profile_pic = image
        request.user.save(update_fields=['profile_pic'])

        pic_url = request.build_absolute_uri(request.user.profile_pic.url)
        return Response({
            'message': 'Profile photo updated successfully.',
            'profile_pic_url': pic_url,
        })


class AlumniProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'alumni':
            return Response({'error': 'Alumni only.'}, status=403)
        try:
            profile = request.user.alumni_profile
        except Exception:
            from apps.accounts.models import AlumniProfile
            profile = AlumniProfile.objects.create(user=request.user)

        pic_url = None
        if request.user.profile_pic:
            try:
                pic_url = request.build_absolute_uri(request.user.profile_pic.url)
            except Exception:
                pass

        data = {
            'id': profile.id,
            'user_id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone', '') or '',
            'gender': getattr(request.user, 'gender', '') or '',
            'profile_pic': pic_url,

            # Professional
            'company': profile.company,
            'designation': profile.designation,
            'employment_type': profile.employment_type,
            'industry': profile.industry,
            'years_of_experience': profile.years_of_experience,
            'current_location': profile.current_location,
            'is_open_to_opportunities': profile.is_open_to_opportunities,

            # Academic
            'graduation_year': profile.graduation_year,
            'degree': profile.degree,
            'branch': profile.branch,
            'college_name': profile.college_name or getattr(request.user, 'college', '') or '',
            'cgpa_or_percentage': profile.cgpa_or_percentage,

            # Skills
            'technical_skills': profile.technical_skills or [],
            'domain_expertise': profile.domain_expertise or [],
            'tools_used': profile.tools_used or [],
            'soft_skills': profile.soft_skills or [],
            'languages_known': profile.languages_known or [],

            # Mentorship
            'available_for_mentorship': profile.available_for_mentorship,
            'mentorship_areas': profile.mentorship_areas or [],
            'preferred_session_mode': profile.preferred_session_mode,
            'preferred_session_duration': profile.preferred_session_duration,
            'max_students_per_week': profile.max_students_per_week,
            'session_price_range': profile.session_price_range,

            # Social
            'linkedin_url': profile.linkedin_url,
            'github_url': profile.github_url,
            'twitter_url': profile.twitter_url,
            'portfolio_url': profile.portfolio_url,
            'blog_url': profile.blog_url,

            # Bio
            'bio': profile.bio,
            'achievements': profile.achievements,
            'advice_for_students': profile.advice_for_students,

            # Verification
            'is_verified': profile.is_verified,
            'verification_status': profile.verification_status,
            'verification_document_url': profile.verification_document_url,
            'verification_note': profile.verification_note,

            # Bank
            'bank_details': profile.bank_details or {},
            'bank_verified': profile.bank_verified,

            # Stats
            'wallet_balance': str(profile.wallet_balance),
            'total_earned': str(profile.total_earned),
            'impact_score': profile.impact_score,
            'profile_completeness_score': profile.profile_completeness_score,
        }
        return Response(data)

    def patch(self, request):
        if request.user.role != 'alumni':
            return Response({'error': 'Alumni only.'}, status=403)
        try:
            profile = request.user.alumni_profile
        except Exception:
            from apps.accounts.models import AlumniProfile
            profile = AlumniProfile.objects.create(user=request.user)

        data = request.data

        # Update User model fields
        user_changed = False
        for field in ['first_name', 'last_name', 'phone', 'gender']:
            if field in data:
                val = data[field]
                if isinstance(val, str):
                    val = val.strip()
                if field in ['first_name', 'last_name', 'phone', 'gender']:
                    if hasattr(request.user, field) or field in ['first_name', 'last_name']:
                        setattr(request.user, field, val)
                        user_changed = True
        if user_changed:
            request.user.save()

        # Update AlumniProfile fields
        profile_fields = [
            'company', 'designation', 'employment_type', 'industry',
            'years_of_experience', 'current_location', 'is_open_to_opportunities',
            'graduation_year', 'degree', 'branch', 'college_name', 'cgpa_or_percentage',
            'technical_skills', 'domain_expertise', 'tools_used', 'soft_skills', 'languages_known',
            'available_for_mentorship', 'mentorship_areas', 'preferred_session_mode',
            'preferred_session_duration', 'max_students_per_week', 'session_price_range',
            'linkedin_url', 'github_url', 'twitter_url', 'portfolio_url', 'blog_url',
            'bio', 'achievements', 'advice_for_students',
        ]
        for field in profile_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    value = value.strip()
                setattr(profile, field, value)

        profile.save()

        return Response({
            'message': 'Profile updated successfully.',
            'profile_completeness_score': profile.profile_completeness_score,
        })


class AlumniBankDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'alumni':
            return Response({'error': 'Alumni only.'}, status=403)
        try:
            bd = request.user.alumni_profile.bank_details or {}
        except Exception:
            bd = {}
        masked = {}
        if bd:
            masked = bd.copy()
            acc = bd.get('account_number', '')
            if len(acc) > 4:
                masked['account_number'] = 'X' * (len(acc) - 4) + acc[-4:]
        return Response({'bank_details': masked, 'has_bank_details': bool(bd.get('account_number'))})

    def patch(self, request):
        if request.user.role != 'alumni':
            return Response({'error': 'Alumni only.'}, status=403)

        required = ['account_holder_name', 'bank_name', 'account_number', 'ifsc_code']
        for field in required:
            if not request.data.get(field, '').strip():
                return Response({'error': f'{field} is required.'}, status=400)

        acc = request.data.get('account_number', '').strip()
        confirm = request.data.get('confirm_account_number', '').strip()
        if confirm and acc != confirm:
            return Response({'error': 'Account numbers do not match.'}, status=400)

        bank_data = {
            'account_holder_name': request.data.get('account_holder_name', '').strip(),
            'bank_name': request.data.get('bank_name', '').strip(),
            'account_number': acc,
            'ifsc_code': request.data.get('ifsc_code', '').strip().upper(),
            'account_type': request.data.get('account_type', 'savings'),
        }

        try:
            profile = request.user.alumni_profile
            profile.bank_details = bank_data
            profile.save(update_fields=['bank_details'])
            return Response({'message': 'Bank details saved successfully.'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AlumniVerificationSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'alumni':
            return Response({'error': 'Alumni only.'}, status=403)

        linkedin_url = request.data.get('linkedin_url', '').strip()
        if not linkedin_url:
            return Response({'error': 'LinkedIn URL is required for verification.'}, status=400)

        try:
            profile = request.user.alumni_profile
            profile.verification_document_url = linkedin_url
            profile.verification_status = 'pending'
            profile.linkedin_url = linkedin_url
            profile.save(update_fields=['verification_document_url', 'verification_status', 'linkedin_url'])

            # Notify admin (create notification for admin users)
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                from apps.notifications.models import Notification
                admin_users = User.objects.filter(role='admin', is_active=True)
                for admin in admin_users:
                    Notification.objects.create(
                        recipient=admin,
                        notif_type='general',
                        title='New Alumni Verification Request',
                        message=f'{request.user.first_name} {request.user.last_name} has submitted their LinkedIn profile for verification.',
                        link='/admin-panel/alumni-verification/',
                    )
            except Exception:
                pass

            return Response({'message': 'Verification request submitted. Admin will review within 1-2 business days.'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AlumniEditProfilePageView(TemplateView):
    template_name = 'accounts/alumni_edit_profile.html'

    def dispatch(self, request, *args, **kwargs):
        token = request.COOKIES.get('access_token')
        from utils.auth_helpers import get_user_from_token
        user = get_user_from_token(token)
        if not user or user.role != 'alumni':
            from django.shortcuts import redirect
            return redirect('/auth/login/?next=/profile/alumni/edit/')
        request.portal_user = user
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = self.request.COOKIES.get('access_token')
        from utils.auth_helpers import get_user_from_token
        user = get_user_from_token(token)
        ctx['user_role'] = 'alumni'
        return ctx

