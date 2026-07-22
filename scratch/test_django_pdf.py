import os
import sys
sys.path.insert(0, os.getcwd())
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admission_system.settings')
django.setup()

from students.views import render_to_pdf
from students.models import Student

student = Student.objects.first()
if student:
    context = {'student': student, 'today': '2026-07-22'}
    resp = render_to_pdf('students/reports/pdf/master_sheet.html', context)
    if resp:
        out_pdf = r'd:\My Drive\1-Python\1-Admission\scratch\django_master_sheet_test.pdf'
        with open(out_pdf, 'wb') as f:
            f.write(resp.content)
        print("Generated Django Master Sheet PDF successfully! Size:", len(resp.content))
    else:
        print("Failed to generate PDF")
else:
    print("No student found in DB")
