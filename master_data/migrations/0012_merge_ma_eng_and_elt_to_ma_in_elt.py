from django.db import migrations
from django.db.models import Q

def merge_ma_eng_and_elt_to_ma_in_elt(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Program = apps.get_model('master_data', 'Program')
    Cluster = apps.get_model('master_data', 'Cluster')
    Student = apps.get_model('students', 'Student')
    ProgramChangeHistory = apps.get_model('students', 'ProgramChangeHistory')
    UserProfile = apps.get_model('core', 'UserProfile')

    # 1. Resolve Arts Cluster (code '02' or name containing 'Arts')
    arts_cluster = Cluster.objects.using(db_alias).filter(code='02').first()
    if not arts_cluster:
        arts_cluster = Cluster.objects.using(db_alias).filter(name__icontains='Arts').first()
    if not arts_cluster:
        arts_cluster = Cluster.objects.using(db_alias).first()

    # 2. Locate or create the canonical 'MA in ELT' program
    canonical_prog = Program.objects.using(db_alias).filter(
        Q(short_name__iexact='MA in ELT') |
        Q(name__iexact='Master of Arts in English Language Teaching') |
        Q(name__iexact='MA in English Language Teaching') |
        Q(name__iexact='MA in ELT')
    ).first()

    if not canonical_prog:
        # Check if an existing program is named 'ELT' or 'MA in ENG' to repurpose it
        candidate = Program.objects.using(db_alias).filter(
            Q(short_name__iexact='ELT') |
            Q(name__iexact='ELT') |
            Q(short_name__iexact='MA in ENG') |
            Q(name__iexact='MA in ENG')
        ).first()

        if candidate:
            canonical_prog = candidate
            canonical_prog.name = 'Master of Arts in English Language Teaching'
            canonical_prog.short_name = 'MA in ELT'
            canonical_prog.level_code = '3'
            if arts_cluster:
                canonical_prog.cluster = arts_cluster
            if not canonical_prog.ugc_code:
                canonical_prog.ugc_code = '16'
            canonical_prog.save(using=db_alias)
        else:
            if arts_cluster:
                canonical_prog = Program.objects.using(db_alias).create(
                    name='Master of Arts in English Language Teaching',
                    short_name='MA in ELT',
                    ugc_code='16',
                    cluster=arts_cluster,
                    level_code='3',
                    sort_order=0
                )
    else:
        # Ensure canonical program details are correct
        canonical_prog.name = 'Master of Arts in English Language Teaching'
        canonical_prog.short_name = 'MA in ELT'
        canonical_prog.level_code = '3'
        if arts_cluster:
            canonical_prog.cluster = arts_cluster
        if not canonical_prog.ugc_code:
            canonical_prog.ugc_code = '16'
        canonical_prog.save(using=db_alias)

    # 3. Clean up any other obsolete/duplicate program records (e.g. 'ELT', 'MA in ENG')
    if canonical_prog:
        obsolete_progs = Program.objects.using(db_alias).filter(
            Q(name__iexact='MA in ENG') |
            Q(short_name__iexact='MA in ENG') |
            Q(name__iexact='ELT') |
            Q(short_name__iexact='ELT')
        ).exclude(pk=canonical_prog.pk)
        obsolete_progs.delete()

    # 4. Update Student records:
    # Any student having program 'MA in ENG', 'ELT', 'MA in English' (case-insensitive)
    # becomes program='MA in ELT' and program_type='Masters'
    for old_val in ['MA in ENG', 'ELT', 'MA in English', 'ma in eng', 'elt']:
        Student.objects.using(db_alias).filter(program__iexact=old_val).update(
            program='MA in ELT',
            program_type='Masters'
        )

    # 5. Update ProgramChangeHistory records if present
    for old_val in ['MA in ENG', 'ELT', 'MA in English', 'ma in eng', 'elt']:
        ProgramChangeHistory.objects.using(db_alias).filter(old_program__iexact=old_val).update(
            old_program='MA in ELT'
        )
        ProgramChangeHistory.objects.using(db_alias).filter(new_program__iexact=old_val).update(
            new_program='MA in ELT'
        )

    # 6. Update UserProfile department scope if present
    for old_val in ['MA in ENG', 'ELT', 'ma in eng', 'elt']:
        UserProfile.objects.using(db_alias).filter(department_scope__iexact=old_val).update(
            department_scope='MA in ELT'
        )
        UserProfile.objects.using(db_alias).filter(department__iexact=old_val).update(
            department='MA in ELT'
        )

def rollback(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('master_data', '0011_alter_program_unique_together'),
        ('students', '0025_alter_smshistory_module_name'),
        ('core', '0018_seed_coe_roles'),
    ]

    operations = [
        migrations.RunPython(merge_ma_eng_and_elt_to_ma_in_elt, rollback),
    ]
