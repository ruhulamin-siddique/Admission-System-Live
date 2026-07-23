# CoE Module — Comprehensive Bug & Gap Report

## Summary

After a full read-through of all CoE module files (`models.py`, `views.py`, `forms.py`, `utils.py`, `admin.py`, `urls.py`, all templates/partials, and the management command), the following bugs and gaps were identified, ordered from **Critical** → **Medium** → **Minor**.

---

## 🔴 CRITICAL Bugs

### BUG-1 — `clean_mobile_number()`: Wrong strip logic for `+880` prefix
**File:** [`coe/forms.py` L110–112](file:///d:/My%20Drive/1-Python/1-Admission/coe/forms.py#L110-L112)

```python
# WRONG: both branches strip 2 chars (same result), `+880` (13 chars) is never handled
if mobile.startswith('880') and len(mobile) == 13:
    mobile = mobile[2:]   # strips '88', leaving '011...' ✗ — should strip 3 chars
elif mobile.startswith('88') and len(mobile) == 13:
    mobile = mobile[2:]
```

**Problem:** If a user types `+8801711223344` → stripped of `+` by `filter(str.isdigit)` → `8801711223344` (13 digits, starts with `880`). The fix strips only 2 chars → produces `01711223344` (11 digits) ✓ — this is actually correct *by accident*. BUT if user types `0088-01711-223344` → 13 digits starting with `00` → neither branch fires → falls through to invalid check. More critically: **`880` prefix stripping strips 2 characters** (`mobile[2:]`) which produces `0…` prefix correctly only because `880` happens to work with index 2. However the comment intent says `880` → strip 3 chars, so this should be `mobile[3:]` for the `880` branch.

**Real impact:** `8801711223344` → `mobile[2:]` → `01711223344` ✓ (correct by luck). But code is logically wrong — the `880` branch and `88` branch do identical things. The `+880` prefix case will produce wrong results for edge cases.

**Fix:**
```python
if mobile.startswith('880') and len(mobile) == 13:
    mobile = mobile[3:]   # ← strip 3 chars, not 2
elif mobile.startswith('88') and len(mobile) == 12:
    mobile = mobile[2:]
```

---

### BUG-2 — Same prefix strip bug in `step2.html` JS (line 303–307)
**File:** [`coe/templates/coe/partials/step2.html` L303–307](file:///d:/My%20Drive/1-Python/1-Admission/coe/templates/coe/partials/step2.html#L303-L307)

```js
// BOTH branches use substring(2) — same wrong logic as forms.py
if (digits.startsWith('880') && digits.length === 13) {
    digits = digits.substring(2);   // ← should be substring(3)
} else if (digits.startsWith('88') && digits.length === 13) {
    digits = digits.substring(2);
}
```

Same logic error as BUG-1 — `880` prefix should strip 3 characters (`substring(3)`), not 2.

---

### BUG-3 — `verify_document_public` not login-protected but reveals sensitive data
**File:** [`coe/views.py` L1276–1291](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1276-L1291)

The public QR verify portal shows the full application record (`app` object) to anyone — no authentication needed. This exposes student name, mobile number, student ID, CGPA, session, department. While QR verification is intentionally public for document authenticity checks, the template should only display verification status + application type, NOT personal data.

**Risk:** Any person with an application number (trackable from submitted docs) can view personal student details without any PIN/OTP check.

---

### BUG-4 — `download_receipt_pdf` has no login/access requirement
**File:** [`coe/views.py` L1358–1376](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1358-L1376)

```python
def download_receipt_pdf(request, pk):   # ← no @login_required or @require_access
```

Any unauthenticated user can download the PDF receipt of any application if they guess the `pk` (sequential integer). The receipt contains full student personal information and QR code.

**Fix:** Add `@login_required` or use session-based token (e.g., check `tracking_pin` in GET params for public access).

---

### BUG-5 — `student_reupload_portal` uses `all_objects` for auth but re-uploads go to `in_processing` with no officer notification
**File:** [`coe/views.py` L1344–1347](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1344-L1347)

```python
transition_status(
    app, ApplicationStatus.IN_PROCESSING,
    note=_('Student re-uploaded corrected document(s) via public portal.'),
    # ← changed_by=None, no send_sms_key — officer never notified
)
```

When a student re-uploads documents via the public portal, the application silently transitions back to `IN_PROCESSING` with NO notification to the assigned officer. The officer has no way of knowing new documents arrived.

**Fix:** Add `send_sms_key='action_required'` or a new `'reupload_complete'` SMS key, and ensure `changed_by=None` is intentional.

---

## 🟠 MEDIUM Bugs

### BUG-6 — `submit_step` Step 3 allows empty files to advance to Step 4
**File:** [`coe/views.py` L167–168](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L167-L168)

```python
if not request.FILES and not existing_pending:
    errors.append(...)
```

If `existing_pending` is already populated from a prior upload attempt AND the user submits Step 3 again with no new files, the check passes with existing pending files even if required attachment types are missing. There is no validation that each **required** attachment key is covered.

**Gap:** Required attachment keys from `_get_required_attachments()` are never cross-checked against `existing_pending.keys()`. A student can upload one file for attachment A, go back, and submit without ever uploading attachment B.

---

### BUG-7 — `hod_review`: `app.save()` not called before `transition_status` on `approve` action
**File:** [`coe/views.py` L638–646](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L638-L646)

```python
if action == 'approve':
    app.dept_head_note = note      # ← mutation
    transition_status(...)         # ← calls app.save() internally
```

`transition_status` calls `application.save()` which saves ALL fields — including the just-mutated `dept_head_note`. This is correct by accident since `transition_status` does a full `save()`. However if `transition_status` is ever refactored to use `save(update_fields=[...])`, the `dept_head_note` will silently fail to persist. The `reject` branch does `app.rejection_reason = note` then `transition_status()` with the same risk.

**Recommendation:** Explicitly save the note field first:
```python
app.dept_head_note = note
app.save(update_fields=['dept_head_note'])
transition_status(...)
```

---

### BUG-8 — `assign_officer`: Re-assignment `save()` includes `updated_at` which doesn't exist as an editable field
**File:** [`coe/views.py` L815](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L815)

```python
app.save(update_fields=['assigned_to', 'updated_at'])
```

`updated_at` is defined as `auto_now=True` in the model, which means Django manages it automatically. Passing it in `update_fields` is ignored by Django but is misleading — and in some Django versions may cause unexpected behavior. Remove `'updated_at'` from `update_fields`.

---

### BUG-9 — `generate_tracking_number()` race condition under concurrent submissions
**File:** [`coe/utils.py` L52–79](file:///d:/My%20Drive/1-Python/1-Admission/coe/utils.py#L52-L79)

```python
max_seq = 0
for app_num in records:
    seq = max_seq + 1
return f"{prefix}-{year}-{seq:04d}"  # ← NOT atomic
```

If two users submit simultaneously, both reads get the same `max_seq`, both generate the same tracking number, and one `objects.create()` will fail with `IntegrityError` (the field is `unique=True`).

**Fix:** Wrap in `select_for_update()` or use a database sequence/`F()` increment approach. At minimum, catch `IntegrityError` and retry.

---

### BUG-10 — `transition_status`: Status log always records `new_status` even when auto-assignment overrides it
**File:** [`coe/utils.py` L255–312](file:///d:/My%20Drive/1-Python/1-Admission/coe/utils.py#L255-L312)

```python
# Auto-assignment changes new_status from 'pending_coe_assignment' → 'in_processing'
# But the caller passed 'pending_coe_assignment' — the log correctly records new_status
# However the SMS key is NOT updated — caller passes send_sms_key='hod_approved'
# which sends an SMS about "forwarded to CoE" even though it's actually in_processing
```

When auto-assignment fires, the status skips `PENDING_COE_ASSIGNMENT` and goes directly to `IN_PROCESSING`, but the SMS sent is the `hod_approved` SMS which says "processing is ongoing" — which is technically true, but the student never gets the assignment notification.

---

### BUG-11 — `CoeAssignmentRule` not in `admin.py` registration
**File:** [`coe/admin.py`](file:///d:/My%20Drive/1-Python/1-Admission/coe/admin.py)

`CoeAssignmentRule` model is defined in `models.py` and used in `views.py` (settings view), but never registered in `admin.py`. Admin superusers cannot manage it through Django admin panel — only through the settings UI.

---

### BUG-12 — Step 3 "Back" button goes to Step 2 via HTMX GET but step 3 `back=1` is not handled
**File:** [`coe/views.py` L353–384](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L353-L384)

In `submit_step` GET handler:
```python
if step == 1 or request.GET.get('back') == '1':
    return render(...step1...)
```

The `back=1` check only fires for Step 1. When the Step 4 "Back to Uploads" button hits `GET /coe/submit/step/3/?back=1`, `submit_step(request, step=3)` is called. But the GET handler renders based on `wizard.step` (which is 4 at that point), not `step` param. The `back=1` is never checked for steps 3 or 4.

**Affected:** Step 4 "Back to Uploads" button may not correctly re-render Step 3 if wizard state is at step 4.

---

## 🟡 MINOR Issues / Gaps

### MINOR-1 — `step2.html` JS submit alert uses `alert()` (blocking browser dialog)
**File:** [`coe/templates/coe/partials/step2.html` L434](file:///d:/My%20Drive/1-Python/1-Admission/coe/templates/coe/partials/step2.html#L434)

```js
alert('Please make sure Student ID (9 or 16 digits starting with 080) and Mobile Number are valid.');
```

Native `alert()` is jarring UX on a premium-styled page. Should be replaced with an inline error badge or toast notification.

---

### MINOR-2 — `student_id` max length mismatch: model allows 30, form allows 30, but HTML `maxlength="16"`
**File:** [`coe/models.py` L83](file:///d:/My%20Drive/1-Python/1-Admission/coe/models.py#L83)

```python
student_id = models.CharField(max_length=30, ...)
```

Model allows 30 chars, but validation only allows 9 or 16. No server-side truncation to 16 — the `clean_student_id()` strips non-digits and checks length, but the HTML input has `maxlength="16"`. Inconsistency: if someone submits via API/Postman, a 20-digit ID passes the model save but fails form validation (only if using the form). Model max_length should match domain rules (`max_length=16`).

---

### MINOR-3 — `export_excel` does not apply `date_from`/`date_to` filter even though `ApplicationSearchForm` has those fields
**File:** [`coe/views.py` L1091–1107](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1091-L1107)

The export view uses `ApplicationSearchForm` but only applies `q`, `status`, `app_type`, and `dept` filters. The `date_from` and `date_to` filter fields are ignored in the export queryset.

---

### MINOR-4 — `delivery_handover_register` uses `timezone.datetime.strptime` (wrong)
**File:** [`coe/views.py` L1409](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1409)

```python
target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
```

`django.utils.timezone` does not have `.datetime` attribute — `timezone` is a module, not the `datetime` class. This will raise `AttributeError` at runtime when a `date` query param is provided.

**Fix:**
```python
from datetime import datetime
target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
```

---

### MINOR-5 — `transition_status` always saves full application (`app.save()`) which may trigger unintended `auto_now` updates on unrelated fields
**File:** [`coe/utils.py` L267](file:///d:/My%20Drive/1-Python/1-Admission/coe/utils.py#L267)

```python
application.save()  # Full save — updates ALL fields + auto_now updated_at
```

A full `.save()` in `transition_status` means any in-memory mutations on the application object (from the calling view) will silently persist. This is dangerous if the caller mutates fields that shouldn't be saved at that moment.

---

### MINOR-6 — `compute_sha256` in `utils.py` vs direct use in `student_reupload_portal`
**File:** [`coe/views.py` L1331](file:///d:/My%20Drive/1-Python/1-Admission/coe/views.py#L1331)

```python
sha = compute_sha256(f)  # f is a Django InMemoryUploadedFile
```

After `compute_sha256(f)`, the file pointer is at position 0 (function does `seek(0)` at end). BUT then:
```python
ApplicationAttachment.objects.create(..., file=f, ...)
```
Django's `FileField.save()` will read from current position. Since `compute_sha256` correctly seeks back to 0 after hashing, this is safe — but fragile. A future refactor of `compute_sha256` that omits the final `seek(0)` would silently create empty attachments.

---

### MINOR-7 — SMS template `action_required` uses `{tracking_number}` but `send_coe_sms` context in reupload portal doesn't include it
**File:** [`coe/utils.py` L180, L280](file:///d:/My%20Drive/1-Python/1-Admission/coe/utils.py#L280)

```python
ctx.setdefault('tracking_number', application.application_number)
```

This `setdefault` is in `transition_status()` — so it correctly adds `tracking_number` if not present. Safe.

---

### MINOR-8 — `purge_attachments` uses `os.path.isfile` / `os.remove` but media files may be in cloud storage (S3)
**File:** [`coe/utils.py` L328–330](file:///d:/My%20Drive/1-Python/1-Admission/coe/utils.py#L328-L330)

```python
if att.file and os.path.isfile(att.file.path):
    os.remove(att.file.path)
```

If `DEFAULT_FILE_STORAGE` is set to S3/GCS, `att.file.path` will raise `NotImplementedError`. Should use `att.file.storage.delete(att.file.name)` for storage-backend-agnostic deletion.

---

## Summary Table

| ID | Severity | File | Issue |
|----|----------|------|-------|
| BUG-1 | 🔴 Critical | `coe/forms.py` | `880` prefix stripping removes 2 chars instead of 3 |
| BUG-2 | 🔴 Critical | `step2.html` | Same JS strip bug as BUG-1 |
| BUG-3 | 🔴 Critical | `views.py` | Public QR verify exposes full student PII |
| BUG-4 | 🔴 Critical | `views.py` | `download_receipt_pdf` requires no login |
| BUG-5 | 🔴 Critical | `views.py` | Re-upload portal: officer never notified of new docs |
| BUG-6 | 🟠 Medium | `views.py` | Step 3 required attachment keys not validated |
| BUG-7 | 🟠 Medium | `views.py` | `dept_head_note` relies on accidental full-save |
| BUG-8 | 🟠 Medium | `views.py` | `auto_now` field in `update_fields` is incorrect |
| BUG-9 | 🟠 Medium | `utils.py` | Tracking number generation race condition |
| BUG-10 | 🟠 Medium | `utils.py` | Auto-assignment SMS key not updated |
| BUG-11 | 🟠 Medium | `admin.py` | `CoeAssignmentRule` not registered in admin |
| BUG-12 | 🟠 Medium | `views.py` | Step back buttons may not correctly re-render steps |
| MINOR-1 | 🟡 Minor | `step2.html` | `alert()` breaks premium UX |
| MINOR-2 | 🟡 Minor | `models.py` | `student_id` model max_length=30 vs validated max 16 |
| MINOR-3 | 🟡 Minor | `views.py` | Date filters missing in export |
| MINOR-4 | 🟡 Minor | `views.py` | `timezone.datetime.strptime` → AttributeError crash |
| MINOR-5 | 🟡 Minor | `utils.py` | Full `app.save()` in `transition_status` is fragile |
| MINOR-6 | 🟡 Minor | `views.py` | SHA256 file seek fragility |
| MINOR-7 | 🟡 Minor | `utils.py` | SMS context auto-filled by setdefault (safe but note) |
| MINOR-8 | 🟡 Minor | `utils.py` | File purge uses `os.remove` — not cloud-storage-safe |
