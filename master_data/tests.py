from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from master_data.models import Program, Cluster, Hall

class ProgramPDFTests(TestCase):
    def setUp(self):
        # Create user
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        
        # Create cluster and programs
        self.cluster = Cluster.objects.create(name='Engineering', code='05')
        self.program = Program.objects.create(
            name='Computer Science and Engineering',
            short_name='CSE',
            ugc_code='01',
            cluster=self.cluster,
            level_code='1'
        )

    def test_pdf_generation_requires_login(self):
        url = reverse('generate_programs_pdf')
        response = self.client.get(url)
        # Should redirect to login page since login is required
        self.assertEqual(response.status_code, 302)

    def test_pdf_generation_success(self):
        self.client.force_login(self.superuser)
        url = reverse('generate_programs_pdf')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Check that PDF has inline attachment header
        self.assertIn('inline', response['Content-Disposition'])
        self.assertIn('BAUST_Academic_Programs_Registry.pdf', response['Content-Disposition'])


class HallTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.force_login(self.superuser)
        
        # Create a hall to start with
        self.hall1 = Hall.objects.create(
            full_name="Abbas Uddin Ahmed Hall",
            short_name="AUAH",
            code="02"
        )

    def test_add_hall_duplicate_code_warning(self):
        url = reverse('add_master_data', args=['hall'])
        # Post a new hall with the same code "02"
        response = self.client.post(url, {
            'full_name': 'Tajuddin Ahmed Hall',
            'short_name': 'TAH',
            'code': '02'
        })
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify both halls exist in database
        self.assertEqual(Hall.objects.filter(code="02").count(), 2)
        
        # Verify the warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("Warning: A duplicate Hall code '02' has been detected", messages[0].message)

    def test_edit_hall_duplicate_code_warning(self):
        # Create a second hall with a unique code
        hall2 = Hall.objects.create(
            full_name="Tajuddin Ahmed Hall",
            short_name="TAH",
            code="01"
        )
        url = reverse('edit_master_data', args=['hall', hall2.id])
        # Edit hall2 to have code "02" (which is used by hall1)
        response = self.client.post(url, {
            'full_name': 'Tajuddin Ahmed Hall',
            'short_name': 'TAH',
            'code': '02'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify db updated
        hall2.refresh_from_db()
        self.assertEqual(hall2.code, "02")
        
        # Verify warning message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("Warning: A duplicate Hall code '02' has been detected", messages[0].message)

