from django.db import migrations

def set_english_short_name_and_normalize(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Program = apps.get_model('master_data', 'Program')
    Student = apps.get_model('students', 'Student')
    
    # 1. Update the program "English" to have short_name='ENG'
    Program.objects.using(db_alias).filter(name__iexact='English').update(short_name='ENG')
    
    # 2. Normalize student records where program is 'English' to 'ENG'
    Student.objects.using(db_alias).filter(program__iexact='English').update(program='ENG')

def rollback(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Program = apps.get_model('master_data', 'Program')
    Program.objects.using(db_alias).filter(name__iexact='English').update(short_name=None)

class Migration(migrations.Migration):

    dependencies = [
        ('master_data', '0007_alter_program_ugc_code_alter_program_unique_together'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_english_short_name_and_normalize, rollback),
    ]
