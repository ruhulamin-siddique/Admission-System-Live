"""
Automated Test Suite for Student Admission Applications Feature.
Tests:
- C1: CoE ApplicationType vs AdmissionApplicationType independence
- C2: Public URL middleware exemptions
- C3: Tracking number prefix distinction (ADMN- vs APP-)
- B1: AdmissionApplicationConfig singleton pattern
- B6: 1-click student profile sync and StudentFieldHistory audit trail
- B7: Protected foreign key constraint on AdmissionApplicationType
- B8: Tracking by phone number returning list
- CC1: 24h duplicate submission detection and warning
- CC2: App 09 self-referential sibling rejection
- CC8: App 10 resubmit date validation (>= today + 7 days)
- Blank and filled PDF generation workflows
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import ProtectedError

from students.models import (
    Student,
    AdmissionApplicationType,
    AdmissionApplicationConfig,
    StudentApplication,
    StudentFieldHistory
)
from students.application_registry import seed_admission_application_types
from students.application_utils import (
    generate_admn_tracking_number,
    detect_profile_mismatches,
    build_application_pdf_context,
    render_application_to_pdf_bytes,
)
from master_data.models import Cluster, Program, AdmissionYear


class AdmissionApplicationTests(TestCase):

    def setUp(self):
        seed_admission_application_types()
        self.client = Client()

        # Create test staff user
        self.staff_user = User.objects.create_user(
            username='staff_test',
            password='Password123!',
            is_staff=True,
            is_superuser=True
        )

        # Create master data
        self.cluster = Cluster.objects.create(name='Engineering', code='05', is_engineering=True)
        self.prog = Program.objects.create(name='Computer Science & Engineering', short_name='CSE', ugc_code='01', cluster=self.cluster)
        self.year = AdmissionYear.objects.create(year=2026)

        # Create test student
        self.student = Student.objects.create(
            student_id='210101001',
            student_name='Md. Rahim Khan',
            student_mobile='01711122233',
            program='CSE',
            admission_year=2026,
            dob=date(2002, 5, 15)
        )

        # Create sibling student for App 09
        self.sibling = Student.objects.create(
            student_id='210101002',
            student_name='Mst. Rohima Khatun',
            student_mobile='01711122244',
            program='CSE',
            admission_year=2026
        )

    def test_c1_no_name_clash_with_coe(self):
        """C1: Verify AdmissionApplicationType from students does not conflict with CoE ApplicationType."""
        from students.models import AdmissionApplicationType as SAppType
        from coe.models import ApplicationType as CoEAppType
        self.assertIsNotNone(SAppType)
        self.assertIsNotNone(CoEAppType)
        self.assertNotEqual(SAppType, CoEAppType)

    def test_c2_public_urls_accessible_without_login(self):
        """C2: Public application portal and tracking must be exempt from authentication middleware."""
        # Unauthenticated client
        c = Client()
        resp_apply = c.get(reverse('public_apply'))
        self.assertEqual(resp_apply.status_code, 200)

        resp_track = c.get(reverse('public_track_application'))
        self.assertEqual(resp_track.status_code, 200)

        resp_blank = c.get(reverse('download_blank_pdf', kwargs={'app_type_code': 'scholarship_admission'}))
        self.assertIn(resp_blank.status_code, [200, 302])

    def test_c3_tracking_number_format(self):
        """C3: Generated tracking number must start with ADMN-YYYY-, distinct from CoE APP-."""
        tracking_no = generate_admn_tracking_number()
        curr_year = timezone.now().year
        self.assertTrue(tracking_no.startswith(f"ADMN-{curr_year}-"))
        self.assertFalse(tracking_no.startswith("APP-"))

    def test_b1_config_singleton(self):
        """B1: AdmissionApplicationConfig.get_config() must always return pk=1 singleton."""
        cfg1 = AdmissionApplicationConfig.get_config()
        cfg2 = AdmissionApplicationConfig.get_config()
        self.assertEqual(cfg1.pk, 1)
        self.assertEqual(cfg2.pk, 1)
        self.assertEqual(AdmissionApplicationConfig.objects.count(), 1)

    def test_b6_profile_sync_audit_trail(self):
        """B6: Profile sync action must update Student profile and create StudentFieldHistory audit records."""
        app_type = AdmissionApplicationType.objects.get(code='two_installments')
        application = StudentApplication.objects.create(
            tracking_number=generate_admn_tracking_number(),
            application_type=app_type,
            student=self.student,
            student_name='Md. Rahim Khan Updated',
            applicant_student_id=self.student.student_id,
            is_id_verified=True,
            department='CSE',
            phone_no='01799988877',
            has_profile_mismatch=True,
            mismatch_details={
                'student_name': {'field_label': 'Student Name', 'current': 'Md. Rahim Khan', 'submitted': 'Md. Rahim Khan Updated'},
                'mobile': {'field_label': 'Mobile Number', 'current': '01711122233', 'submitted': '01799988877'}
            }
        )

        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse('admin_sync_student_profile', kwargs={'tracking_number': application.tracking_number}))
        self.assertEqual(resp.status_code, 200)

        # Refresh student
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_name, 'Md. Rahim Khan Updated')
        self.assertEqual(self.student.student_mobile, '01799988877')

        # Check audit trail records
        histories = StudentFieldHistory.objects.filter(student=self.student)
        self.assertTrue(histories.filter(field_name='student_name').exists())
        self.assertTrue(histories.filter(field_name='student_mobile').exists())

    def test_b7_protected_foreign_key(self):
        """B7: Deleting AdmissionApplicationType with existing submissions must raise ProtectedError."""
        app_type = AdmissionApplicationType.objects.get(code='scholarship_admission')
        StudentApplication.objects.create(
            tracking_number=generate_admn_tracking_number(),
            application_type=app_type,
            student_name='Test Student',
            department='CSE',
            phone_no='01712345678'
        )

        with self.assertRaises(ProtectedError):
            app_type.delete()

    def test_b8_tracking_by_phone_returns_list(self):
        """B8: Tracking by phone number should return all applications submitted with that phone."""
        app_type = AdmissionApplicationType.objects.get(code='two_installments')
        shared_phone = '01855544433'

        StudentApplication.objects.create(
            tracking_number=generate_admn_tracking_number(),
            application_type=app_type,
            student_name='Brother 1',
            department='CSE',
            phone_no=shared_phone
        )
        StudentApplication.objects.create(
            tracking_number=generate_admn_tracking_number(),
            application_type=app_type,
            student_name='Brother 2',
            department='EEE',
            phone_no=shared_phone
        )

        resp = self.client.get(reverse('public_track_application'), {'phone': shared_phone})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['applications']), 2)

    def test_cc1_duplicate_submission_warning(self):
        """CC1: Submitting the same application format within 24h triggers a duplicate warning."""
        app_type = AdmissionApplicationType.objects.get(code='two_installments')

        # First submission
        resp1 = self.client.post(reverse('public_apply'), {
            'application_type': app_type.code,
            'student_name': 'Test Student',
            'student_id': '210101001',
            'department': 'CSE',
            'phone_no': '01712345678',
            'batch': 'Fall 2026',
            'semester': '1st',
            'father_profession': 'Teacher',
            'first_installment_tk': '30000',
            'second_installment_tk': '20000',
            'second_installment_date': '2026-10-15',
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1['status'], 'success')

        # Immediate duplicate submission
        resp2 = self.client.post(reverse('public_apply'), {
            'application_type': app_type.code,
            'student_name': 'Test Student',
            'student_id': '210101001',
            'department': 'CSE',
            'phone_no': '01712345678',
            'batch': 'Fall 2026',
            'semester': '1st',
            'father_profession': 'Teacher',
            'first_installment_tk': '30000',
            'second_installment_tk': '20000',
            'second_installment_date': '2026-10-15',
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2['status'], 'duplicate_warning')
        self.assertEqual(data2['tracking_number'], data1['tracking_number'])

    def test_cc2_self_referential_sibling_rejected(self):
        """CC2: App 09 rejects listing own ID as sibling."""
        app_type = AdmissionApplicationType.objects.get(code='sibling_waiver')
        resp = self.client.post(reverse('public_apply'), {
            'application_type': app_type.code,
            'student_name': 'Md. Rahim Khan',
            'student_id': '210101001',
            'department': 'CSE',
            'phone_no': '01711122233',
            'batch': '2026',
            'level': '1',
            'term': 'I',
            'sibling_id': '210101001',  # Same as student_id!
            'sibling_name': 'Self',
            'sibling_dept': 'CSE',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cannot list yourself as your own sibling', resp.json()['message'])

    def test_cc8_withdraw_papers_resubmit_date_validation(self):
        """CC8: App 10 requires resubmit_date to be >= today + 7 days."""
        app_type = AdmissionApplicationType.objects.get(code='withdraw_academic_papers')
        invalid_date = (timezone.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')

        resp = self.client.post(reverse('public_apply'), {
            'application_type': app_type.code,
            'student_name': 'Md. Rahim Khan',
            'student_id': '210101001',
            'department': 'CSE',
            'phone_no': '01711122233',
            'batch': '2026',
            'level': '1',
            'term': 'I',
            'withdraw_reason': 'Name Correction in Board',
            'papers_list': 'Original SSC Certificate',
            'duration_days': '7 Days',
            'resubmit_date': invalid_date,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('at least 7 days from today', resp.json()['message'])

    def test_secure_autofill_endpoint(self):
        """Autofill endpoint verifies student_id + mobile or DOB and returns masked data."""
        # Correct mobile
        resp = self.client.post(reverse('api_secure_autofill'), {
            'student_id': '210101001',
            'verify_type': 'mobile',
            'verify_value': '01711122233'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['student_name'], 'Md. Rahim Khan')
        self.assertIn('warning', data)

        # Incorrect mobile
        resp_fail = self.client.post(reverse('api_secure_autofill'), {
            'student_id': '210101001',
            'verify_type': 'mobile',
            'verify_value': '01700000000'
        })
        self.assertEqual(resp_fail.status_code, 403)

    def test_blank_pdf_creates_zero_db_records(self):
        """Blank PDF template download must create 0 StudentApplication records in DB."""
        initial_count = StudentApplication.objects.count()
        resp = self.client.get(reverse('download_blank_pdf', kwargs={'app_type_code': 'army_waiver'}))
        self.assertIn(resp.status_code, [200, 302])
        self.assertEqual(StudentApplication.objects.count(), initial_count)

    def test_delete_application_rbac(self):
        """Super Admin or user with delete_application permission can delete an application."""
        app_type = AdmissionApplicationType.objects.first()
        app = StudentApplication.objects.create(
            tracking_number="ADMN-2026-9999",
            application_type=app_type,
            student=self.student,
            student_name="Delete Test Student",
            applicant_student_id="210101001",
            is_id_verified=True,
            department="CSE",
            phone_no="01711223344",
            status="SUBMITTED"
        )
        # Unauthorized client cannot delete
        resp_unauth = self.client.post(reverse('admin_delete_application', kwargs={'tracking_number': app.tracking_number}))
        self.assertEqual(resp_unauth.status_code, 302) # Redirect to login

        # Superuser can delete
        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse('admin_delete_application', kwargs={'tracking_number': app.tracking_number}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(StudentApplication.objects.filter(tracking_number="ADMN-2026-9999").exists())
