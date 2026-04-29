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


class ExamBillingTests(TestCase):
    def setUp(self):
        cluster = Cluster.objects.create(name='Engineering', code='05')
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
        self.faculty = FacultyProfile.objects.create(name='Md. Al-Hasan', designation='Lecturer', program=self.cse)
        self.course = ExamCourse.objects.create(
            exam_program=self.exam_program,
            level='1',
            term='1',
            course_code='CSE101',
            course_title='Programming',
            no_of_scripts=10,
            total_students=10,
            is_engineering=True,
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
            term='1',
            total_students=10,
        )
        QuestionSetterAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A+B')
        ScriptExaminerAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A')
        ScriptScrutinizerAssignment.objects.create(exam_program=self.exam_program, faculty=self.faculty, course=self.course, part='A')

        summary = calculate_exam_program_summary(self.exam_program)
        row = summary['rows'][0]

        self.assertEqual(row['cecc'], Decimal('750.00'))
        self.assertEqual(row['rpsc'], Decimal('25.00'))
        self.assertEqual(row['question_setting'], Decimal('800.00'))
        self.assertEqual(row['script_examining'], Decimal('250.00'))
        self.assertEqual(row['scrutiny'], Decimal('50.00'))
        self.assertEqual(row['total'], Decimal('1875.00'))

    def test_amount_in_words(self):
        self.assertEqual(taka_in_words(Decimal('1875.00')), 'Taka One Thousand Eight Hundred Seventy Five Zero Paisa')
