from django.db import migrations

def normalize_program_names(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    Program = apps.get_model('master_data', 'Program')
    
    # Build a lookup mapping
    progs = list(Program.objects.all())
    cache = {}
    for p in progs:
        canonical = p.short_name if p.short_name else p.name
        cache[p.name.upper()] = canonical
        if p.short_name:
            cache[p.short_name.upper()] = canonical
            
    for student in Student.objects.exclude(program__isnull=True).exclude(program=''):
        key = str(student.program).strip().upper()
        if key in cache:
            canonical = cache[key]
            if student.program != canonical:
                student.program = canonical
                student.save(update_fields=['program'])

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_student_academic_verification_logs_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_program_names, noop),
    ]
