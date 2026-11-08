import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from students.models import AdmissionIntake, OnlineApplicant
from master_data.models import AdmissionYear

User = get_user_model()


class Command(BaseCommand):
    help = "Seed 2 realistic test student applicants for the Winter 2027 intake on the live server."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-open',
            action='store_true',
            default=True,
            help='Ensure intake is open and deadline is set to a future date'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> Checking Winter 2027 Intake..."))

        # 1. Look for Winter 2027 intake
        intake = AdmissionIntake.objects.filter(intake_name__icontains="Winter 2027").first()
        if not intake:
            intake = AdmissionIntake.objects.filter(intake_name__icontains="Winter").first()

        now = timezone.now()
        future_deadline = now + datetime.timedelta(days=90)
        future_exam_date = now + datetime.timedelta(days=105)

        if not intake:
            academic_year = AdmissionYear.objects.filter(year=2027).first()
            if not academic_year:
                academic_year, _ = AdmissionYear.objects.get_or_create(year=2027, defaults={'is_active': True})

            intake = AdmissionIntake.objects.create(
                intake_name="Winter 2027",
                academic_year=academic_year,
                exam_roll_prefix="BAUST-W27-",
                next_roll_number=1003,
                form_fee_bdt=750.00,
                bkash_charge_bdt=12.00,
                bkash_number="01769675556",
                exam_venue="BAUST Campus (Saidpur)",
                is_open_for_application=True,
                application_deadline=future_deadline,
                exam_date=future_exam_date,
            )
            self.stdout.write(self.style.SUCCESS(f"Created new intake: {intake.intake_name} (ID: {intake.id})"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Found existing intake: {intake.intake_name} (ID: {intake.id})"))
            # If expired or closed, adjust deadline so public application and test status are active
            changed = False
            if not intake.is_open_for_application:
                intake.is_open_for_application = True
                changed = True
            if intake.application_deadline and intake.application_deadline < now:
                self.stdout.write(self.style.WARNING(
                    f"Notice: Deadline was past ({intake.application_deadline}). Extending to {future_deadline.strftime('%Y-%m-%d')} for active live testing."
                ))
                intake.application_deadline = future_deadline
                changed = True
            if changed:
                intake.save()
                self.stdout.write(self.style.SUCCESS(f"Updated intake {intake.intake_name} to active/open status."))

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        prefix = intake.exam_roll_prefix or "BAUST-W27-"

        # 2. Student 1: Nafis Fuad (Engineering - CSE) -> Status: APPROVED (Admit Card Ready)
        app_no_1 = "OA-W27-00101"
        exam_roll_1 = f"{prefix}1001"
        applicant1, created1 = OnlineApplicant.objects.update_or_create(
            application_no=app_no_1,
            defaults={
                "exam_roll": exam_roll_1,
                "intake": intake,
                "intake_name": intake.intake_name,
                "program_category": "Engineering",
                "desired_program": "CSE",
                "exam_venue": intake.exam_venue or "BAUST Campus (Saidpur)",
                "name": "Nafis Fuad",
                "mobile": "01711000101",
                "email": "nafis.fuad@example.com",
                "national_id": "19951234567890",
                "place_of_birth": "Dhaka",
                "gender": "Male",
                "blood_group": "A+",
                "dob": datetime.date(2005, 4, 15),
                "nationality": "Bangladeshi",
                "marital_status": "Single",
                "student_type": "Regular",
                "father_name": "Dr. Rafiqul Islam Fuad",
                "father_occupation": "Professor",
                "father_mobile": "01711000201",
                "mother_name": "Salma Begum",
                "mother_occupation": "Govt Officer",
                "mother_mobile": "01711000301",
                "present_house": "House 14, Road 5, Sector 4, Uttara",
                "present_district": "Dhaka",
                "present_police_station": "Uttara",
                "present_post_code": "1230",
                "present_country": "Bangladesh",
                "same_as_present": True,
                "permanent_house": "House 14, Road 5, Sector 4, Uttara",
                "permanent_district": "Dhaka",
                "permanent_police_station": "Uttara",
                "permanent_post_code": "1230",
                "permanent_country": "Bangladesh",
                "ssc_school": "Saidpur Govt Technical High School",
                "ssc_board": "Dinajpur",
                "ssc_roll": "214589",
                "ssc_reg": "1817452301",
                "ssc_year": "2022",
                "ssc_gpa": 5.00,
                "ssc_verified": True,
                "hsc_college": "Cantonment Public School & College, Saidpur",
                "hsc_board": "Dinajpur",
                "hsc_roll": "104523",
                "hsc_reg": "1817452301",
                "hsc_year": "2024",
                "hsc_gpa": 5.00,
                "hsc_verified": True,
                "total_gpa": 10.00,
                "payment_method": "bKash",
                "payment_trx_id": "BK9W27001",
                "payment_status": "VERIFIED",
                "payment_verified_by": admin_user,
                "payment_verified_at": now,
                "status": "APPROVED",
                "office_remarks": "Eligible for Engineering. Documents and bKash transaction verified. Admit card issued.",
                "is_trashed": False,
            }
        )
        status_1 = "Created" if created1 else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"[{status_1}] Student 1: {applicant1.name} ({applicant1.application_no}) | Status: {applicant1.status} | Roll: {applicant1.exam_roll}"
        ))

        # 3. Student 2: Sumaiya Tasnim (Non Engineering - BBA) -> Status: PENDING (New Applicant)
        app_no_2 = "OA-W27-00102"
        applicant2, created2 = OnlineApplicant.objects.update_or_create(
            application_no=app_no_2,
            defaults={
                "exam_roll": None,  # Pending applicants don't have roll numbers yet
                "intake": intake,
                "intake_name": intake.intake_name,
                "program_category": "Non Engineering",
                "desired_program": "BBA",
                "exam_venue": intake.exam_venue or "BAUST Campus (Saidpur)",
                "name": "Sumaiya Tasnim",
                "mobile": "01811000102",
                "email": "sumaiya.tasnim@example.com",
                "national_id": "20059876543210",
                "place_of_birth": "Rangpur",
                "gender": "Female",
                "blood_group": "O+",
                "dob": datetime.date(2005, 8, 22),
                "nationality": "Bangladeshi",
                "marital_status": "Single",
                "student_type": "Regular",
                "father_name": "Md. Aminur Rahman",
                "father_occupation": "Businessman",
                "father_mobile": "01811000202",
                "mother_name": "Nasreen Akhter",
                "mother_occupation": "Homemaker",
                "mother_mobile": "01811000302",
                "present_house": "Dhap, Jail Road, House 8",
                "present_district": "Rangpur",
                "present_police_station": "Kotwali",
                "present_post_code": "5400",
                "present_country": "Bangladesh",
                "same_as_present": False,
                "permanent_house": "Vill: Modern More, PO: Rangpur Sadar",
                "permanent_district": "Rangpur",
                "permanent_police_station": "Kotwali",
                "permanent_post_code": "5400",
                "permanent_country": "Bangladesh",
                "ssc_school": "Rangpur Govt Girls High School",
                "ssc_board": "Dinajpur",
                "ssc_roll": "314590",
                "ssc_reg": "1817459988",
                "ssc_year": "2022",
                "ssc_gpa": 4.90,
                "ssc_verified": False,
                "hsc_college": "Carmichael College, Rangpur",
                "hsc_board": "Dinajpur",
                "hsc_roll": "204599",
                "hsc_reg": "1817459988",
                "hsc_year": "2024",
                "hsc_gpa": 4.85,
                "hsc_verified": False,
                "total_gpa": 9.75,
                "payment_method": "bKash",
                "payment_trx_id": "BK9W27002",
                "payment_status": "PENDING",
                "payment_verified_by": None,
                "payment_verified_at": None,
                "status": "PENDING",
                "office_remarks": "Submitted online. Pending payment verification by accounts office.",
                "is_trashed": False,
            }
        )
        status_2 = "Created" if created2 else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"[{status_2}] Student 2: {applicant2.name} ({applicant2.application_no}) | Status: {applicant2.status} | Payment: PENDING"
        ))

        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS("[OK] 2 Test Applicants successfully ready for Winter 2027!"))
        self.stdout.write(self.style.SUCCESS("  1. Nafis Fuad (OA-W27-00101)  -> APPROVED (Can download Admit Card)"))
        self.stdout.write(self.style.SUCCESS("  2. Sumaiya Tasnim (OA-W27-00102) -> PENDING (Test Verification Flow)"))
        self.stdout.write(self.style.SUCCESS("========================================================\n"))
