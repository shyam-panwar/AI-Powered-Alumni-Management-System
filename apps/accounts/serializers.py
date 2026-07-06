from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP
from .validators import (
    validate_student_email,
    validate_alumni_company_email,
    validate_faculty_email,
    generate_otp,
)
from .tasks import send_otp_email

User = get_user_model()


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=15, default='')
    college = serializers.CharField(required=False, allow_blank=True, max_length=300, default='')
    batch_year = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        value = value.strip().lower()

        existing = User.objects.filter(email=value).first()
        if existing:
            if existing.is_verified:
                raise serializers.ValidationError(
                    "An account with this email already exists."
                )
            # Unverified duplicate — allow re-registration by deleting the stale user
            existing.delete()

        # Role-based email validation — role comes from initial_data
        role = self.initial_data.get('role', '')
        if role == User.STUDENT:
            validate_student_email(value)
        elif role == User.ALUMNI:
            validate_alumni_company_email(value)
        elif role == User.FACULTY:
            validate_faculty_email(value)

        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long."
            )
        if not any(ch.isdigit() for ch in value):
            raise serializers.ValidationError(
                "Password must contain at least one number."
            )
        return value

    def create(self, validated_data):
        email = validated_data['email']

        # Build a unique username from the email local part
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            password=make_password(validated_data['password']),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role=validated_data['role'],
            phone=validated_data.get('phone', ''),
            college=validated_data.get('college', ''),
            batch_year=validated_data.get('batch_year'),
            is_verified=False,
            is_active=True,
        )

        # Generate OTP and persist it
        otp_code = generate_otp()
        EmailOTP.objects.create(
            user=user,
            email=email,
            otp_code=otp_code,
            purpose=EmailOTP.REGISTRATION,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Send OTP — use Celery if available, otherwise send directly (dev)
        try:
            from .tasks import send_otp_email_task
            send_otp_email_task.delay(user.id, email, otp_code, EmailOTP.REGISTRATION)
        except Exception:
            send_otp_email(user.id, email, otp_code, EmailOTP.REGISTRATION)

        return user


class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6)

    def validate(self, data):
        email = data['email'].strip().lower()
        otp_code = data['otp_code'].strip()

        try:
            otp = EmailOTP.objects.filter(
                email=email,
                otp_code=otp_code,
                purpose=EmailOTP.REGISTRATION,
                is_used=False,
            ).latest('created_at')
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code.")

        if otp.is_expired():
            raise serializers.ValidationError(
                "OTP has expired. Please request a new one."
            )

        data['otp_instance'] = otp
        return data

    def save(self):
        otp = self.validated_data['otp_instance']
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user = otp.user
        if user:
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        return user


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=True)

    def validate(self, data):
        email = data['email'].strip().lower()
        role = data['role']

        # Generic message — never reveal whether the email exists (prevents enumeration)
        _generic = "If an account exists with this email and role, an OTP has been sent."

        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            raise serializers.ValidationError(_generic)

        if not user.is_verified:
            raise serializers.ValidationError(
                "Your email is not verified. Please verify your email first."
            )

        if not user.is_active:
            raise serializers.ValidationError("Your account has been deactivated.")

        data['user'] = user

        # Demo bypass — @test.com accounts skip OTP when DEMO_OTP is configured
        from django.conf import settings as _s
        if getattr(_s, 'DEMO_OTP', '') and email.endswith('@test.com'):
            data['is_demo'] = True

        return data

    def save(self):
        user = self.validated_data['user']

        # Demo bypass — return JWT directly without OTP
        if self.validated_data.get('is_demo'):
            refresh = RefreshToken.for_user(user)
            return {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'full_name': user.full_name,
                    'is_profile_complete': user.is_profile_complete,
                },
            }

        otp_code = generate_otp()
        EmailOTP.objects.create(
            user=user,
            email=user.email,
            otp_code=otp_code,
            purpose=EmailOTP.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        try:
            from .tasks import send_otp_email_task
            send_otp_email_task.delay(user.id, user.email, otp_code, EmailOTP.LOGIN)
        except Exception:
            send_otp_email(user.id, user.email, otp_code, EmailOTP.LOGIN)

        return user


class LoginOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(required=True, max_length=6)

    def validate(self, data):
        email = data['email'].strip().lower()
        otp_code = data['otp_code'].strip()

        try:
            otp = EmailOTP.objects.filter(
                email=email,
                otp_code=otp_code,
                purpose=EmailOTP.LOGIN,
                is_used=False,
            ).latest('created_at')
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code.")

        if otp.is_expired():
            raise serializers.ValidationError(
                "OTP has expired. Please request a new one."
            )

        data['otp_instance'] = otp
        return data

    def save(self):
        otp = self.validated_data['otp_instance']
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user = otp.user
        refresh = RefreshToken.for_user(user)

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'full_name': user.full_name,
                'is_profile_complete': user.is_profile_complete,
            },
        }


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone', 'profile_pic', 'college', 'batch_year',
            'is_verified', 'is_profile_complete', 'created_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified', 'created_at']

    def get_full_name(self, obj):
        return obj.full_name


# ── Day 4-5: Profile Serializers ──────────────────────────────────────────────

from .models import (
    AlumniProfile, StudentProfile, FacultyProfile,
    StudentEducation, StudentProject, StudentInternship,
    StudentCertification, StudentAward, StudentCompetitiveExam,
    StudentLanguage, StudentEmployment,
)
from django.core.validators import FileExtensionValidator
import os


class UserBasicSerializer(serializers.ModelSerializer):
    """Lightweight user info used inside profile serializers."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role',
                  'phone', 'profile_pic', 'college', 'is_verified']
        read_only_fields = fields


class AlumniProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    profile_completeness = serializers.SerializerMethodField()

    class Meta:
        model = AlumniProfile
        fields = [
            'id', 'user', 'company', 'designation', 'company_email',
            'linkedin_url', 'years_of_experience', 'skills',
            'wallet_balance', 'total_earned', 'bank_verified', 'impact_score',
            'verification_document', 'is_available_for_1on1',
            'price_per_30min', 'price_per_60min', 'bio', 'profile_completeness',
        ]
        read_only_fields = ['id', 'user', 'wallet_balance', 'total_earned',
                            'bank_verified', 'impact_score']

    def get_profile_completeness(self, obj) -> int:
        """Return 0-100 score based on filled fields."""
        fields_to_check = [
            obj.company, obj.designation, obj.company_email,
            obj.linkedin_url, obj.bio, obj.skills,
        ]
        filled = sum(1 for f in fields_to_check if f)
        return int((filled / len(fields_to_check)) * 100)

    def validate_price_per_30min(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        if value > 10000:
            raise serializers.ValidationError("Price cannot exceed ₹10,000.")
        return value

    def validate_price_per_60min(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        if value > 20000:
            raise serializers.ValidationError("Price cannot exceed ₹20,000.")
        return value

    def validate(self, data):
        p30 = data.get('price_per_30min')
        p60 = data.get('price_per_60min')
        if p30 is not None and p60 is not None and p60 < p30:
            raise serializers.ValidationError(
                {'price_per_60min': 'Price for 60 min must be greater than or equal to price for 30 min.'}
            )
        return data

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        # Update is_profile_complete on the user
        user = instance.user
        required = [instance.company, instance.designation, instance.bio]
        user.is_profile_complete = all(required)
        user.save(update_fields=['is_profile_complete'])
        return instance


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    resume_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'college_email', 'enrollment_number', 'degree',
            'branch', 'graduation_year', 'skills', 'resume_file',
            'resume_score', 'github_url', 'portfolio_url', 'looking_for',
            'demo_session_used', 'resume_check_count',
            'profile_summary', 'gender', 'date_of_birth', 'current_location',
            'preferred_locations', 'availability', 'profile_completeness_score',
        ]
        read_only_fields = ['id', 'user', 'resume_score',
                            'demo_session_used', 'resume_check_count',
                            'profile_completeness_score']

    def validate_resume_file(self, value):
        if value is None:
            return value
        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in ['pdf', 'doc', 'docx']:
            raise serializers.ValidationError(
                "Only PDF, DOC, and DOCX files are allowed."
            )
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Resume file must be under 5MB.")
        return value

    def validate_graduation_year(self, value):
        if value is not None:
            from django.utils import timezone
            current_year = timezone.now().year
            if value < 2000 or value > current_year + 6:
                raise serializers.ValidationError(
                    f"Graduation year must be between 2000 and {current_year + 6}."
                )
        return value

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        user = instance.user
        required = [instance.degree, instance.branch, instance.graduation_year]
        user.is_profile_complete = all(required)
        user.save(update_fields=['is_profile_complete'])
        return instance


class FacultyProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = FacultyProfile
        fields = [
            'id', 'user', 'college_email', 'employee_id', 'department',
            'designation', 'subjects', 'wallet_balance', 'total_earned',
            'bank_verified', 'bio',
        ]
        read_only_fields = ['id', 'user', 'wallet_balance', 'total_earned', 'bank_verified']

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()

        user = instance.user
        required = [instance.department, instance.designation, instance.bio]
        user.is_profile_complete = all(required)
        user.save(update_fields=['is_profile_complete'])
        return instance


class CVUploadSerializer(serializers.Serializer):
    """Accepts a PDF or DOCX CV file (max 5MB)."""
    cv_file = serializers.FileField()

    def validate_cv_file(self, value):
        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in ['pdf', 'docx']:
            raise serializers.ValidationError("Only PDF and DOCX files are accepted.")
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("CV file must be under 5MB.")
        return value


class ProfilePictureSerializer(serializers.Serializer):
    """Accepts a JPG or PNG profile picture (max 2MB)."""
    profile_pic = serializers.ImageField()

    def validate_profile_pic(self, value):
        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in ['jpg', 'jpeg', 'png']:
            raise serializers.ValidationError("Only JPG and PNG images are accepted.")
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Profile picture must be under 2MB.")
        return value


# ── Section Serializers (Naukri-style student profile) ────────────────────────

class StudentEducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentEducation
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']

    def validate(self, data):
        start = data.get('start_year')
        end = data.get('end_year')
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_year': 'End year must be greater than start year.'}
            )
        return data


class StudentProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProject
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']

    def validate(self, data):
        if data.get('is_ongoing'):
            data['end_month'] = 'Present'
        return data


class StudentInternshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentInternship
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class StudentCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentCertification
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']

    def validate(self, data):
        if data.get('does_not_expire'):
            data['expiry_date'] = None
        return data


class StudentAwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAward
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class StudentCompetitiveExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentCompetitiveExam
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class StudentLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentLanguage
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class StudentEmploymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentEmployment
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at']


class FullStudentProfileSerializer(serializers.Serializer):
    """Returns everything about a student in one response."""
    user = UserBasicSerializer(source='*', read_only=True)
    profile = serializers.SerializerMethodField()
    educations = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    internships = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()
    awards = serializers.SerializerMethodField()
    competitive_exams = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    employments = serializers.SerializerMethodField()
    profile_completeness = serializers.SerializerMethodField()

    def get_profile(self, obj):
        try:
            return StudentProfileSerializer(obj.student_profile).data
        except StudentProfile.DoesNotExist:
            return None

    def get_educations(self, obj):
        return StudentEducationSerializer(obj.educations.all(), many=True).data

    def get_projects(self, obj):
        return StudentProjectSerializer(obj.projects.all(), many=True).data

    def get_internships(self, obj):
        return StudentInternshipSerializer(obj.internships.all(), many=True).data

    def get_certifications(self, obj):
        return StudentCertificationSerializer(obj.certifications.all(), many=True).data

    def get_awards(self, obj):
        return StudentAwardSerializer(obj.awards.all(), many=True).data

    def get_competitive_exams(self, obj):
        return StudentCompetitiveExamSerializer(obj.competitive_exams.all(), many=True).data

    def get_languages(self, obj):
        return StudentLanguageSerializer(obj.languages.all(), many=True).data

    def get_employments(self, obj):
        return StudentEmploymentSerializer(obj.employments.all(), many=True).data

    def get_profile_completeness(self, obj):
        from utils.profile_helpers import get_full_profile_completeness
        return get_full_profile_completeness(obj)


class FacultyPublicSerializer(serializers.Serializer):
    """Public-facing faculty profile — excludes private fields."""
    user_id = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    college = serializers.SerializerMethodField()
    department = serializers.CharField()
    designation = serializers.CharField()
    subjects = serializers.JSONField()
    bio = serializers.CharField()

    def get_user_id(self, obj): return obj.user.id
    def get_full_name(self, obj): return obj.user.full_name
    def get_first_name(self, obj): return obj.user.first_name
    def get_profile_pic(self, obj): return obj.user.profile_pic.url if obj.user.profile_pic else None
    def get_college(self, obj): return obj.user.college
