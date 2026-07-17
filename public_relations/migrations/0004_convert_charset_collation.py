# Generated manually to handle MySQL charset/collation issues

from django.db import migrations

def convert_to_utf8(apps, schema_editor):
    if schema_editor.connection.vendor == 'mysql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public_relations_mediahouse CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE public_relations_publicrelationsarchive CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE public_relations_mediacoverage CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE public_relations_mediaasset CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

def rollback_utf8(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('public_relations', '0003_alter_mediahouse_media_type_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_to_utf8, rollback_utf8),
    ]
