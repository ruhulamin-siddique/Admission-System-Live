# Data migration: updates existing CoeSettings SMS templates to English.
# The field 'default' only affects new records — existing rows must be
# updated via a data migration.

from django.db import migrations


def update_sms_templates_to_english(apps, schema_editor):
    CoeSettings = apps.get_model('coe', 'CoeSettings')
    CoeSettings.objects.update(
        sms_template_submit=(
            'Your application ({tracking_number}) has been submitted. '
            'Your PIN and tracking ID have been emailed to you.'
        ),
        sms_template_hod_approved=(
            'Your application ({tracking_number}) has been approved by the '
            'Head of Department. Processing is underway.'
        ),
        sms_template_action_required=(
            'Action required for your application ({tracking_number}): {note}. '
            'Please re-upload your documents.'
        ),
        sms_template_ready_for_delivery=(
            'Your {doc_type} is ready ({tracking_number}). Please collect it '
            'from the BAUST CoE Desk. OTP will follow in the next SMS.'
        ),
        sms_template_delivery_otp=(
            'BAUST CoE Delivery OTP: {otp}. Provide this code to the clerk. '
            'Do not share with anyone.'
        ),
        sms_template_reupload_complete=(
            'Your re-uploaded documents for application ({tracking_number}) '
            'have been received. Processing has resumed.'
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('coe', '0011_alter_coesettings_sla_danger_hours'),
    ]

    operations = [
        migrations.RunPython(
            update_sms_templates_to_english,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
