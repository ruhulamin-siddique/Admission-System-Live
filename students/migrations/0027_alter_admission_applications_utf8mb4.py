from django.db import migrations


def convert_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        with schema_editor.connection.cursor() as cursor:
            # Set default charset on tables
            cursor.execute("ALTER TABLE students_admissionapplicationtype DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE students_studentapplication DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE students_admissionapplicationconfig DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

            # Convert only text/string columns that store Bangla/Unicode (do NOT touch foreign key columns)
            cursor.execute("""
                ALTER TABLE students_admissionapplicationtype
                    MODIFY title_bn VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                    MODIFY title_en VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                    MODIFY subject VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                    MODIFY body_template LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """)

            cursor.execute("""
                ALTER TABLE students_studentapplication
                    MODIFY student_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                    MODIFY department VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                    MODIFY office_notes LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """)


def seed_types(apps, schema_editor):
    from students.application_registry import seed_admission_application_types
    seed_admission_application_types()


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0026_admissionapplicationconfig_admissionapplicationtype_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_to_utf8mb4, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(seed_types, reverse_code=migrations.RunPython.noop),
    ]
