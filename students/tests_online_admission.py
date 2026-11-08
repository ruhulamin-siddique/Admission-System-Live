from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
import io
from PIL import Image

from students.models import AdmissionIntake, OnlineApplicant, Student
from master_data.models import AdmissionYear, Cluster, Program, Hall
from students.application_utils import (
    generate_exam_roll,
    generate_application_no,
    normalize_mobile,
    validate_applicant_photo
)


class OnlineAdmissionTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Setup Admission Year
        self.year = AdmissionYear.objects.create(year=timezone.now().year)

        # Setup Intake
        self.intake = AdmissionIntake.objects.create(
            intake_name="Winter 2027 Test Intake",
            academic_year=self.year,
            is_open_for_application=True,
            form_fee_bdt=Decimal("750.00"),
            bkash_charge_bdt=Decimal("12.00"),
            bkash_number="01769675556",
            exam_venue="BAUST Campus (Saidpur)",
            exam_roll_prefix="BAUST-Winter2027-",
            next_roll_number=1001
        )

        # Setup Master Data
        self.cluster = Cluster.objects.create(name="Engineering & Technology", code="05")
        self.program = Program.objects.create(
            name="Computer Science and Engineering",
            short_name="CSE",
            cluster=self.cluster,
            ugc_code="01",
            level_code="1"
        )
        self.hall = Hall.objects.create(
            short_name="ABB",
            full_name="Abbas Ali Khan Hall",
            code="01"
        )

    def test_mobile_normalization(self):
        """Test normalization of various BD mobile number formats."""
        self.assertEqual(normalize_mobile("+8801711223344"), "01711223344")
        self.assertEqual(normalize_mobile("8801711223344"), "01711223344")
        self.assertEqual(normalize_mobile("8801812-345678"), "01812345678")
        self.assertEqual(normalize_mobile("01711223344"), "01711223344")

    def test_atomic_roll_generation(self):
        """Test exam roll generator atomically increments rolls without collision."""
        roll1 = generate_exam_roll(self.intake)
        roll2 = generate_exam_roll(self.intake)
        self.assertEqual(roll1, "BAUST-Winter2027-1001")
        self.assertEqual(roll2, "BAUST-Winter2027-1002")
        self.intake.refresh_from_db()
        self.assertEqual(self.intake.next_roll_number, 1003)

    def test_photo_validation(self):
        """Test Pillow image validator rejects spoofed text/exe files and accepts real images."""
        # Genuine PNG image
        img_io = io.BytesIO()
        img = Image.new('RGB', (300, 300), color='blue')
        img.save(img_io, format='PNG')
        img_io.seek(0)
        valid_file = SimpleUploadedFile("test.png", img_io.getvalue(), content_type="image/png")
        self.assertTrue(validate_applicant_photo(valid_file))

        # Fake text file renamed to .jpg
        fake_file = SimpleUploadedFile("fake.jpg", b"This is not a real JPEG image", content_type="image/jpeg")
        self.assertFalse(validate_applicant_photo(fake_file))

    def test_public_urls_accessible_without_login(self):
        """Verify all public admission portal URLs return HTTP 200 without authentication."""
        urls = [
            reverse('public_requirements'),
            reverse('public_apply_form'),
            reverse('public_application_status'),
            reverse('api_check_open_intakes'),
        ]
        for u in urls:
            response = self.client.get(u)
            self.assertEqual(response.status_code, 200, f"URL {u} returned status {response.status_code}")

    def test_application_submission_and_duplicate_guard(self):
        """Test successful application submission and duplicate check on mobile+intake."""
        # Create image file
        img_io = io.BytesIO()
        img = Image.new('RGB', (300, 300), color='white')
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        photo_file = SimpleUploadedFile("avatar.jpg", img_io.getvalue(), content_type="image/jpeg")

        post_data = {
            'intake': self.intake.id,
            'mobile': '01711998877',
            'program_category': 'Engineering',
            'desired_program': 'CSE',
            'name': 'TAHMIDUL ISLAM',
            'gender': 'Male',
            'dob': '2005-06-15',
            'father_name': 'Father Name',
            'mother_name': 'Mother Name',
            'present_house': 'House 1, Road 2',
            'present_district': 'Saidpur',
            'ssc_school': 'Saidpur Cantonment Public School',
            'ssc_board': 'Dinajpur',
            'ssc_roll': '123456',
            'ssc_year': '2022',
            'ssc_gpa': '5.00',
            'hsc_college': 'Saidpur Cantonment College',
            'hsc_board': 'Dinajpur',
            'hsc_roll': '654321',
            'hsc_year': '2024',
            'hsc_gpa': '4.80',
            'payment_method': 'bKash',
            'payment_trx_id': 'TESTTRX123',
            'photo': photo_file,
        }

        # 1st Submission: Should redirect to confirmation
        response = self.client.post(reverse('public_apply_form'), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/admission-portal/confirmation/' in response.url)

        # Verify record in DB
        applicant = OnlineApplicant.objects.get(mobile='01711998877')
        self.assertEqual(applicant.name, 'TAHMIDUL ISLAM')
        self.assertEqual(applicant.total_gpa, 9.80)
        self.assertEqual(applicant.exam_roll, 'BAUST-Winter2027-1001')
        self.assertEqual(applicant.status, 'PENDING')

        # 2nd Submission with same mobile and semester: Must be rejected as duplicate
        photo_file.seek(0)
        response2 = self.client.post(reverse('public_apply_form'), post_data)
        # Should redirect with error
        self.assertEqual(response2.status_code, 302)
        self.assertEqual(OnlineApplicant.objects.filter(mobile='01711998877').count(), 1)

    def test_admit_card_security_two_factor(self):
        """Test admit card download requires both Exam Roll AND registered Mobile number."""
        applicant = OnlineApplicant.objects.create(
            application_no="OA-2027-00001",
            exam_roll="BAUST-Winter2027-1005",
            intake=self.intake,
            intake_name=self.intake.intake_name,
            program_category="Engineering",
            desired_program="CSE",
            name="TEST CANDIDATE",
            mobile="01711000000",
            gender="Male",
            father_name="Father",
            mother_name="Mother",
            payment_trx_id="TRX0001",
            status="APPROVED"
        )

        # 1. Correct roll + correct mobile: Returns 200 (Admit card page)
        res = self.client.get(reverse('public_admitcard_download'), {
            'exam_roll': 'BAUST-Winter2027-1005',
            'mobile': '01711000000'
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ADMIT CARD")
        self.assertContains(res, "BAUST-Winter2027-1005")

        # 2. Correct roll + WRONG mobile: Blocked (redirect with error)
        res_wrong = self.client.get(reverse('public_admitcard_download'), {
            'exam_roll': 'BAUST-Winter2027-1005',
            'mobile': '01899999999'
        })
        self.assertEqual(res_wrong.status_code, 302)

        # 3. Status is PENDING (not approved yet): Blocked
        applicant.status = 'PENDING'
        applicant.save()
        res_pending = self.client.get(reverse('public_admitcard_download'), {
            'exam_roll': 'BAUST-Winter2027-1005',
            'mobile': '01711000000'
        })
        self.assertEqual(res_pending.status_code, 302)

    def test_admin_workflows(self):
        """Test Admin Applicant Hub: status update, payment verification, and 1-click enrollment."""
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser(username="admin_user", email="admin@baust.edu.bd", password="password123")
        self.client.force_login(admin_user)

        applicant = OnlineApplicant.objects.create(
            application_no="OA-2027-00100",
            exam_roll="BAUST-Winter2027-1006",
            intake=self.intake,
            intake_name=self.intake.intake_name,
            program_category="Engineering",
            desired_program="CSE",
            name="TEST ENROLL STUDENT",
            mobile="01711222333",
            gender="Male",
            father_name="Father",
            mother_name="Mother",
            payment_trx_id="TRX12345",
            status="PENDING"
        )

        # 1. Update status to APPROVED
        status_res = self.client.post(reverse('admin_update_applicant_status', args=[applicant.id]), {
            'status': 'APPROVED',
            'remarks': 'All papers verified'
        })
        self.assertEqual(status_res.status_code, 200)
        applicant.refresh_from_db()
        self.assertEqual(applicant.status, 'APPROVED')

        # 2. Verify payment
        pay_res = self.client.post(reverse('admin_verify_payment', args=[applicant.id]), {
            'payment_status': 'VERIFIED',
            'payment_notes': 'bKash merchant confirmed'
        })
        self.assertEqual(pay_res.status_code, 200)
        applicant.refresh_from_db()
        self.assertEqual(applicant.payment_status, 'VERIFIED')
        self.assertEqual(applicant.payment_verified_by, admin_user)

        # 3. 1-Click Enrollment to Database
        enroll_res = self.client.post(reverse('admin_enroll_to_database', args=[applicant.id]), {
            'hall_name': self.hall.full_name,
            'batch_name': '1st Batch',
        })
        self.assertEqual(enroll_res.status_code, 200)
        data = enroll_res.json()
        self.assertEqual(data['status'], 'success')
        new_student_id = data['student_id']

        applicant.refresh_from_db()
        self.assertEqual(applicant.status, 'ADMITTED')
        self.assertIsNotNone(applicant.admitted_student)
        self.assertEqual(applicant.admitted_student.student_id, new_student_id)

        # Verify Student record exists in database
        student = Student.objects.get(student_id=new_student_id)
        self.assertEqual(student.student_name, "TEST ENROLL STUDENT")
        self.assertEqual(student.student_mobile, "01711222333")
        self.assertEqual(student.program, "CSE")

        # 4. Double enrollment attempt must be blocked (B9 guard)
        enroll_again = self.client.post(reverse('admin_enroll_to_database', args=[applicant.id]), {
            'hall_name': self.hall.full_name,
            'batch_name': '1st Batch',
        })
        self.assertEqual(enroll_again.status_code, 400)
        self.assertIn('already enrolled', enroll_again.json()['message'])

    def test_soft_delete_and_restore_guard(self):
        """Test soft delete and restore guard when active duplicate exists (B4)."""
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser(username="admin_user2", email="admin2@baust.edu.bd", password="password123")
        self.client.force_login(admin_user)

        app1 = OnlineApplicant.objects.create(
            application_no="OA-2027-00201",
            exam_roll="BAUST-Winter2027-1007",
            intake=self.intake,
            intake_name=self.intake.intake_name,
            program_category="Engineering",
            desired_program="CSE",
            name="STUDENT ONE",
            mobile="01711333444",
            gender="Male",
            father_name="Father",
            mother_name="Mother",
            payment_trx_id="TRX201"
        )

        # Soft delete app1
        trash_res = self.client.post(reverse('admin_trash_applicant', args=[app1.id]))
        self.assertEqual(trash_res.status_code, 200)
        app1.refresh_from_db()
        self.assertTrue(app1.is_trashed)

        # Student applies again with same mobile and semester while app1 is trashed
        app2 = OnlineApplicant.objects.create(
            application_no="OA-2027-00202",
            exam_roll="BAUST-Winter2027-1008",
            intake=self.intake,
            intake_name=self.intake.intake_name,
            program_category="Engineering",
            desired_program="CSE",
            name="STUDENT ONE NEW",
            mobile="01711333444",
            gender="Male",
            father_name="Father",
            mother_name="Mother",
            payment_trx_id="TRX202"
        )

        # Admin tries to restore app1: Guard B4 must block it because app2 is active
        restore_res = self.client.post(reverse('admin_restore_applicant', args=[app1.id]))
        self.assertEqual(restore_res.status_code, 400)
        self.assertIn('another active application already exists', restore_res.json()['message'])

