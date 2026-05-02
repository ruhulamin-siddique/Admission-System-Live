import random
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from master_data.models import Program
from exam_billing.models import (
    BillingExam, ExamProgram, FacultyProfile, ExamCourse, 
    ExamFaculty, ExamLevelTermSummary, QuestionSetterAssignment,
    RPSCAssignment, ScriptExaminerAssignment, ScriptScrutinizerAssignment,
    CECCAssignment, ECMember, QMSCAssignment, QPSCMember, ExamBillingSetting
)

class Command(BaseCommand):
    help = "Seeds dummy data with Bangladeshi names for all departments in the Exam Billing suite."

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Universal Institutional Workflow Data...")
        
        # 1. Expand Bangladeshi Names
        first_names = [
            "Arif", "Sabbir", "Tanveer", "Niaz", "Morshed", "Kamrul", "Zulfikar", "Mahfuz", "Anisur", "Siddiqur",
            "Mustafiz", "Rezwan", "Mashrafe", "Tamim", "Mushfiq", "Shakib", "Mahmudullah", "Taskin", "Mustafizur", "Rubel",
            "Mominul", "Liton", "Soumya", "Imrul", "Taijul", "Abu Jayed", "Ebadot", "Najmul", "Yasir", "Nayeem",
            "Abdullah", "Saif", "Rony", "Sabbir", "Mehedi", "Afif", "Nurul", "Bijoy", "Nasir", "Al-Amin"
        ]
        last_names = [
            "Hossain", "Ahmed", "Rahman", "Islam", "Uddin", "Khan", "Sarker", "Mollah", "Talukder", "Alam",
            "Chowdhury", "Patwary", "Bhuiyan", "Majumder", "Siddique", "Ali", "Haque", "Munshi", "Sheikh", "Akand",
            "Miah", "Babu", "Rana", "Mir", "Dewan", "Kazi", "Sufi", "Laskar", "Gazi", "Siddiqui"
        ]
        designations = ["Professor", "Associate Professor", "Assistant Professor", "Lecturer"]

        programs = list(Program.objects.all())
        if not programs:
            self.stdout.write(self.style.ERROR("No programs found. Seed master data first."))
            return

        # 2. Create high-volume Faculty profiles (Bangladeshi names)
        for i in range(120):
            f_name = random.choice(first_names)
            l_name = random.choice(last_names)
            
            FacultyProfile.objects.get_or_create(
                employee_id=f"BAUST-BD-{3000+i}",
                defaults={
                    'first_name': f_name,
                    'last_name': l_name,
                    'designation': random.choice(designations),
                    'program': random.choice(programs),
                    'email': f"{f_name.lower()}.{l_name.lower()}{i}@baust.edu.bd",
                    'mobile': f"017{random.randint(11000000, 99999999)}",
                    'is_active': True
                }
            )
        
        all_faculties = list(FacultyProfile.objects.all())

        # 3. Create Testing Exam
        exam, created = BillingExam.objects.get_or_create(
            name="Spring 2026 Institutional Cycle",
            defaults={
                'exam_type': 'semester_final',
                'semester_label': 'Spring 2026',
                'starts_on': date(2026, 1, 1),
                'ends_on': date(2026, 6, 30),
                'status': 'open'
            }
        )
        if created:
            from exam_billing.views import _settings_defaults
            ExamBillingSetting.objects.get_or_create(exam=exam, defaults=_settings_defaults())

        # 4. Link ALL Programs to this Exam
        for prog in programs:
            ExamProgram.objects.get_or_create(exam=exam, program=prog)

        # 5. Seed ALL Departments
        exam_programs = exam.programs.all()
        for ep in exam_programs:
            prog_name = ep.program.short_name or ep.program.name
            self.stdout.write(f"Mass-seeding workflow data for {prog_name}...")
            
            # Cleanup previous
            ep.rpsc_assignments.all().delete()
            ep.qmsc_assignments.all().delete()
            ep.question_setters.all().delete()
            ep.script_examiners.all().delete()
            ep.script_scrutinizers.all().delete()
            ep.cecc_assignments.all().delete()
            ep.ec_members.all().delete()
            ep.qpsc_members.all().delete()
            ep.faculty.all().delete()
            ep.courses.all().delete()
            ep.level_term_summaries.all().delete()

            # Assign 30 unique faculty members per department
            dept_faculties = random.sample(all_faculties, min(50, len(all_faculties)))
            for f in dept_faculties[:30]:
                ExamFaculty.objects.create(exam_program=ep, faculty=f)
            
            # A. Student Counts (Fundamentals)
            for l in ['1', '2', '3', '4']:
                for t in ['I', 'II']:
                    ExamLevelTermSummary.objects.create(
                        exam_program=ep, level=l, term=t, total_students=random.randint(50, 70)
                    )
            
            # B. Courses (Fundamentals)
            dept_courses = []
            for i in range(15):
                course = ExamCourse.objects.create(
                    exam_program=ep,
                    course_code=f"{prog_name}-{200+i}",
                    syllabus="2022",
                    course_title=f"Core {prog_name} Module {i+1}",
                    level=random.choice(['1', '2', '3', '4']),
                    term=random.choice(['I', 'II']),
                    offering_department=prog_name,
                    no_of_scripts=random.randint(60, 100)
                )
                dept_courses.append(course)

            # C. Assignments (15 rows each)
            for i in range(15):
                # Question Setter
                QuestionSetterAssignment.objects.create(
                    exam_program=ep, course=dept_courses[i], part='A+B',
                    faculty=random.choice(dept_faculties)
                )
                # Script Examiner
                ScriptExaminerAssignment.objects.create(
                    exam_program=ep, course=dept_courses[i], part='A',
                    faculty=random.choice(dept_faculties)
                )
                # Script Scrutinizer
                ScriptScrutinizerAssignment.objects.create(
                    exam_program=ep, course=dept_courses[i], part='B',
                    faculty=random.choice(dept_faculties)
                )

            # D. Committees (RPSC Fixed)
            # One Chairman for all
            RPSCAssignment.objects.create(
                exam_program=ep, level='All', term='All', role='Chairman', 
                faculty=random.choice(dept_faculties)
            )
            # Tabulators for specific levels/terms
            rpsc_slots = [(l, t, r) for l in ['1', '2', '3', '4'] for t in ['I', 'II'] for r in ['Tabulator 1', 'Tabulator 2']]
            for i in range(min(15, len(rpsc_slots))):
                l, t, r = rpsc_slots[i]
                RPSCAssignment.objects.create(
                    exam_program=ep, level=l, term=t, role=r, faculty=random.choice(dept_faculties)
                )

            # CECC & EC
            for i in range(15):
                CECCAssignment.objects.create(
                    exam_program=ep, faculty=dept_faculties[i % len(dept_faculties)],
                    role=random.choice(['Chairman', 'Member', 'Assistant'])
                )
                ECMember.objects.create(
                    exam_program=ep, faculty=dept_faculties[(i+7) % len(dept_faculties)],
                    role=random.choice(['Chairman', 'Member', 'Tabulator 1', 'Tabulator 2'])
                )

            # QMSC (Fixed)
            QMSCAssignment.objects.create(exam_program=ep, role='Chairman', faculty=random.choice(dept_faculties))
            for i in range(15):
                QMSCAssignment.objects.create(
                    exam_program=ep, course=dept_courses[i], role='Member',
                    faculty=random.choice(dept_faculties),
                    external_member_name=f"Prof. {random.choice(first_names)} {random.choice(last_names)}",
                    external_member_designation="External Expert (AUST/BUET)"
                )

            # QPSC
            for i in range(15):
                QPSCMember.objects.create(
                    exam_program=ep, faculty=dept_faculties[i % len(dept_faculties)],
                    role=random.choice(['Chairman', 'Member']),
                    question_count=random.randint(10, 25)
                )

        self.stdout.write(self.style.SUCCESS(f"Universal Seeding Complete: {len(exam_programs)} Departments Populated with Bangladeshi Dummy Data."))
