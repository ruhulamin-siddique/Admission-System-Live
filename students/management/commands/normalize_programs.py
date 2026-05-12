from django.core.management.base import BaseCommand
from students.models import Student
from students.utils import get_canonical_program_name
from django.db import transaction, models

class Command(BaseCommand):
    help = 'Normalizes student program names to short versions (e.g., Computer Science and Engineering -> CSE)'

    def handle(self, *args, **options):
        students = Student.objects.all()
        total = students.count()
        updated = 0
        
        self.stdout.write(f'Starting normalization of {total} student records...')
        
        with transaction.atomic():
            for student in students:
                old_name = student.program
                if not old_name:
                    continue
                    
                new_name = get_canonical_program_name(old_name)
                
                # Further sync Cluster and Type from Master Data
                from master_data.models import Program
                prog_obj = Program.objects.filter(
                    models.Q(name__iexact=old_name) | models.Q(short_name__iexact=old_name)
                ).first()
                
                changed = False
                if old_name != new_name:
                    student.program = new_name
                    changed = True
                
                if prog_obj:
                    if student.cluster != prog_obj.cluster.name:
                        student.cluster = prog_obj.cluster.name
                        changed = True
                    if student.program_type != prog_obj.get_level_code_display():
                        student.program_type = prog_obj.get_level_code_display()
                        changed = True
                
                if changed:
                    student.save()
                    updated += 1
                    
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} records.'))
