from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from master_data.models import Program, Cluster

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
