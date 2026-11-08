"""
counseling/tests.py
===================
Automated test suite for the Psychological Counseling & Student Wellbeing module.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from students.models import Student
from core.models import Role, RolePermission, UserProfile
from .models import (
    CounselingCase,
    CounselingAppointment,
    SessionRecord,
    MentalHealthAssessment,
    CounselingSettings,
    CounselorProfile,
    CaseCategory,
    RiskLevel,
    CaseStatus,
    AssessmentType,
)
from .utils import calculate_phq9_score, calculate_gad7_score, calculate_dass21_score


class CounselingModelTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_id="202401040099",
            student_name="Test Student",
            student_mobile="01711223344",
            program="CSE",
            batch="25th",
            hall_attached="Abbas Uddin Hall"
        )
        self.user = User.objects.create_user(username="psychologist", password="password123")
        self.counselor = CounselorProfile.objects.create(
            user=self.user,
            designation="University Psychologist",
            room_number="Room 204"
        )

    def test_case_id_auto_generation(self):
        """Tests that Case IDs are auto-generated atomically in format CASE-YYYY-NNNN."""
        case = CounselingCase.objects.create(
            student=self.student,
            category=CaseCategory.ACADEMIC_STRESS,
            risk_level=RiskLevel.LOW,
            status=CaseStatus.OPEN,
            assigned_counselor=self.counselor,
            presenting_complaints="Exam anxiety"
        )
        self.assertTrue(case.case_number.startswith("CASE-"))
        self.assertIn("0001", case.case_number)

    def test_soft_delete_manager(self):
        """Tests that soft-deleted cases do not appear in active manager."""
        case = CounselingCase.objects.create(
            student=self.student,
            category=CaseCategory.EXAM_ANXIETY,
            presenting_complaints="Stress test"
        )
        self.assertEqual(CounselingCase.objects.count(), 1)
        case.is_deleted = True
        case.save()
        self.assertEqual(CounselingCase.objects.count(), 0)
        self.assertEqual(CounselingCase.all_objects.count(), 1)

    def test_counseling_settings_singleton(self):
        """Tests that CounselingSettings maintains only 1 row."""
        s1 = CounselingSettings.get_settings()
        s1.session_lock_hours = 48
        s1.save()
        s2 = CounselingSettings.get_settings()
        self.assertEqual(s2.session_lock_hours, 48)
        self.assertEqual(CounselingSettings.objects.count(), 1)


class PsychometricScoreTests(TestCase):
    def test_phq9_scoring(self):
        """Tests PHQ-9 calculation and severity classifications."""
        # Minimal
        res_min = {f"q{i}": 0 for i in range(1, 10)}
        score_min = calculate_phq9_score(res_min)
        self.assertEqual(score_min['total_score'], 0)
        self.assertIn("Minimal", score_min['severity_tier'])
        self.assertFalse(score_min['has_suicidal_flag'])

        # Moderate with Suicidal flag (Q9=2)
        res_mod = {f"q{i}": 1 for i in range(1, 10)}
        res_mod['q9'] = 2
        score_mod = calculate_phq9_score(res_mod)
        self.assertEqual(score_mod['total_score'], 10)
        self.assertIn("Moderate", score_mod['severity_tier'])
        self.assertTrue(score_mod['has_suicidal_flag'])

        # Severe
        res_sev = {f"q{i}": 3 for i in range(1, 10)}
        score_sev = calculate_phq9_score(res_sev)
        self.assertEqual(score_sev['total_score'], 27)
        self.assertIn("Severe", score_sev['severity_tier'])

    def test_gad7_scoring(self):
        """Tests GAD-7 anxiety scoring."""
        res = {f"q{i}": 2 for i in range(1, 8)}
        score = calculate_gad7_score(res)
        self.assertEqual(score['total_score'], 14)
        self.assertIn("Moderate", score['severity_tier'])

    def test_dass21_scoring(self):
        """Tests DASS-21 subscale breakdown."""
        res = {f"q{i}": 1 for i in range(1, 22)}
        score = calculate_dass21_score(res)
        self.assertIn('sub_scores', score)
        self.assertIn('depression', score['sub_scores'])
        self.assertIn('anxiety', score['sub_scores'])
        self.assertIn('stress', score['sub_scores'])


class CounselingAccessControlTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.unauth_user = User.objects.create_user(username="faculty_user", password="password123")
        self.psych_role = Role.objects.create(name="Psychologist")
        RolePermission.objects.create(role=self.psych_role, module="counseling", task="view_dashboard")
        
        self.psych_user = User.objects.create_user(username="licensed_psych", password="password123")
        self.psych_user.profile.role = self.psych_role
        self.psych_user.profile.save()

        # Student & Counselor for public booking tests
        self.student = Student.objects.create(
            student_id="202401040099",
            student_name="Test Student",
            student_mobile="01711223344",
            program="B.Sc. in CSE",
            batch="25th",
            hall_attached="Abbas Uddin Hall"
        )
        self.counselor = CounselorProfile.objects.create(
            user=self.psych_user,
            designation="University Psychologist",
            room_number="Room 204",
            is_active_counselor=True
        )

    def test_unauthorized_user_blocked(self):
        """Tests that general users cannot access the counseling dashboard."""
        self.client.login(username="faculty_user", password="password123")
        response = self.client.get(reverse('counseling_dashboard'))
        # Should redirect to profile with access denied message
        self.assertEqual(response.status_code, 302)

    def test_authorized_psychologist_allowed(self):
        """Tests that authorized psychologists can access the dashboard."""
        self.client.login(username="licensed_psych", password="password123")
        response = self.client.get(reverse('counseling_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_public_booking_portal_accessible_without_login(self):
        """Tests that students can access the booking portal without logging in."""
        response = self.client.get(reverse('counseling_public_book'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PHQ-4")
        self.assertContains(response, "CARE-2026")

    def test_api_verify_student_id(self):
        """Tests real-time student ID verification endpoint."""
        # Valid ID
        resp_valid = self.client.get(reverse('counseling_api_verify_student'), {'student_id': self.student.student_id})
        self.assertEqual(resp_valid.status_code, 200)
        self.assertContains(resp_valid, "Verified Student")

        # Invalid ID
        resp_invalid = self.client.get(reverse('counseling_api_verify_student'), {'student_id': '999999999999'})
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertContains(resp_invalid, "not found")

    def test_public_booking_generates_secret_token_and_status_check(self):
        """Tests booking creates unique secret token and allows anonymous status lookup."""
        import datetime
        from django.utils import timezone
        booking_date = timezone.localdate() + datetime.timedelta(days=2)
        if booking_date.weekday() == 4: # Friday
            booking_date += datetime.timedelta(days=2)

        post_data = {
            'student_id': self.student.student_id,
            'student_mobile': '01799887766', # Custom active BD mobile
            'category': 'academic_stress',
            'urgency': 'routine',
            'session_mode': 'in_person',
            'appointment_date': booking_date.strftime('%Y-%m-%d'),
            'time_slot': '09:00 AM - 09:50 AM',
            'brief_notes': 'Need advice on study focus.',
            'consent_agreed': 'on',
        }
        response = self.client.post(reverse('counseling_public_book'), data=post_data)
        self.assertEqual(response.status_code, 302) # Redirects to success

        # Check appointment created with secret token
        appt = CounselingAppointment.objects.filter(case__student=self.student, time_slot='09:00 AM - 09:50 AM').first()
        self.assertIsNotNone(appt)
        self.assertTrue(appt.secret_token.startswith('CARE-'))
        self.assertEqual(appt.contact_mobile, '01799887766')

        # Test anonymous status lookup via secret token
        lookup_resp = self.client.post(reverse('counseling_api_check_status'), {'lookup_query': appt.secret_token})
        self.assertEqual(lookup_resp.status_code, 200)
        self.assertContains(lookup_resp, appt.secret_token)
        self.assertContains(lookup_resp, "09:00 AM - 09:50 AM")
