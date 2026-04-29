from io import BytesIO

import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Role, RolePermission
from master_data.models import Cluster, Program
from students.models import Student


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class StudentDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        engineering = Cluster.objects.create(name='Engineering & Technology', code='05')
        business = Cluster.objects.create(name='Business & Management', code='09')

        cls.cse_program = Program.objects.create(
            name='Computer Science and Engineering',
            short_name='CSE',
            ugc_code='01',
            cluster=engineering,
            level_code='1',
        )
        cls.eee_program = Program.objects.create(
            name='Electrical and Electronic Engineering',
            short_name='EEE',
            ugc_code='02',
            cluster=engineering,
            level_code='1',
        )
        Program.objects.create(
            name='Master of Business Administration',
            short_name='MBA',
            ugc_code='03',
            cluster=business,
            level_code='3',
        )

        for index in range(1, 16):
            Student.objects.create(
                student_id=f'CSE{index:03d}',
                student_name=f'CSE Student {index:02d}',
                program=cls.cse_program.name,
                admission_year=2025 if index <= 10 else 2024,
                cluster=engineering.name,
                batch='25th' if index <= 10 else '24th',
                semester_name='Spring',
                program_type='Bachelor',
                admission_status='Active',
                gender='Male' if index % 2 else 'Female',
                father_name=f'Father CSE {index:02d}',
                mother_name=f'Mother CSE {index:02d}',
                student_mobile=f'01700000{index:03d}',
            )

        cls.inactive_student = Student.objects.create(
            student_id='CSE900',
            student_name='Inactive CSE Student',
            program=cls.cse_program.name,
            admission_year=2024,
            cluster=engineering.name,
            batch='24th',
            semester_name='Fall',
            program_type='Bachelor',
            admission_status='Inactive',
            gender='Female',
            father_name='Inactive Father',
            mother_name='Inactive Mother',
            father_mobile='01711000001',
            mother_mobile='01711000002',
            student_mobile='01810000000',
            student_email='inactive@example.com',
            emergency_contact='01711999999',
            blood_group='B+',
            religion='Islam',
            present_address='Dormitory Road, Section 1, Dhaka Cantonment',
            permanent_address='Village Home, Cumilla Sadar, Cumilla',
            photo_path='photos/inactive.jpg',
        )
        cls.cancelled_student = Student.objects.create(
            student_id='CSE901',
            student_name='Cancelled CSE Student',
            program=cls.cse_program.name,
            admission_year=2025,
            cluster=engineering.name,
            batch='25th',
            semester_name='Spring',
            program_type='Bachelor',
            admission_status='Cancelled',
            gender='Male',
            father_name='Cancelled Father',
            mother_name='Cancelled Mother',
            student_mobile='01810000001',
            photo_path='https://example.com/cancelled.jpg',
        )
        cls.legacy_scope_student = Student.objects.create(
            student_id='CSE902',
            student_name='Legacy Short Program Student',
            program='CSE',
            admission_year=2025,
            cluster=engineering.name,
            batch='25th',
            semester_name='Spring',
            program_type='Bachelor',
            admission_status='Active',
            gender='Male',
            father_name='Legacy Father',
            mother_name='Legacy Mother',
            student_mobile='01810000002',
        )

        for index in range(1, 5):
            Student.objects.create(
                student_id=f'EEE{index:03d}',
                student_name=f'EEE Student {index:02d}',
                program=cls.eee_program.name,
                admission_year=2025,
                cluster=engineering.name,
                batch='25th',
                semester_name='Spring',
                program_type='Bachelor',
                admission_status='Active',
                gender='Female',
                father_name=f'Father EEE {index:02d}',
                mother_name=f'Mother EEE {index:02d}',
                student_mobile=f'01900000{index:03d}',
            )

        cls.latest_eee_student = Student.objects.create(
            student_id='EEE900',
            student_name='EEE Latest Batch Student',
            program=cls.eee_program.name,
            admission_year=2026,
            cluster=engineering.name,
            batch='26th',
            semester_name='Spring',
            program_type='Bachelor',
            admission_status='Active',
            gender='Female',
            father_name='Latest EEE Father',
            mother_name='Latest EEE Mother',
            student_mobile='01999999999',
        )

        cls.mba_student = Student.objects.create(
            student_id='MBA001',
            student_name='MBA Student',
            program='MBA',
            admission_year=2025,
            cluster=business.name,
            batch='MBA-1',
            semester_name='Spring',
            program_type='Masters',
            admission_status='Active',
            gender='Female',
            father_name='MBA Father',
            mother_name='MBA Mother',
            student_mobile='01610000000',
        )

        cls.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123',
        )

        scoped_role = Role.objects.create(name='Scoped Staff')
        RolePermission.objects.create(role=scoped_role, module='students', task='view_directory')
        RolePermission.objects.create(role=scoped_role, module='students', task='export_excel')

        cls.scoped_user = User.objects.create_user(
            username='scoped',
            email='scoped@example.com',
            password='password123',
        )
        cls.scoped_user.profile.role = scoped_role
        cls.scoped_user.profile.department_scope = 'CSE'
        cls.scoped_user.profile.save()

    def setUp(self):
        self.client.force_login(self.superuser)

    def read_excel(self, response):
        return pd.read_excel(BytesIO(response.content))

    def test_directory_excludes_cancelled_by_default(self):
        response = self.client.get(reverse('student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.cancelled_student, response.context['page_obj'].paginator.object_list)
        self.assertContains(response, 'Showing all students except')

    def test_directory_status_filter_can_show_cancelled(self):
        response = self.client.get(reverse('student_list'), {'status': 'Cancelled'})

        students = list(response.context['page_obj'].object_list)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(students, [self.cancelled_student])

    def test_directory_renders_combined_parent_column(self):
        response = self.client.get(reverse('student_list'), {'search': self.inactive_student.student_id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>Parents</th>', html=True)
        self.assertContains(response, f'Father: {self.inactive_student.father_name}')
        self.assertContains(response, f'Mother: {self.inactive_student.mother_name}')

    def test_directory_page_has_clear_filters_button(self):
        response = self.client.get(reverse('student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clear Filters')
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, '?per_page=25')
        self.assertContains(response, 'sort=dept_batch_serial')

    def test_directory_filters_work_for_visible_fields(self):
        cases = (
            ({'search': 'Inactive CSE Student'}, lambda rows: rows == [self.inactive_student]),
            ({'year': '2024'}, lambda rows: all(student.admission_year == 2024 for student in rows)),
            ({'dept': 'Business & Management'}, lambda rows: rows == [self.mba_student]),
            ({'program': self.cse_program.name}, lambda rows: all(student.program == self.cse_program.name for student in rows)),
            ({'batch': 'MBA-1'}, lambda rows: rows == [self.mba_student]),
            ({'type': 'Masters'}, lambda rows: rows == [self.mba_student]),
            ({'gender': 'Female'}, lambda rows: rows and all(student.gender == 'Female' for student in rows)),
        )

        for params, assertion in cases:
            with self.subTest(params=params):
                response = self.client.get(reverse('student_list'), params)
                rows = list(response.context['page_obj'].paginator.object_list)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(assertion(rows))

    def test_default_directory_sort_is_department_then_latest_batch_then_serial(self):
        response = self.client.get(reverse('student_list'))

        ordered_ids = [student.student_id for student in response.context['page_obj'].paginator.object_list]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ordered_ids[:3], ['CSE001', 'CSE002', 'CSE003'])
        self.assertLess(ordered_ids.index('CSE010'), ordered_ids.index('CSE011'))
        self.assertLess(ordered_ids.index('CSE900'), ordered_ids.index('EEE900'))

    def test_batchwise_sort_prioritizes_latest_batch_before_department(self):
        response = self.client.get(reverse('student_list'), {'sort': 'batch_dept_serial'})

        ordered_ids = [student.student_id for student in response.context['page_obj'].paginator.object_list]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ordered_ids[0], self.latest_eee_student.student_id)
        self.assertLess(ordered_ids.index('CSE001'), ordered_ids.index('EEE001'))

    def test_htmx_directory_results_include_synced_controls(self):
        response = self.client.get(
            reverse('student_list'),
            {'program': self.cse_program.name, 'per_page': 10},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-target="#directory-results"')
        self.assertContains(response, 'hx-include="#directory-filter-form"')
        self.assertContains(response, 'id="total-count-display"')
        self.assertContains(response, reverse('export_students_all'))

    def test_directory_pagination_and_page_size_preserve_filters(self):
        response = self.client.get(
            reverse('student_list'),
            {'program': self.cse_program.name, 'page': 2, 'per_page': 10},
            HTTP_HX_REQUEST='true',
        )

        page_obj = response.context['page_obj']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.paginator.per_page, 10)
        self.assertTrue(all(student.program == self.cse_program.name for student in page_obj.object_list))
        self.assertContains(response, 'directory-per-page-control')
        self.assertContains(response, 'hx-get="/students/?page=1"')

    def test_htmx_pagination_footer_hides_filtered_count_sentence(self):
        response = self.client.get(
            reverse('student_list'),
            {'program': self.cse_program.name},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Showing <strong>')

    def test_api_preview_id_requires_add_student_permission(self):
        self.client.force_login(self.scoped_user)

        response = self.client.get(reverse('api_preview_id'))

        self.assertRedirects(response, reverse('user_profile'))

    def test_bulk_update_rejects_unknown_field(self):
        response = self.client.post(reverse('api_bulk_update_execute'), {
            'student_ids': self.inactive_student.student_id,
            'field_name': 'student_name',
            'new_value': 'Changed By Bulk Update',
        })

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'cannot be updated in bulk', status_code=400)
        self.inactive_student.refresh_from_db()
        self.assertEqual(self.inactive_student.student_name, 'Inactive CSE Student')

    def test_scoped_user_sees_and_exports_mapped_programs(self):
        self.client.force_login(self.scoped_user)

        response = self.client.get(reverse('student_list'))
        visible_programs = {student.program for student in response.context['page_obj'].paginator.object_list}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(visible_programs, {self.cse_program.name, 'CSE'})

        export_response = self.client.get(reverse('export_students'))
        export_df = self.read_excel(export_response)
        self.assertEqual(set(export_df['program']), {self.cse_program.name, 'CSE'})
        self.assertEqual(len(export_df), 17)

    def test_standard_export_matches_filtered_directory_dataset(self):
        params = {'program': self.cse_program.name, 'status': 'Inactive'}
        list_response = self.client.get(reverse('student_list'), params)
        export_response = self.client.get(reverse('export_students'), params)

        self.assertEqual(list_response.context['total_count'], 1)
        export_df = self.read_excel(export_response)
        self.assertEqual(len(export_df), 1)
        self.assertEqual(export_df.iloc[0]['student_id'], self.inactive_student.student_id)

    def test_export_respects_selected_sort_order(self):
        response = self.client.get(reverse('export_students'), {'sort': 'batch_dept_serial'})

        export_df = self.read_excel(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(export_df.iloc[0]['student_id'], self.latest_eee_student.student_id)

    def test_all_info_export_includes_all_student_fields(self):
        response = self.client.get(reverse('export_students_all'), {'search': self.inactive_student.student_id})

        export_df = self.read_excel(response)
        expected_columns = [field.name for field in Student._meta.concrete_fields]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(export_df.columns), expected_columns)
        self.assertEqual(len(export_df), 1)
        self.assertEqual(export_df.iloc[0]['student_id'], self.inactive_student.student_id)

    def test_student_photo_url_handles_relative_and_absolute_paths(self):
        self.assertEqual(self.inactive_student.photo_url, '/media/photos/inactive.jpg')
        self.assertEqual(self.cancelled_student.photo_url, 'https://example.com/cancelled.jpg')

    def test_quick_info_card_shows_only_extra_details_not_visible_in_rows(self):
        response = self.client.get(reverse('student_short_info', args=[self.inactive_student.student_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quick Student Details')
        self.assertContains(response, self.inactive_student.student_email)
        self.assertContains(response, self.inactive_student.father_mobile)
        self.assertContains(response, self.inactive_student.mother_mobile)
        self.assertContains(response, self.inactive_student.emergency_contact)
        self.assertContains(response, self.inactive_student.present_address)
        self.assertContains(response, self.inactive_student.permanent_address)
        self.assertContains(response, self.inactive_student.blood_group)
        self.assertContains(response, self.inactive_student.religion)
        self.assertNotContains(response, self.inactive_student.father_name)
        self.assertNotContains(response, self.inactive_student.program)
        self.assertNotContains(response, 'Open Profile')
