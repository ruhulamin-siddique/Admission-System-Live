from django.test import Client, TestCase, override_settings

from students.models import Student

from .models import APIClient, APIRequestLog


@override_settings(EXTERNAL_API_REQUIRE_HTTPS=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class ExternalAPITests(TestCase):
    def setUp(self):
        self.api_client = APIClient(name='Partner SIS', scopes=['students:read'], rate_limit_per_minute=10)
        self.raw_key = self.api_client.set_new_key()
        self.api_client.save()
        self.http = Client()
        Student.objects.create(student_id='S-1001', student_name='Test Student', program='CSE', admission_status='Active')

    def auth_headers(self, key=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {key or self.raw_key}'}

    def test_student_list_requires_valid_key_and_logs_denial(self):
        response = self.http.get('/external-api/v1/students/', HTTP_AUTHORIZATION='Bearer invalid')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(APIRequestLog.objects.filter(status='DENIED').count(), 1)

    def test_student_list_returns_authorized_data_and_logs_success(self):
        response = self.http.get('/external-api/v1/students/', **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['student_id'], 'S-1001')
        self.assertEqual(APIRequestLog.objects.filter(client=self.api_client, status='SUCCESS').count(), 1)

    def test_pii_requires_explicit_scope(self):
        response = self.http.get('/external-api/v1/students/S-1001/', **self.auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('national_id', response.json()['result'])

    def test_report_summary_requires_report_scope(self):
        response = self.http.get('/external-api/v1/reports/summary/', **self.auth_headers())

        self.assertEqual(response.status_code, 403)
        self.assertIn('Missing required scope', response.json()['error'])

    def test_student_list_rejects_invalid_query_parameters(self):
        cases = [
            {'page_size': 'abc'},
            {'page': '0'},
            {'admission_year': 'twenty'},
        ]

        for params in cases:
            with self.subTest(params=params):
                response = self.http.get('/external-api/v1/students/', params, **self.auth_headers())
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
