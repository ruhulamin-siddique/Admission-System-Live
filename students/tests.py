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
        from students.utils import get_canonical_program_name
        if hasattr(get_canonical_program_name, '_cache'):
            delattr(get_canonical_program_name, '_cache')
            
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
        response = self.client.get(
            reverse('student_list'),
            {'search': self.inactive_student.student_id},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>Parents</th>', html=True)
        self.assertContains(response, f'Father: {self.inactive_student.father_name}')
        self.assertContains(response, f'Mother: {self.inactive_student.mother_name}')

    def test_directory_page_has_clear_filters_button(self):
        response = self.client.get(reverse('student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'btn-clear-filters')
        self.assertContains(response, 'name="sort"')
        self.assertContains(response, '?per_page=25')
        self.assertContains(response, 'sort=dept_batch_serial')

    def test_directory_filters_work_for_visible_fields(self):
        cases = (
            ({'search': 'Inactive CSE Student'}, lambda rows: rows == [self.inactive_student]),
            ({'year': '2024'}, lambda rows: all(student.admission_year == 2024 for student in rows)),
            ({'dept': 'Business & Management'}, lambda rows: rows == [self.mba_student]),
            ({'program': 'CSE'}, lambda rows: all(student.program == 'CSE' for student in rows)),
            ({'batch': 'MBA-1'}, lambda rows: rows == [self.mba_student]),
            ({'type': 'Masters'}, lambda rows: rows == [self.mba_student]),
            ({'gender': 'Female'}, lambda rows: rows and all(student.gender == 'Female' for student in rows)),
        )

        for params, assertion in cases:
            with self.subTest(params=params):
                response = self.client.get(
                    reverse('student_list'),
                    params,
                    HTTP_HX_REQUEST='true',
                )
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
            {'program': 'CSE', 'page': 2, 'per_page': 10},
            HTTP_HX_REQUEST='true',
        )

        page_obj = response.context['page_obj']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.paginator.per_page, 10)
        self.assertTrue(all(student.program == 'CSE' for student in page_obj.object_list))
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
        self.assertEqual(visible_programs, {'CSE'})

        export_response = self.client.get(reverse('export_students'))
        export_df = self.read_excel(export_response)
        self.assertEqual(set(export_df['program']), {'CSE'})
        self.assertEqual(len(export_df), 17)

    def test_standard_export_matches_filtered_directory_dataset(self):
        params = {'program': 'CSE', 'status': 'Inactive'}
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
        self.assertNotContains(response, self.cse_program.name)
        self.assertNotContains(response, 'Open Profile')

    def test_institutional_report_access_and_rendering(self):
        # Update some students to have ssc_school and hsc_college
        student1 = Student.objects.get(student_id='CSE001')
        student1.ssc_school = 'Lions School'
        student1.hsc_college = 'Lions College'
        student1.save()

        student2 = Student.objects.get(student_id='CSE002')
        student2.ssc_school = 'Lions School'
        student2.hsc_college = 'Blue College'
        student2.save()

        # Check access for superuser
        response = self.client.get(reverse('institutional_report'), {'year': '2025'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lions School')
        self.assertContains(response, 'Lions College')
        self.assertContains(response, 'Blue College')

        # Check access denied for scoped_user (no view_analytics under reports)
        self.client.force_login(self.scoped_user)
        response = self.client.get(reverse('institutional_report'))
        self.assertRedirects(response, reverse('user_profile'))

    def test_api_institutional_students_modal_data(self):
        student1 = Student.objects.get(student_id='CSE001')
        student1.ssc_school = 'Lions School'
        student1.save()

        # Query API for students from Lions School
        response = self.client.get(reverse('api_institutional_students'), {'school': 'Lions School', 'year': '2025'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CSE001')
        self.assertContains(response, 'Lions School')
        # Print URL should be formatted in response
        self.assertContains(response, reverse('print_institutional_students'))

    def test_print_institutional_students_view(self):
        student1 = Student.objects.get(student_id='CSE001')
        student1.ssc_school = 'Lions School'
        student1.save()

        response = self.client.get(reverse('print_institutional_students'), {'school': 'Lions School'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CSE001')
        self.assertContains(response, 'Lions School')
        self.assertContains(response, 'window.print()')

    def test_dashboard_reference_nodes(self):
        # Update some students to have references
        student1 = Student.objects.get(student_id='CSE001')
        student1.reference = 'Facebook Ad'
        student1.batch = '26th'
        student1.save()

        student2 = Student.objects.get(student_id='CSE002')
        student2.reference = 'Alumni Network'
        student2.batch = '26th'
        student2.save()

        student3 = Student.objects.get(student_id='CSE003')
        student3.reference = 'Facebook Ad'
        student3.batch = '26th'
        student3.save()

        # Query the dashboard
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Assert top_references is in context
        stats = response.context['stats']
        self.assertIn('top_references', stats)
        
        # Verify Facebook Ad is ranked #1 (since it has 2 count, Alumni has 1)
        top_refs = stats['top_references']
        self.assertEqual(top_refs[0]['reference'], 'Facebook Ad')
        self.assertEqual(top_refs[0]['count'], 2)
        self.assertEqual(top_refs[1]['reference'], 'Alumni Network')
        self.assertEqual(top_refs[1]['count'], 1)

        # Assert page rendering has the reference text
        self.assertContains(response, 'Admission Reference')
        self.assertContains(response, 'Facebook Ad')
        self.assertContains(response, 'Alumni Network')

    def test_student_field_audit_and_revert(self):
        from students.models import StudentFieldHistory
        
        # 1. Edit a student's profile and confirm changes are logged
        student = Student.objects.get(student_id='CSE001')
        self.assertEqual(student.student_name, 'CSE Student 01')
        
        student.student_name = 'Updated Name'
        student.changed_by_user = self.superuser
        student.save()
        
        # Verify history entry was created
        history = StudentFieldHistory.objects.filter(student=student, field_name='student_name')
        self.assertEqual(history.count(), 1)
        entry = history.first()
        self.assertEqual(entry.old_value, 'CSE Student 01')
        self.assertEqual(entry.new_value, 'Updated Name')
        self.assertEqual(entry.changed_by, self.superuser)
        self.assertFalse(entry.reverted)
        
        # 2. Test permission checks on the revert API
        revert_url = reverse('revert_field_change', args=[entry.id])
        
        # Non-superuser should be denied (returns 403)
        self.client.force_login(self.scoped_user)
        resp_scoped = self.client.post(revert_url)
        self.assertEqual(resp_scoped.status_code, 403)
        
        # Superuser should succeed (returns 200 JSON with success: True)
        self.client.force_login(self.superuser)
        resp_super = self.client.post(revert_url)
        self.assertEqual(resp_super.status_code, 200)
        self.assertTrue(resp_super.json()['success'])
        
        # Verify database reverted to old value
        student.refresh_from_db()
        self.assertEqual(student.student_name, 'CSE Student 01')
        
        # Verify history entry state updated
        entry.refresh_from_db()
        self.assertTrue(entry.reverted)
        self.assertEqual(entry.reverted_by, self.superuser)
        self.assertIsNotNone(entry.reverted_at)

    def test_dashboard_batch_department_matrix(self):
        # Request the dashboard page
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        # Assert context variables are present
        self.assertIn('matrix_cols', response.context)
        self.assertIn('matrix_rows', response.context)
        self.assertIn('column_totals', response.context)
        self.assertIn('grand_total', response.context)

        cols = response.context['matrix_cols']
        rows = response.context['matrix_rows']

        # Assert column headers (programs) are sorted alphabetically
        self.assertEqual(cols, sorted(cols))

        # Assert rows (batches) are sorted descending by batch_number
        prev_num = float('inf')
        for r in rows:
            batch_num = r['batch_number'] or 0
            self.assertTrue(batch_num <= prev_num, f"Batch {r['batch_name']} with number {batch_num} is out of order (previous was {prev_num})")
            prev_num = batch_num

        # Assert grand total sums up all students in database
        self.assertEqual(response.context['grand_total'], Student.objects.count())

    def test_ugc_id_generation_program_lookup_exact(self):
        from students.utils import generate_next_ugc_id, generate_ugc_prefix
        from master_data.models import Cluster, Program

        # 1. Create a dummy Arts cluster and English program
        arts_cluster = Cluster.objects.create(name='Arts', code='02')
        english_program = Program.objects.create(
            name='English',
            short_name='ENG',
            ugc_code='09',
            cluster=arts_cluster,
            level_code='1'
        )

        # 2. Create a dummy Civil Engineering program that could clash if contains matches
        civil_program = Program.objects.create(
            name='Civil Engineering',
            short_name='CE',
            ugc_code='04',
            cluster=self.cse_program.cluster,  # Engineering cluster code '05'
            level_code='1'
        )

        # Test generate_next_ugc_id for program_name='ENG'
        # Arts code = 02, English ugc_code = 09, Level code = 1. Part CcssP should be 02091
        next_id = generate_next_ugc_id(
            admission_year=2026,
            semester_name='Spring',
            hall_name='Non-Residential',
            program_name='ENG',
            cluster_name='Arts'
        )
        # UGC ID prefix: UUU(080) YY(26) S(1) HH(00) CcssP(02091)
        expected_prefix = "0802610002091"
        self.assertTrue(next_id.startswith(expected_prefix), f"Expected ID to start with {expected_prefix}, got {next_id}")

        # Test generate_ugc_prefix for program_name='ENG'
        prefix = generate_ugc_prefix(
            admission_year=2026,
            semester_name='Spring',
            hall_name='Non-Residential',
            program_name='ENG',
            cluster_name='Arts'
        )
        self.assertEqual(prefix, expected_prefix)

    def test_excel_import_logs_activity(self):
        from core.models import ActivityLog
        # Create Excel file in-memory
        data = {
            'student_id': ['0802510001011001'],
            'student_name': ['IMPORT STUDENT ONE'],
            'program': ['CSE'],
            'admission_status': ['Active'],
            'gender': ['Male']
        }
        df = pd.DataFrame(data)
        excel_file = BytesIO()
        df.to_excel(excel_file, index=False)
        excel_file.seek(0)
        excel_file.name = 'test_import.xlsx'

        # Perform POST request to import_students
        import_url = reverse('import_students')
        response = self.client.post(import_url, {'excel_file': excel_file})
        self.assertEqual(response.status_code, 200)

        # Check that Student was created
        student_exists = Student.objects.filter(student_id='0802510001011001').exists()
        self.assertTrue(student_exists)

        # Check ActivityLog entry
        log_entry = ActivityLog.objects.filter(module='students', object_id='0802510001011001', action_type='CREATE').first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.superuser)
        self.assertIn('Imported student record', log_entry.description)

        # Now test the timeline rendering of the imported student profile view!
        profile_url = reverse('student_profile', args=['0802510001011001'])
        profile_response = self.client.get(profile_url)
        self.assertEqual(profile_response.status_code, 200)
        timeline = profile_response.context['timeline']
        
        # Verify timeline has correct import details
        import_event = next((e for e in timeline if 'Imported' in e['title'] or 'Record Imported' in e['title']), None)
        self.assertIsNotNone(import_event)
        self.assertEqual(import_event['user'], self.superuser.username)
        self.assertIn('imported into the system via Excel spreadsheet', import_event['description'])

    def test_api_matrix_students_drilldown(self):
        # We query the api_matrix_students endpoint for CSE and batch 25th
        matrix_url = reverse('api_matrix_students')
        
        # Test specific batch and program filter
        response = self.client.get(matrix_url, {'batch': '25th', 'program': 'CSE'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Showing')
        self.assertContains(response, 'CSE Student')
        
        # Test total column drill-down (all programs in batch)
        response_batch_total = self.client.get(matrix_url, {'batch': '25th', 'program': 'Total'})
        self.assertEqual(response_batch_total.status_code, 200)
        self.assertContains(response_batch_total, 'CSE Student')
        self.assertContains(response_batch_total, 'EEE Student')
        
        # Test total row drill-down (all batches in program)
        response_program_total = self.client.get(matrix_url, {'batch': 'Total', 'program': 'CSE'})
        self.assertEqual(response_program_total.status_code, 200)
        self.assertContains(response_program_total, 'CSE Student')
        
        # Test grand total drill-down
        response_grand_total = self.client.get(matrix_url, {'batch': 'Total', 'program': 'Total'})
        self.assertEqual(response_grand_total.status_code, 200)
        self.assertContains(response_grand_total, 'CSE Student')
        self.assertContains(response_grand_total, 'EEE Student')
        self.assertContains(response_grand_total, 'MBA Student')

    def test_legacy_student_form_validation(self):
        from students.forms import StudentForm
        form_data = {
            'student_name': 'Legacy test student',
            'is_legacy_student': 'on',
            'old_student_id': '123456789',
            'program': self.cse_program.name,
            'admission_year': 2024,
            'semester_name': 'Spring',
            'program_type': 'Bachelor',
            'batch': '24th',
            'current_batch': '24th',
            'current_semester': 'Level 1 Term I',
            'student_mobile': '01700000000',
            'father_mobile': '01700000001',
            'mother_mobile': '01700000002',
            'ssc_school': 'SSC School',
            'ssc_year': '2022',
            'ssc_board': 'Dhaka',
            'ssc_roll': '123456',
            'ssc_gpa': 5.00,
            'hsc_college': 'HSC College',
            'hsc_year': '2024',
            'hsc_board': 'Dhaka',
            'hsc_roll': '123456',
            'hsc_gpa': 5.00,
            'admission_payment': 10000,
            'admission_status': 'Active',
        }
        form = StudentForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertIsNotNone(form.cleaned_data['student_id'])
        self.assertTrue(form.cleaned_data['student_id'].startswith('080'))

    def test_api_student_ugc_id_preview(self):
        # Create a legacy student with missing academic parameters
        legacy_student_missing = Student.objects.create(
            student_id='999999',
            student_name='Legacy Missing Fields',
            is_legacy_student=True,
            admission_year=None,
            semester_name=None,
            hall_attached=None,
            program=None,
            cluster=None
        )
        
        url = reverse('api_student_ugc_id_preview', kwargs={'student_id': legacy_student_missing.student_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Required academic parameters are missing', data['error'])
        
        # Fill in the academic parameters and retry
        legacy_student_missing.admission_year = 2025
        legacy_student_missing.semester_name = 'Spring'
        legacy_student_missing.hall_attached = 'Non-Residential'
        legacy_student_missing.program = self.cse_program.name
        legacy_student_missing.cluster = self.cse_program.cluster.name
        legacy_student_missing.program_type = 'Bachelor'
        legacy_student_missing.save()
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIsNotNone(data['suggested_id'])
        self.assertEqual(len(data['suggested_id']), 16)
        self.assertTrue(data['suggested_id'].startswith('0802510005011'))

    def test_legacy_student_unlocked_fields(self):
        # Create a standard student with a 16-digit ID
        std_student = Student.objects.create(
            student_id='0802510005011001',
            student_name='Standard Student',
            is_legacy_student=False,
            admission_year=2025,
            semester_name='Spring',
            hall_attached='Non-Residential',
            program=self.cse_program.name,
            cluster=self.cse_program.cluster.name,
            program_type='Bachelor'
        )
        
        # Create a legacy student with a 9-digit ID
        legacy_student = Student.objects.create(
            student_id='190103024',
            student_name='Legacy Student',
            is_legacy_student=True,
            admission_year=2019,
            semester_name='Spring',
            hall_attached='Non-Residential',
            program=self.cse_program.name,
            cluster=self.cse_program.cluster.name,
            program_type='Bachelor'
        )
        
        # Test GET on edit view for standard student (fields should be disabled)
        url_std = reverse('edit_student', kwargs={'student_id': std_student.student_id})
        res_std = self.client.get(url_std)
        self.assertEqual(res_std.status_code, 200)
        form_std = res_std.context['form']
        self.assertEqual(form_std.fields['program'].widget.attrs.get('disabled'), 'disabled')
        self.assertEqual(form_std.fields['admission_year'].widget.attrs.get('disabled'), 'disabled')
        
        # Test GET on edit view for legacy student (fields should NOT be disabled)
        url_legacy = reverse('edit_student', kwargs={'student_id': legacy_student.student_id})
        res_legacy = self.client.get(url_legacy)
        self.assertEqual(res_legacy.status_code, 200)
        form_legacy = res_legacy.context['form']
        self.assertIsNone(form_legacy.fields['program'].widget.attrs.get('disabled'))
        self.assertIsNone(form_legacy.fields['admission_year'].widget.attrs.get('disabled'))

    def test_smart_campus_excel_export(self):
        # Trigger the SMART CAMPUS export URL
        response = self.client.get(reverse('export_students_smart_campus'))
        self.assertEqual(response.status_code, 200)

        # Parse the downloaded Excel content
        df = self.read_excel(response)

        # 1. Verify that 'current_batch' and 'current_semester' fields are removed
        self.assertNotIn('current_batch', df.columns)
        self.assertNotIn('current_semester', df.columns)

        # 2. Verify that 'batch' and 'semester_name' are still present
        self.assertIn('batch', df.columns)
        self.assertIn('semester_name', df.columns)

        # 3. Verify that the cancelled student (CSE901) is included in the exported students list
        student_ids = df['student_id'].astype(str).tolist()
        self.assertIn('CSE901', student_ids)

        # 4. Verify that semester_name is formatted correctly (e.g. combined with year, like "Spring 2025")
        # For CSE Student 01, it was 'Spring' and '2025' admission_year
        cse001_row = df[df['student_id'] == 'CSE001'].iloc[0]
        self.assertEqual(cse001_row['semester_name'], 'Spring 2025')

        # 5. Verify row styling for the cancelled student (CSE901) using openpyxl
        # Reading using openpyxl directly to verify colors
        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(response.content))
        ws = wb['Students']
        
        # Row 1 is header, find the row index for CSE901
        cse901_row_idx = None
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=2).value == 'CSE901':  # student_id column is 2nd column (SL is 1st)
                cse901_row_idx = r
                break
        
        self.assertIsNotNone(cse901_row_idx)
        # Check that the cells in that row have the yellow fill (hex FFF2CC)
        cell_fill = ws.cell(row=cse901_row_idx, column=2).fill
        self.assertIn(cell_fill.start_color.rgb, ['00FFF2CC', 'FFFFF2CC', 'FFF2CC'])

    def test_smart_campus_dept_wise_zip_export(self):
        import zipfile
        # Trigger the department-wise SMART CAMPUS export URL
        response = self.client.get(reverse('export_students_smart_campus_dept'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

        # Load the ZIP file
        zip_file = zipfile.ZipFile(BytesIO(response.content))
        file_list = zip_file.namelist()

        # 1. Verify that files are generated for each program in the dataset (CSE, EEE, MBA)
        self.assertIn('CSE_smart_campus_export.xlsx', file_list)
        self.assertIn('EEE_smart_campus_export.xlsx', file_list)
        self.assertIn('MBA_smart_campus_export.xlsx', file_list)

        # 2. Extract and inspect one of the Excel sheets (CSE)
        cse_excel_data = zip_file.read('CSE_smart_campus_export.xlsx')
        df = pd.read_excel(BytesIO(cse_excel_data))

        # Verify columns are correct (no current_batch, current_semester)
        self.assertNotIn('current_batch', df.columns)
        self.assertNotIn('current_semester', df.columns)
        self.assertIn('batch', df.columns)
        self.assertIn('semester_name', df.columns)

        # Verify that the cancelled CSE student is included in the CSE export
        student_ids = df['student_id'].astype(str).tolist()
        self.assertIn('CSE901', student_ids)

        # Verify row styling for the cancelled student inside the zipped Excel
        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(cse_excel_data))
        ws = wb['Students']
        
        cse901_row_idx = None
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=2).value == 'CSE901':
                cse901_row_idx = r
                break
        
        self.assertIsNotNone(cse901_row_idx)
        cell_fill = ws.cell(row=cse901_row_idx, column=2).fill
        self.assertIn(cell_fill.start_color.rgb, ['00FFF2CC', 'FFFFF2CC', 'FFF2CC'])

    def test_smart_campus_dept_wise_modal_view(self):
        # Trigger the modal endpoint
        response = self.client.get(reverse('export_students_smart_campus_dept_modal'))
        self.assertEqual(response.status_code, 200)

        # 1. Verify that the modal lists the correct departments and counts in context
        departments = response.context['departments']
        self.assertEqual(len(departments), 3)  # CSE, EEE, MBA

        # CSE has 15 standard + 1 inactive + 1 cancelled + 1 legacy scope = 18 students
        cse_dept = next(d for d in departments if d['name'] == 'CSE')
        self.assertEqual(cse_dept['count'], 18)

        # EEE has 4 standard + 1 latest = 5 students
        eee_dept = next(d for d in departments if d['name'] == 'EEE')
        self.assertEqual(eee_dept['count'], 5)

        # MBA has 1 student
        mba_dept = next(d for d in departments if d['name'] == 'MBA')
        self.assertEqual(mba_dept['count'], 1)

        # 2. Verify download links are set up and override program filter
        self.assertIn('program=CSE', cse_dept['download_url'])
        self.assertIn('program=EEE', eee_dept['download_url'])
        self.assertIn('program=MBA', mba_dept['download_url'])

        # 3. Verify ZIP download URL is in context
        self.assertEqual(response.context['zip_download_url'], reverse('export_students_smart_campus_dept'))




