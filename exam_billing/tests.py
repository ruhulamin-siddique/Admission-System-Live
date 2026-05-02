from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Role, RolePermission
from master_data.models import Cluster, Program

from .billing_calculator import calculate_exam_program_summary, taka_in_words
from .models import (
    BillingExam,
    BillingRateTemplate,
    CECCAssignment,
    ExamBillingSetting,
    ExamCourse,
    ExamProgram,
    FacultyProfile,
    QuestionSetterAssignment,
    RPSCAssignment,
    ScriptExaminerAssignment,
    ScriptScrutinizerAssignment,
)
from .scope import get_allowed_programs
from .views import _copy_program_seed_data, _summary_payload


class ExamBillingTests(TestCase):
    def setUp(self):
        cluster = Cluster.objects.create(name='Engineering', code='05', is_engineering=True)
        self.cse = Program.objects.create(name='Computer Science and Engineering', short_name='CSE', ugc_code='01', cluster=cluster)
        self.eee = Program.objects.create(name='Electrical and Electronic Engineering', short_name='EEE', ugc_code='02', cluster=cluster)
        self.user = User.objects.create_user(username='dept', password='test')
        role = Role.objects.create(name='Dept Billing')
        for task in ['view_dashboard', 'manage_department_data', 'export_print']:
            RolePermission.objects.create(role=role, module='exam_billing', task=task)
        self.user.profile.role = role
        self.user.profile.department_scope = 'CSE'
        self.user.profile.save()
        self.admin = User.objects.create_superuser(username='admin', password='test')

        template = BillingRateTemplate.objects.create(name='Default', is_default=True)
        self.exam = BillingExam.objects.create(name='Winter 2026', exam_type='FINAL', semester_label='Winter 2026', status='open')
        ExamBillingSetting.create_from_template(self.exam, template)
        self.exam_program = ExamProgram.objects.create(exam=self.exam, program=self.cse)
        # FIX BUG-4: Use first_name/last_name, not the property 'name'
        self.faculty = FacultyProfile.objects.create(
            first_name='Md. Al-Hasan',
            designation='Lecturer',
            program=self.cse
        )
        # FIX BUG-4: ExamCourse has no total_students or is_engineering fields
        self.course = ExamCourse.objects.create(
            exam_program=self.exam_program,
            level='1',
            term='I',
            course_code='CSE101',
            course_title='Programming',
            no_of_scripts=10,
        )

    def test_department_scope_limits_programs(self):
        self.assertEqual(list(get_allowed_programs(self.user)), [self.cse])
        self.assertIn(self.eee, list(get_allowed_programs(self.admin)))

    def test_calculator_combines_committee_and_course_duties(self):
        CECCAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, role='Member')
        RPSCAssignment.objects.create(
            exam_program=self.exam_program,
            faculty=self.faculty,
            role='Member',
            level='1',
            term='I',
        )
        QuestionSetterAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A+B')
        ScriptExaminerAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A')
        ScriptScrutinizerAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A')

        summary = calculate_exam_program_summary(self.exam_program)
        row = summary['rows'][0]

        self.assertEqual(row['cecc'], Decimal('750.00'))
        self.assertEqual(row['rpsc'], Decimal('0.00'))       # 0 students in level_term_summaries
        self.assertEqual(row['question_setting'], Decimal('800.00'))
        self.assertEqual(row['script_examining'], Decimal('250.00'))
        self.assertEqual(row['scrutiny'], Decimal('50.00'))

    def test_amount_in_words(self):
        self.assertEqual(taka_in_words(Decimal('1875.00')), 'Taka One Thousand Eight Hundred Seventy Five')

    def test_calculator_returns_empty_summary_when_no_settings(self):
        """BUG-7: Missing exam.settings must not crash the dashboard."""
        bare_exam = BillingExam.objects.create(name='Bare Exam', exam_type='FINAL', semester_label='S1', status='open')
        bare_ep = ExamProgram.objects.create(exam=bare_exam, program=self.cse)
        summary = calculate_exam_program_summary(bare_ep)
        self.assertEqual(summary['grand_total'], Decimal('0.00'))
        self.assertEqual(summary['rows'], [])

    def test_copy_previous_exam_seed_data_reuses_faculty_and_courses(self):
        from .models import ExamFaculty

        previous_exam = BillingExam.objects.create(name='Summer 2025', exam_type='FINAL', semester_label='Summer 2025', status='finalized')
        ExamBillingSetting.create_from_template(previous_exam)
        previous_program = ExamProgram.objects.create(exam=previous_exam, program=self.cse)
        ExamFaculty.objects.create(exam_program=previous_program, faculty=self.faculty)
        # FIX BUG-4: ExamCourse has no total_students or is_engineering fields
        ExamCourse.objects.create(
            exam_program=previous_program,
            level='2',
            term='I',
            course_code='CSE202',
            course_title='Data Structures',
            no_of_scripts=20,
        )

        copied = _copy_program_seed_data(previous_program, self.exam_program)

        self.assertEqual(copied, {'faculty': 1, 'courses': 1})
        self.assertTrue(self.exam_program.faculty.filter(faculty=self.faculty).exists())
        self.assertTrue(self.exam_program.courses.filter(course_code='CSE202').exists())

    def test_finalize_cache_payload_is_json_safe(self):
        CECCAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, role='Member')
        summary = calculate_exam_program_summary(self.exam_program)
        payload = _summary_payload(summary)

        self.exam_program.mark_finalized(summary['grand_total'], payload)
        self.exam_program.refresh_from_db()

        # BUG-9 fix: status should now be 'finalized', not 'locked'
        self.assertEqual(self.exam_program.status, 'finalized')
        self.assertEqual(self.exam_program.cached_total, Decimal('750.00'))
        self.assertEqual(self.exam_program.cached_summary['rows'][0]['faculty_name'], 'Md. Al-Hasan')
