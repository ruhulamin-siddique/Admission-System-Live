from django.core.management.base import BaseCommand
from master_data.models import Cluster, Program, Hall, AdmissionYear, Semester, Batch

class Command(BaseCommand):
    help = 'Seed initial master data'

    def handle(self, *args, **kwargs):
        # Clusters
        eng, _ = Cluster.objects.get_or_create(name="Engineering & Technology", code="05")
        biz, _ = Cluster.objects.get_or_create(name="Business", code="04")
        arts, _ = Cluster.objects.get_or_create(name="Arts", code="02")

        # Programs
        Program.objects.get_or_create(name="CSE", ugc_code="01", cluster=eng, level_code='1')
        Program.objects.get_or_create(name="EEE", ugc_code="02", cluster=eng, level_code='1')
        Program.objects.get_or_create(name="BBA", ugc_code="08", cluster=biz, level_code='1')
        Program.objects.get_or_create(name="English", ugc_code="09", cluster=arts, level_code='1')

        # Halls
        Hall.objects.get_or_create(name="AUAH", code="02")
        Hall.objects.get_or_create(name="TBH", code="01")
        Hall.objects.get_or_create(name="ZH", code="04")
        Hall.objects.get_or_create(name="Non-Residential", code="00")

        # Years
        y24, _ = AdmissionYear.objects.get_or_create(year=2024)
        y25, _ = AdmissionYear.objects.get_or_create(year=2025)

        # Semesters
        Semester.objects.get_or_create(name="Spring", code="1")
        Semester.objects.get_or_create(name="Summer", code="2")
        Semester.objects.get_or_create(name="Fall", code="2")
        Semester.objects.get_or_create(name="Winter", code="1")

        self.stdout.write(self.style.SUCCESS('Successfully seeded master data'))
