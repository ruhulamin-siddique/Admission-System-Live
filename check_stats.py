import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admission_system.settings')
django.setup()

from students.models import Student

now = timezone.now()
today = now.date()
count = Student.objects.filter(admission_date=today).count()
print(f"Students with admission_date today ({today}): {count}")

total = Student.objects.count()
print(f"Total students in database: {total}")

if total > 0:
    latest = Student.objects.order_by('-created_at').first()
    print(f"Latest student: {latest.student_name}, ID: {latest.student_id}, Admission Date: {latest.admission_date}")
