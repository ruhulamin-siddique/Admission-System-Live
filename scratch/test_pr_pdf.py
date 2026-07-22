import os
import sys
sys.path.insert(0, os.getcwd())
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admission_system.settings')
django.setup()

from public_relations.models import PublicRelationsArchive
from public_relations.utils import render_archive_pdf

entry = PublicRelationsArchive.objects.first()
if entry:
    class DummyRequest:
        def build_absolute_uri(self, location=''):
            return location

    resp = render_archive_pdf(DummyRequest(), entry.pk)
    if resp and resp.status_code == 200:
        out_pdf = r'd:\My Drive\1-Python\1-Admission\scratch\pr_archive_test.pdf'
        with open(out_pdf, 'wb') as f:
            f.write(resp.content)
        print("Generated PR Archive PDF successfully! Size:", len(resp.content))
    else:
        print("Failed to generate PR PDF:", getattr(resp, 'content', 'None'))
else:
    print("No PR Archive entry found in DB")
