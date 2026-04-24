from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from master_data.models import Cluster, Program

from .models import Role, RolePermission


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class UserSecurityManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        engineering = Cluster.objects.create(name='Engineering & Technology', code='05')
        cls.program = Program.objects.create(
            name='Computer Science and Engineering',
            short_name='CSE',
            ugc_code='01',
            cluster=engineering,
            level_code='1',
        )

        cls.security_manager_role = Role.objects.create(
            name='Security Manager',
            description='Manages staff accounts and role definitions.',
        )
        RolePermission.objects.create(role=cls.security_manager_role, module='security', task='manage_users')
        RolePermission.objects.create(role=cls.security_manager_role, module='security', task='manage_roles')

        cls.admission_role = Role.objects.create(
            name='Admission Officer',
            description='Handles admission workflows and student coordination.',
        )

        cls.manager = User.objects.create_user(
            username='security.manager',
            password='StrongPass123!',
            email='manager@example.com',
            first_name='Security',
            last_name='Manager',
        )
        cls.manager.profile.role = cls.security_manager_role
        cls.manager.profile.save()

        cls.regular_user = User.objects.create_user(
            username='staff.member',
            password='StrongPass123!',
            email='staff@example.com',
        )

        cls.scoped_user = User.objects.create_user(
            username='scoped.staff',
            password='StrongPass123!',
            email='scoped@example.com',
            first_name='Scoped',
            last_name='Staff',
        )
        cls.scoped_user.profile.role = cls.admission_role
        cls.scoped_user.profile.department_scope = cls.program.short_name
        cls.scoped_user.profile.save()

    def test_regular_authenticated_user_can_open_and_update_own_profile(self):
        self.client.force_login(self.regular_user)

        response = self.client.get(reverse('user_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Update My Information')

        response = self.client.post(reverse('user_profile'), {
            'first_name': 'General',
            'last_name': 'Staff',
            'email': 'general.staff@example.com',
        })

        self.assertRedirects(response, reverse('user_profile'))
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'General')
        self.assertEqual(self.regular_user.last_name, 'Staff')
        self.assertEqual(self.regular_user.email, 'general.staff@example.com')

    def test_user_management_supports_filters_and_dynamic_scope_choices(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('user_management'), {
            'scope': self.program.short_name,
            'status': 'active',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtered_count'], 1)
        self.assertTrue(any(value == self.program.short_name for value, _ in response.context['scope_choices']))
        self.assertContains(response, self.scoped_user.username)
        self.assertNotContains(response, self.regular_user.username)

    def test_user_management_post_updates_account_details_and_scope(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse('user_management'), {
            'action': 'update_user',
            'user_id': self.regular_user.id,
            'first_name': 'Updated',
            'last_name': 'Member',
            'email': 'updated.member@example.com',
            'role': self.admission_role.id,
            'department_scope': self.program.short_name,
        })

        self.assertRedirects(response, reverse('user_management'))
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')
        self.assertEqual(self.regular_user.last_name, 'Member')
        self.assertEqual(self.regular_user.email, 'updated.member@example.com')
        self.assertEqual(self.regular_user.profile.role, self.admission_role)
        self.assertEqual(self.regular_user.profile.department_scope, self.program.short_name)

    def test_user_create_assigns_role_scope_and_staff_status(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse('user_create'), {
            'first_name': 'New',
            'last_name': 'Officer',
            'username': 'new.officer',
            'email': 'new.officer@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'role': self.admission_role.id,
            'department_scope': self.program.short_name,
        })

        self.assertRedirects(response, reverse('user_management'))
        created_user = User.objects.get(username='new.officer')
        self.assertTrue(created_user.is_staff)
        self.assertEqual(created_user.first_name, 'New')
        self.assertEqual(created_user.last_name, 'Officer')
        self.assertEqual(created_user.profile.role, self.admission_role)
        self.assertEqual(created_user.profile.department_scope, self.program.short_name)

    def test_role_management_can_create_new_role(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse('role_management'), {
            'action': 'create_role',
            'name': 'Report Reviewer',
            'description': 'Reviews reports and export outputs.',
        })

        self.assertRedirects(response, reverse('role_management'))
        self.assertTrue(Role.objects.filter(name='Report Reviewer').exists())
