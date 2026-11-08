from django.db import migrations

def rename_dba_to_bba(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Student = apps.get_model('students', 'Student')
    UserProfile = apps.get_model('core', 'UserProfile')
    
    # 1. Update Student program 'DBA' to 'BBA'
    Student.objects.using(db_alias).filter(program__iexact='dba').update(program='BBA')
    
    # 2. Update UserProfile department 'DBA' to 'BBA'
    UserProfile.objects.using(db_alias).filter(department__iexact='dba').update(department='BBA')

def reverse_rename(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('students', '0023_alter_smshistory_options_smshistory_module_name_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_dba_to_bba, reverse_rename),
    ]
