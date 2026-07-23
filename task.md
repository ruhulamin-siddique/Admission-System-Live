# CoE Bug Fix Task List

## Critical
- [x] BUG-1: `forms.py` — Fix `880` prefix strip (mobile[2:] → mobile[3:])
- [x] BUG-2: `step2.html` — Fix JS `880` prefix strip (substring(2) → substring(3))
- [x] BUG-3: `verify_public.html` — Remove sensitive PII (mobile, CGPA) from public verify page
- [x] BUG-4: `views.py` — Add PIN check to `download_receipt_pdf` (no login required currently)
- [x] BUG-5: `views.py` — Add officer notification + student SMS to `student_reupload_portal`

## Medium
- [x] BUG-6: `views.py` — Validate required attachment keys in Step 3 POST
- [x] BUG-7: `views.py` — Explicit `save(update_fields=...)` before `transition_status` in `hod_review`
- [x] BUG-8: `views.py` — Remove `updated_at` from `update_fields` in `assign_officer`
- [x] BUG-9: `utils.py` — Wrap `generate_tracking_number` in `transaction.atomic()` + `select_for_update`
- [x] BUG-10: `utils.py` — Add `reupload_complete` SMS template
- [x] BUG-11: `admin.py` — Register `CoeAssignmentRule` in admin
- [x] BUG-12: `views.py` — Fix step back navigation (back=1 always renders step1 currently)

## Minor
- [x] MINOR-1: `step2.html` — Replace `alert()` with inline error div
- [x] MINOR-2: `models.py` — Fix `student_id` max_length (30 → 16) + migration
- [x] MINOR-3: `views.py` — Add `date_from`/`date_to` filters to `export_excel`
- [x] MINOR-4: `views.py` — Fix `timezone.datetime.strptime` → `datetime.strptime` crash
- [x] MINOR-8: `utils.py` — Use storage-backend-safe `att.file.storage.delete()` in `purge_attachments`

## Post-fix
- [x] Run `python manage.py makemigrations coe` (for MINOR-2 model change)
- [x] Run `python manage.py migrate`
- [x] Run `python manage.py check`
