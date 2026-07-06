import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alumni_platform.settings.dev')
django.setup()

import pytest
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import EmailOTP, AlumniProfile, StudentProfile, FacultyProfile
from apps.feed.models import Post
from apps.sessions_app.models import Session, Booking
from apps.payments.models import Transaction, Wallet, PayoutRequest, AIToolUsage

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def verified_student(db):
    user = User.objects.create_user(
        username='student_test',
        email='student@college.ac.in',
        password='testpass123',
        first_name='Test',
        last_name='Student',
        role='student',
        college='Test College',
        batch_year=2024,
        is_verified=True,
        is_active=True,
    )
    return user


@pytest.fixture
def verified_alumni(db):
    user = User.objects.create_user(
        username='alumni_test',
        email='alumni@techcompany.com',
        password='testpass123',
        first_name='Test',
        last_name='Alumni',
        role='alumni',
        college='Test College',
        batch_year=2020,
        is_verified=True,
        is_active=True,
    )
    return user


@pytest.fixture
def verified_faculty(db):
    user = User.objects.create_user(
        username='faculty_test',
        email='faculty@college.ac.in',
        password='testpass123',
        first_name='Test',
        last_name='Faculty',
        role='faculty',
        college='Test College',
        is_verified=True,
        is_active=True,
        is_profile_complete=False,
    )
    FacultyProfile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def student_with_token(api_client, verified_student):
    # Ensure profile exists (signal may have created it already)
    StudentProfile.objects.get_or_create(user=verified_student)
    token = RefreshToken.for_user(verified_student)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    return api_client


@pytest.fixture
def alumni_with_token(api_client, verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    token = RefreshToken.for_user(verified_alumni)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    return api_client


@pytest.fixture
def faculty_with_token(api_client, verified_faculty):
    token = RefreshToken.for_user(verified_faculty)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    return api_client


@pytest.fixture
def alumni_post(db, verified_alumni):
    return Post.objects.create(
        author=verified_alumni,
        post_type='general',
        content='This is a test alumni post with enough content.',
        status='active',
    )


@pytest.fixture
def job_post(db, verified_alumni):
    return Post.objects.create(
        author=verified_alumni,
        post_type='job',
        title='Senior Django Developer',
        content='Looking for experienced Django developer.',
        company_name='Google',
        job_role='Senior SDE',
        status='active',
    )


# ── Session fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def upcoming_session(db, verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='DSA Masterclass',
        description='Complete DSA course covering arrays, trees, graphs and DP.',
        niche='DSA',
        skills_covered=['Arrays', 'Trees', 'DP'],
        scheduled_at=timezone.now() + timedelta(days=3),
        duration_minutes=60,
        price=Decimal('499.00'),
        max_seats=20,
        status='upcoming',
    )


@pytest.fixture
def free_session(db, verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='Free DSA Intro',
        description='Free introduction to DSA concepts for all students.',
        niche='DSA',
        scheduled_at=timezone.now() + timedelta(days=1),
        duration_minutes=30,
        price=Decimal('0.00'),
        is_free=True,
        is_demo_eligible=True,
        max_seats=50,
        status='upcoming',
    )


@pytest.fixture
def confirmed_booking(db, upcoming_session, verified_student):
    StudentProfile.objects.get_or_create(user=verified_student)
    return Booking.objects.create(
        session=upcoming_session,
        student=verified_student,
        status='confirmed',
        amount_paid=Decimal('499.00'),
        platform_cut=Decimal('149.70'),
        host_share=Decimal('349.30'),
    )


# ── Razorpay mock (autouse — applies to all tests) ────────────────────────────

@pytest.fixture(autouse=True)
def mock_razorpay(monkeypatch):
    """Mock Razorpay to avoid real API calls in tests."""
    import apps.sessions_app.views as sessions_views

    class MockOrder:
        @staticmethod
        def create(data):
            return {'id': 'order_test_123456', 'amount': data['amount'], 'currency': 'INR'}

    class MockUtility:
        @staticmethod
        def verify_payment_signature(data):
            return True

    class MockRazorpayClient:
        order = MockOrder()
        utility = MockUtility()

    class MockRazorpayModule:
        @staticmethod
        def Client(**kwargs):
            return MockRazorpayClient()

    monkeypatch.setattr(sessions_views, 'razorpay', MockRazorpayModule())


# ── Phase 5 fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def upcoming_group_session(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='DSA Masterclass for FAANG',
        description='Complete DSA course covering arrays, trees, linked lists, graphs and dynamic programming.',
        niche='DSA',
        skills_covered=['Arrays', 'Trees', 'Dynamic Programming', 'Graphs'],
        scheduled_at=timezone.now() + timedelta(days=3),
        duration_minutes=60,
        price=Decimal('499.00'),
        max_seats=20,
        booked_seats=0,
        status='upcoming',
        is_free=False,
        is_demo_eligible=True,
    )


@pytest.fixture
def upcoming_one_on_one_session(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='one_on_one',
        title='1:1 Resume Review Session',
        description='Personal resume review and career guidance for software engineering roles.',
        niche='Career Guidance',
        skills_covered=['Resume Writing', 'Career Planning'],
        scheduled_at=timezone.now() + timedelta(days=1),
        duration_minutes=30,
        price=Decimal('299.00'),
        max_seats=1,
        booked_seats=0,
        status='upcoming',
        is_free=False,
    )


@pytest.fixture
def free_demo_session(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='Free Intro to System Design',
        description='Free introduction session to system design concepts for beginners.',
        niche='System Design',
        skills_covered=['System Design', 'Architecture'],
        scheduled_at=timezone.now() + timedelta(days=2),
        duration_minutes=30,
        price=Decimal('0.00'),
        max_seats=100,
        booked_seats=0,
        status='upcoming',
        is_free=True,
        is_demo_eligible=True,
    )


@pytest.fixture
def full_session(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='Full Session - No Seats',
        description='This session is completely booked out.',
        niche='Python',
        skills_covered=['Python'],
        scheduled_at=timezone.now() + timedelta(days=5),
        duration_minutes=60,
        price=Decimal('399.00'),
        max_seats=5,
        booked_seats=5,
        status='upcoming',
    )


@pytest.fixture
def past_session(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    return Session.objects.create(
        host=verified_alumni,
        session_type='group',
        title='Completed Python Bootcamp',
        description='A completed Python bootcamp session.',
        niche='Python',
        skills_covered=['Python', 'Django'],
        scheduled_at=timezone.now() - timedelta(days=2),
        duration_minutes=90,
        price=Decimal('599.00'),
        max_seats=15,
        booked_seats=8,
        status='completed',
    )


@pytest.fixture
def confirmed_booking_p5(upcoming_group_session, verified_student):
    """Phase 5 confirmed booking — separate from the older confirmed_booking fixture."""
    StudentProfile.objects.get_or_create(user=verified_student)
    booking = Booking.objects.create(
        session=upcoming_group_session,
        student=verified_student,
        status='confirmed',
        amount_paid=Decimal('499.00'),
        platform_cut=Decimal('149.70'),
        host_share=Decimal('349.30'),
        razorpay_order_id='order_test_confirmed_123',
        razorpay_payment_id='pay_test_confirmed_123',
    )
    upcoming_group_session.booked_seats = 1
    upcoming_group_session.save()
    return booking


@pytest.fixture
def completed_booking(past_session, verified_student):
    StudentProfile.objects.get_or_create(user=verified_student)
    return Booking.objects.create(
        session=past_session,
        student=verified_student,
        status='completed',
        amount_paid=Decimal('599.00'),
        platform_cut=Decimal('179.70'),
        host_share=Decimal('419.30'),
        razorpay_order_id='order_test_completed_456',
        razorpay_payment_id='pay_test_completed_456',
    )


@pytest.fixture
def student_api_client(api_client, verified_student):
    StudentProfile.objects.get_or_create(user=verified_student)
    refresh = RefreshToken.for_user(verified_student)
    api_client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(refresh.access_token))
    api_client._student = verified_student
    return api_client


@pytest.fixture
def alumni_api_client(api_client, verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    refresh = RefreshToken.for_user(verified_alumni)
    api_client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(refresh.access_token))
    api_client._alumni = verified_alumni
    return api_client


@pytest.fixture
def faculty_api_client(api_client, verified_faculty):
    refresh = RefreshToken.for_user(verified_faculty)
    api_client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(refresh.access_token))
    api_client._faculty = verified_faculty
    return api_client


# ── Referral fixtures ─────────────────────────────────────────────────────────

from datetime import timedelta
from apps.referrals.models import Referral, ReferralApplication


@pytest.fixture
def active_referral(verified_alumni):
    return Referral.objects.create(
        posted_by=verified_alumni,
        company_name='TestCorp',
        job_title='Python Developer',
        job_description='We need a Python developer with Django experience. Must know REST APIs and databases. Excellent communication skills required.',
        work_type='full_time',
        experience_level='fresher',
        location='Bangalore',
        required_skills=['Python', 'Django', 'REST API', 'PostgreSQL'],
        preferred_skills=['Docker', 'AWS'],
        max_applicants=5,
        deadline=timezone.now() + timedelta(days=7),
        status='active',
    )


@pytest.fixture
def expired_referral(verified_alumni):
    return Referral.objects.create(
        posted_by=verified_alumni,
        company_name='OldCorp',
        job_title='Java Developer',
        job_description='Looking for a Java developer with Spring Boot experience and knowledge of microservices.',
        work_type='full_time',
        experience_level='junior',
        location='Mumbai',
        required_skills=['Java', 'Spring Boot'],
        max_applicants=5,
        deadline=timezone.now() - timedelta(days=1),
        status='expired',
    )


@pytest.fixture
def full_referral(verified_alumni):
    return Referral.objects.create(
        posted_by=verified_alumni,
        company_name='FullCorp',
        job_title='React Developer',
        job_description='Looking for React developer with hooks, redux and testing experience for our product team.',
        work_type='internship',
        experience_level='fresher',
        location='Pune',
        required_skills=['React', 'JavaScript'],
        max_applicants=2,
        total_applications=2,
        deadline=timezone.now() + timedelta(days=5),
        status='closed',
    )


@pytest.fixture
def student_with_matching_skills(verified_student):
    """Student whose skills match the active_referral requirements"""
    try:
        sp = verified_student.student_profile
        sp.skills = ['Python', 'Django', 'REST API', 'PostgreSQL', 'JavaScript']
        sp.save(update_fields=['skills'])
    except Exception:
        pass
    return verified_student


@pytest.fixture
def student_with_no_skills(verified_student):
    """Student with empty skills list"""
    try:
        sp = verified_student.student_profile
        sp.skills = []
        sp.save(update_fields=['skills'])
    except Exception:
        pass
    return verified_student


@pytest.fixture
def confirmed_referral_application(active_referral, verified_student):
    return ReferralApplication.objects.create(
        referral=active_referral,
        student=verified_student,
        status='applied',
        match_score=85,
        matched_skills=['Python', 'Django', 'REST API'],
        missing_skills=['PostgreSQL'],
    )


# ── Payment fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def alumni_wallet(verified_alumni):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    wallet, _ = Wallet.objects.get_or_create(user=verified_alumni)
    wallet.balance = Decimal('2000.00')
    wallet.total_earned = Decimal('5000.00')
    wallet.save()
    return wallet


@pytest.fixture
def faculty_wallet(verified_faculty):
    wallet, _ = Wallet.objects.get_or_create(user=verified_faculty)
    wallet.balance = Decimal('1500.00')
    wallet.total_earned = Decimal('3000.00')
    wallet.save()
    return wallet


@pytest.fixture
def completed_session_transaction(verified_alumni, verified_student):
    AlumniProfile.objects.get_or_create(user=verified_alumni)
    StudentProfile.objects.get_or_create(user=verified_student)
    return Transaction.objects.create(
        payer=verified_student,
        payee=verified_alumni,
        transaction_type='session_booking',
        status='completed',
        gross_amount=Decimal('499.00'),
        platform_fee=Decimal('149.70'),
        payee_amount=Decimal('349.30'),
        razorpay_order_id='order_test_txn_001',
        razorpay_payment_id='pay_test_txn_001',
        description='DSA Masterclass session booking',
        related_object_type='session_booking',
        related_object_id=1,
    )


@pytest.fixture
def mock_razorpay_payments(monkeypatch):
    """Mock Razorpay for payment tests that need it."""
    class FakeOrder:
        @staticmethod
        def create(data):
            return {'id': f'order_test_{data["amount"]}', 'amount': data['amount'], 'currency': 'INR'}

    class FakeUtility:
        @staticmethod
        def verify_payment_signature(params):
            return True

    class FakeClient:
        order = FakeOrder()
        utility = FakeUtility()

    # payment_utils is the only place razorpay is called from views
    import utils.payment_utils as payment_utils

    class MockRazorpayModule:
        @staticmethod
        def Client(**kwargs):
            return FakeClient()

    monkeypatch.setattr(payment_utils, 'razorpay', MockRazorpayModule())
    return FakeClient


# ── AI Tools fixtures (Phase 8) ───────────────────────────────────────────────

import json


@pytest.fixture
def resume_check_free_usage(verified_student):
    """A free AIToolUsage record for resume_check — simulates payment gate passed"""
    return AIToolUsage.objects.create(
        user=verified_student,
        tool_type='resume_check',
        is_free_use=True,
    )


@pytest.fixture
def resume_check_paid_usage(verified_student, completed_session_transaction):
    """A paid AIToolUsage record for resume_check"""
    return AIToolUsage.objects.create(
        user=verified_student,
        tool_type='resume_check',
        is_free_use=False,
        transaction=completed_session_transaction,
    )


@pytest.fixture
def skill_gap_usage(verified_student):
    """A paid AIToolUsage for skill_gap"""
    return AIToolUsage.objects.create(
        user=verified_student,
        tool_type='skill_gap',
        is_free_use=False,
    )


@pytest.fixture
def interview_usage(verified_student):
    """A paid AIToolUsage for ai_interview"""
    return AIToolUsage.objects.create(
        user=verified_student,
        tool_type='ai_interview',
        is_free_use=False,
    )


@pytest.fixture
def resume_build_usage(verified_student):
    """A paid AIToolUsage for resume_builder"""
    return AIToolUsage.objects.create(
        user=verified_student,
        tool_type='resume_builder',
        is_free_use=False,
    )


@pytest.fixture
def student_with_full_profile(verified_student):
    """Student with complete profile data for AI tool testing"""
    try:
        sp = verified_student.student_profile
        sp.skills = ['Python', 'Django', 'React', 'JavaScript', 'PostgreSQL', 'REST API', 'Git']
        sp.profile_summary = 'Computer Science student with strong programming background.'
        sp.save(update_fields=['skills', 'profile_summary'])
    except Exception:
        pass
    return verified_student


@pytest.fixture
def mock_openai(monkeypatch):
    """Mocks OpenAI API calls to avoid real API costs during testing.
    Returns pre-defined responses for each tool type."""

    class FakeChoice:
        def __init__(self, content):
            self.message = type('msg', (), {'content': content})()

    class FakeCompletion:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            prompt_content = str(kwargs.get('messages', ''))

            # Check most-specific patterns FIRST to avoid false matches on 'grade'
            if 'resume_sections' in prompt_content or 'tailoring_notes' in prompt_content:
                mock_data = json.dumps({
                    "resume_sections": {
                        "header": {"name": "Test Student", "email": "test@college.ac.in", "phone": "9999999999", "location": "Bangalore"},
                        "summary": "Computer Science student with Python and Django skills seeking software engineering role.",
                        "education": [{"degree": "B.Tech CSE", "institution": "Test University", "year": "2026", "grade": "8.5 CGPA"}],
                        "skills": {"technical": ["Python", "Django", "JavaScript"], "tools": ["Git", "VS Code"], "soft": ["Communication"]},
                        "experience": [],
                        "projects": [{"name": "E-commerce App", "description": "Full stack Django app", "tech_stack": ["Python", "Django"], "bullets": ["Built REST APIs", "Implemented user auth"]}],
                        "certifications": [],
                        "achievements": ["Top performer in coding competition"],
                    },
                    "tailoring_notes": "Resume tailored for software engineering roles with emphasis on Python skills.",
                    "ats_optimization_tips": ["Add more keywords", "Quantify achievements", "Use action verbs"],
                })
                return FakeCompletion(mock_data)

            elif 'hiring_recommendation' in prompt_content or 'post-interview' in prompt_content.lower():
                mock_data = json.dumps({
                    "overall_score": 70,
                    "grade": "B",
                    "performance_by_type": {"technical": 72, "behavioral": 68, "hr": 75},
                    "top_strengths": ["Strong Python knowledge", "Good communication", "Problem solving"],
                    "areas_to_improve": ["System design depth", "Time complexity analysis", "SQL optimization"],
                    "recommended_resources": [
                        {"topic": "System Design", "resource": "Designing Data-Intensive Applications book"},
                        {"topic": "Algorithms", "resource": "LeetCode medium problems"},
                    ],
                    "hiring_recommendation": "Hire",
                    "detailed_feedback": "Candidate shows solid foundation in Python and Django. Ready for junior roles.",
                    "next_steps": ["Practice system design", "Solve 2 LeetCode mediums daily", "Build 1 full stack project"],
                })
                return FakeCompletion(mock_data)

            elif 'overall_score' in prompt_content or 'ats_score' in prompt_content:
                mock_data = json.dumps({
                    "overall_score": 72,
                    "section_scores": {
                        "contact_info": 8, "education": 16, "skills": 15,
                        "experience": 18, "projects": 10, "formatting": 5,
                    },
                    "strengths": ["Strong Python skills", "Good project portfolio", "Clear formatting"],
                    "weaknesses": ["Limited work experience", "Missing quantified achievements", "No LinkedIn"],
                    "improvements": [
                        {"section": "Experience", "issue": "No internships", "suggestion": "Add any freelance or volunteer work"},
                        {"section": "Skills", "issue": "Missing cloud skills", "suggestion": "Add AWS or GCP basics"},
                        {"section": "Contact", "issue": "No LinkedIn", "suggestion": "Add LinkedIn profile URL"},
                    ],
                    "ats_score": 68,
                    "ats_keywords_found": ["Python", "Django", "REST"],
                    "ats_keywords_missing": ["AWS", "Docker", "CI/CD"],
                    "summary": "Solid resume with good technical foundation. Needs more practical experience.",
                    "grade": "B",
                })
                return FakeCompletion(mock_data)

            elif 'readiness_score' in prompt_content or 'learning_roadmap' in prompt_content:
                mock_data = json.dumps({
                    "target_role": "Full Stack Developer",
                    "readiness_score": 55,
                    "readiness_level": "Getting There",
                    "current_skills_relevant": ["Python", "Django", "JavaScript"],
                    "skills_to_learn": [
                        {
                            "skill": "React",
                            "priority": "Critical",
                            "why_needed": "Primary frontend framework for full stack roles",
                            "estimated_weeks": 4,
                            "free_resources": ["React official docs", "Scrimba React course"],
                            "paid_resources": ["Udemy React course by Maximilian"],
                        },
                        {
                            "skill": "Docker",
                            "priority": "High",
                            "why_needed": "Required for deployment and DevOps",
                            "estimated_weeks": 2,
                            "free_resources": ["Docker docs", "TechWorld with Nana YouTube"],
                            "paid_resources": ["Docker Mastery Udemy"],
                        },
                    ],
                    "learning_roadmap": [
                        {"week": 1, "focus": "React basics", "skills": ["React", "JSX"], "milestone": "Build a simple React app"},
                        {"week": 2, "focus": "React hooks", "skills": ["useState", "useEffect"], "milestone": "Build a CRUD app"},
                        {"week": 3, "focus": "Docker basics", "skills": ["Docker"], "milestone": "Containerize a Django app"},
                        {"week": 4, "focus": "Full stack project", "skills": ["React", "Django", "Docker"], "milestone": "Deploy a full stack project"},
                    ],
                    "total_weeks_to_ready": 4,
                    "job_market_insight": "Full stack developers are in high demand with React and Django.",
                    "similar_roles_easier": ["Backend Developer", "Django Developer"],
                })
                return FakeCompletion(mock_data)

            elif 'time_limit_seconds' in prompt_content or 'interview questions' in prompt_content.lower():
                mock_data = json.dumps({
                    "questions": [
                        {"id": 1, "type": "technical", "difficulty": "medium", "question": "Explain how Django's ORM works and give an example.", "hint": "Cover QuerySets and lazy loading", "time_limit_seconds": 180},
                        {"id": 2, "type": "technical", "difficulty": "easy", "question": "What is REST API and how have you used it?", "hint": "HTTP methods, status codes, JSON", "time_limit_seconds": 120},
                        {"id": 3, "type": "behavioral", "difficulty": "easy", "question": "Tell me about a challenging project you worked on.", "hint": "Use STAR method", "time_limit_seconds": 180},
                    ],
                    "job_role": "Software Engineer",
                    "total_questions": 3,
                    "estimated_duration_minutes": 12,
                })
                return FakeCompletion(mock_data)

            elif 'evaluate' in prompt_content.lower() or 'ideal_answer_points' in prompt_content:
                mock_data = json.dumps({
                    "score": 7,
                    "feedback": "Good answer that covers the basics. Could include more technical depth.",
                    "strengths": ["Clear explanation", "Good example given"],
                    "improvements": ["Add more technical details", "Mention performance implications"],
                    "ideal_answer_points": ["QuerySets are lazy", "Use select_related for optimization", "F() and Q() objects"],
                    "follow_up_question": "How would you optimize a slow Django query?",
                })
                return FakeCompletion(mock_data)

            # Default fallback
            return FakeCompletion(json.dumps({"success": True, "message": "Mock response"}))

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        chat = FakeChat()

    monkeypatch.setattr('utils.ai_tools_service.OpenAI', lambda **kwargs: FakeOpenAI())
    return FakeOpenAI()


# ── Phase 9 Admin fixtures ────────────────────────────────────────────────────

import pytest
from apps.accounts.models import AdminActionLog


@pytest.fixture
def admin_api_client(api_client):
    """API client authenticated as dev admin"""
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken
    User = get_user_model()
    try:
        admin = User.objects.get(email='test.admin@alumniai.com')
    except User.DoesNotExist:
        admin = User.objects.create_user(
            username='test.admin@alumniai.com',
            email='test.admin@alumniai.com',
            password='DevPass@123',
            role='admin',
            first_name='Dev',
            last_name='Admin',
            is_verified=True,
        )
    refresh = RefreshToken.for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(refresh.access_token))
    api_client._admin = admin
    return api_client


@pytest.fixture
def unverified_alumni(verified_alumni):
    """Alumni who has submitted verification but not yet approved"""
    verified_alumni.is_verified = False
    verified_alumni.save(update_fields=['is_verified'])
    try:
        p = verified_alumni.alumni_profile
        p.verification_status = 'pending'
        p.verification_document_url = 'https://linkedin.com/in/devtest'
        p.save(update_fields=['verification_status', 'verification_document_url'])
    except Exception:
        pass
    return verified_alumni


# ── Phase 10 Notification fixtures ───────────────────────────────────────────

from apps.notifications.models import Notification, NotificationPreference


@pytest.fixture
def sample_notification(verified_student):
    return Notification.objects.create(
        recipient=verified_student,
        notif_type='general',
        title='Test Notification',
        message='This is a test notification message for unit testing.',
        link='/dashboard/student/',
        is_read=False,
    )


@pytest.fixture
def read_notification(verified_student):
    return Notification.objects.create(
        recipient=verified_student,
        notif_type='payment',
        title='Payment Received',
        message='You received Rs.349 from a session booking.',
        link='/payments/wallet/',
        is_read=True,
        read_at=timezone.now(),
    )


@pytest.fixture
def multiple_notifications(verified_student):
    """Creates 5 notifications: 3 unread, 2 read"""
    notifs = []
    for i in range(3):
        notifs.append(Notification.objects.create(
            recipient=verified_student,
            notif_type='general',
            title=f'Unread Notification {i + 1}',
            message=f'This is unread notification number {i + 1}.',
            is_read=False,
        ))
    for i in range(2):
        notifs.append(Notification.objects.create(
            recipient=verified_student,
            notif_type='session',
            title=f'Read Notification {i + 1}',
            message=f'This is read notification number {i + 1}.',
            is_read=True,
            read_at=timezone.now(),
        ))
    return notifs
