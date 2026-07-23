# CoE Module — Controller of Examinations (Academic Document Processing)
## Complete Implementation Plan (Reviewed with Full Specification)

---

## Overview

A brand-new Django app `coe` will be added alongside the existing `exam_billing` module, which remains **100% untouched**. The CoE module handles the complete lifecycle of student academic document applications — from a **public-facing 4-step submission wizard**, through departmental review, CoE desk Kanban assignment, processing officer split-screen workstation, and OTP-secured delivery at a counter.

The sidebar will be restructured to group both `exam_billing` and the new `coe` under a shared **"OFFICE OF THE CONTROLLER OF EXAMINATIONS"** header.

---

## All 8 Application Types (Complete)

| # | Type | Key Dynamic Fields | Required Attachments |
|---|------|--------------------|---------------------|
| 1 | **Main/Original Certificate** | Session, Dept, Admission Batch, Passing Semester, CGPA, Result Publication Date | Final Clearance, Offer Letter (Printed Copy), Payment Slip |
| 2 | **Provisional / Main Academic Transcript** | Father's & Mother's Name, Session, Dept, DOB, Passing Semester, CGPA, Result Date | Final Clearance, SSC/HSC Certificate OR NID Photocopy, Payment Slip |
| 3 | **Incomplete Academic Transcript** | Father's & Mother's Name, Session, Dept, DOB, Passing Semester, CGPA, Result Date | Final Clearance, SSC/HSC Certificate OR NID Photocopy, Payment Slip |
| 4 | **Student's Name Correction** | Corrected Name, Father's & Mother's Name, Dept, Admission Batch, CGPA, Result Date | Final Clearance, Corrected SSC/HSC Cert/Online Copy, BAUST Originals (MCE, MoI, MC, TS) |
| 5 | **Father/Mother Name Correction** | Corrected Parent Name, Student Name, Dept, Admission Batch, CGPA, Result Date | Final Clearance, Corrected SSC/HSC Cert/Online Copy, BAUST Originals (MCE, MoI, MC, TS) |
| 6 | **Recommendation Letter** | Session, Dept, Admission Batch, Passing Semester, CGPA, Result Date, **Purpose/Destination** | Final Clearance, Payment Slip |
| 7 | **Grade Sheet** | Level/Term, Session, Dept, Admission Batch, Passing Semester, CGPA, Result Date | Final Clearance, Payment Slip |
| 8 | **Duplicate Documents (as per GD)** | **Missing Document Type**, Session, Dept, Level/Term, Passing Semester, CGPA, Result Date | Missing Document Copy, **General Diary (GD) Copy**, Payment Slip |

---

## Full Lifecycle State Engine

### Main Flow
```
[SUBMITTED]
    ↓
[UNDER_HOD_REVIEW]
    ↓
[PENDING_COE_ASSIGNMENT]  ─────────────────────────────────────► [REJECTED]
    ↓                                                                  ▲
[IN_PROCESSING] ──────────────────────────────────────────────────────┤
    ↓                       ↕ (if bad attachments)                    │
[ACTION_REQUIRED_BY_STUDENT] ◄──── Officer sends SMS query            │
    ↓ (student re-uploads)                                            │
[IN_PROCESSING] (resumed)                                             │
    ↓                                                          [CANCELLED] ◄── student
[READY_FOR_DELIVERY] — SMS auto-dispatched to student
    ↓
[DELIVERED] — OTP verified
```

### Status Choices (9 States)
| Status Key | Label | Who triggers |
|---|---|---|
| `submitted` | Submitted | Student (system auto) |
| `under_hod_review` | Under HoD Review | System (on submit) |
| `pending_coe_assignment` | Pending CoE Assignment | HoD (approve action) |
| `in_processing` | In Processing | CoE (assign to officer) |
| `action_required` | Action Required by Student | Processing Officer |
| `ready_for_delivery` | Ready for Delivery | Processing Officer |
| `delivered` | Delivered | Delivery Clerk (OTP verified) |
| `rejected` | Rejected | HoD or Processing Officer |
| `cancelled` | Cancelled | Student or Admin |

---

## Proposed Changes

---

### Component 1: New Django App Scaffold

#### [NEW] `coe/` — complete app directory
```
coe/
├── __init__.py
├── apps.py              # CoeConfig
├── admin.py             # ModelAdmin registrations
├── models.py            # All data models
├── forms.py             # Application + review forms
├── views.py             # All view functions
├── urls.py              # All URL patterns
├── utils.py             # SMS dispatching, OTP gen, tracking ID gen, cleanup
├── migrations/
│   └── 0001_initial.py
└── templates/coe/       # All HTML templates
```

---

### Component 2: Data Models (`coe/models.py`)

**Model 1: `DocumentApplication`** — Core application record
```python
Fields:
  application_number  CharField (auto-generated: APP-2026-XXXX)
  tracking_pin        CharField (4-digit PIN for public status lookup)
  application_type    CharField(choices: 8 types above)
  student_name        CharField
  student_id          CharField (BAUST student ID)
  mobile_number       CharField (for SMS alerts)
  email               EmailField (optional)
  session             CharField
  department          ForeignKey(Program)
  admission_batch     CharField
  father_name         CharField(blank=True)
  mother_name         CharField(blank=True)
  dob                 DateField(null=True)
  passing_semester    CharField
  cgpa                DecimalField(max_digits=4, decimal_places=2)
  result_date         DateField(null=True)
  corrected_name      CharField(blank=True)   # Type 4
  corrected_parent_name CharField(blank=True) # Type 5
  purpose_destination CharField(blank=True)   # Type 6
  level_term          CharField(blank=True)   # Type 7, 8
  missing_doc_type    CharField(blank=True)   # Type 8
  status              CharField(choices: 9 statuses above)
  submitted_by        ForeignKey(User, null=True)  # null = public
  assigned_to         ForeignKey(User, null=True)  # Processing Officer
  dept_head_note      TextField(blank=True)
  processing_note     TextField(blank=True)
  rejection_reason    TextField(blank=True)
  delivery_otp        CharField(blank=True)   # 6-digit OTP
  delivery_otp_verified  BooleanField(default=False)
  delivered_at        DateTimeField(null=True)
  delivered_by        ForeignKey(User, null=True)
  is_deleted          BooleanField(default=False)  # soft-delete
  submitted_at        DateTimeField(auto_now_add=True)
  updated_at          DateTimeField(auto_now=True)
```

**Model 2: `ApplicationAttachment`** — File uploads (< 2MB each)
```python
Fields:
  application         ForeignKey(DocumentApplication)
  attachment_type     CharField(choices: 12 types)
                      # final_clearance, payment_slip, ssc_cert, hsc_cert,
                      # nid_photocopy, offer_letter, baust_mce, baust_moi,
                      # baust_mc, baust_ts, gd_copy, missing_doc_copy, other
  file                FileField(upload_to='coe/attachments/')
  sha256_hash         CharField(max_length=64)  # For dedup / integrity
  original_filename   CharField
  file_size_kb        IntegerField
  is_purged           BooleanField(default=False)  # After cleanup window
  uploaded_at         DateTimeField(auto_now_add=True)
```

**Model 3: `ApplicationStatusLog`** — Complete audit trail
```python
Fields:
  application         ForeignKey(DocumentApplication)
  old_status          CharField
  new_status          CharField
  changed_by          ForeignKey(User, null=True)  # null = system/auto
  note                TextField
  sms_sent            BooleanField(default=False)
  changed_at          DateTimeField(auto_now_add=True)
```

**Model 4: `ProcessingVerification`** — Verification data from Processing Desk
```python
Fields:
  application         OneToOneField(DocumentApplication)
  admission_api_fetched  BooleanField(default=False)
  admission_api_data     JSONField(null=True)     # Cached from student portal API
  board_api_fetched      BooleanField(default=False)
  board_api_data         JSONField(null=True)     # Cached from SSC/HSC board API
  board_roll             CharField(blank=True)
  board_registration     CharField(blank=True)
  board_name             CharField(blank=True)
  board_year             CharField(blank=True)
  verification_notes     TextField(blank=True)
  verified_by            ForeignKey(User, null=True)
  verified_at            DateTimeField(null=True)
```

**Model 5: `CoeSettings`** — Module-level configuration (singleton)
```python
Fields:
  tracking_id_prefix     CharField(default='APP')  # e.g. APP-2026-XXXX
  sms_notify_submit      BooleanField(default=True)
  sms_notify_approved    BooleanField(default=True)
  sms_notify_ready       BooleanField(default=True)
  sms_delivery_otp       BooleanField(default=True)
  attachment_max_mb      IntegerField(default=2)
  rejected_purge_days    IntegerField(default=15)
  delivered_purge_days   IntegerField(default=90)
  updated_at             DateTimeField(auto_now=True)
```

---

### Component 3: Access Registry (`core/access_registry.py`)

#### [MODIFY] `core/access_registry.py`
Add new `coe` module with 9 granular permission tasks:

```python
"coe": {
    "display": "Controller of Examinations (CoE)",
    "icon": "fas fa-graduation-cap",
    "tasks": {
        "submit_application":    ("Submit Application", "Submit new student document applications via public portal."),
        "track_application":     ("Track Application", "Look up own application status using Tracking ID + PIN."),
        "dept_head_review":      ("Dept. Head Review & Approval", "Review, approve, hold, or reject applications as Dept. Head. Supports bulk actions."),
        "coe_desk_assign":       ("CoE Desk — Assignment & Kanban", "Review pending assignments, view Kanban board, assign to processing officers."),
        "processing_officer":    ("Processing Officer Workstation", "Verify records via board/admission API, request re-uploads, mark ready for delivery."),
        "delivery_desk":         ("Delivery Desk — OTP Handover", "Search applications by tracking ID, verify OTP, log physical delivery."),
        "view_all_applications": ("View All Applications", "View and search all applications across departments and statuses."),
        "export_data":           ("Export & Print", "Export application data to Excel and generate print-formatted summaries."),
        "manage_settings":       ("Manage CoE Settings", "Configure tracking ID prefix, SMS rules, and retention policies."),
    }
}
```

---

### Component 4: URLs (`coe/urls.py`)

Full URL structure under prefix `/coe/`:

| URL | View | Name | Access Required |
|-----|------|------|----------------|
| `/coe/` | `dashboard` | `coe_dashboard` | `view_all_applications` |
| `/coe/submit/` | `submit_application` | `coe_submit` | **Public (no login)** |
| `/coe/track/` | `track_application` | `coe_track` | **Public (no login)** |
| `/coe/applications/` | `application_list` | `coe_application_list` | `view_all_applications` |
| `/coe/applications/<pk>/` | `application_detail` | `coe_application_detail` | Various |
| `/coe/hod/` | `hod_dashboard` | `coe_hod_dashboard` | `dept_head_review` |
| `/coe/hod/<pk>/review/` | `hod_review` | `coe_hod_review` | `dept_head_review` |
| `/coe/hod/bulk-action/` | `hod_bulk_action` | `coe_hod_bulk` | `dept_head_review` |
| `/coe/kanban/` | `kanban_board` | `coe_kanban` | `coe_desk_assign` |
| `/coe/kanban/<pk>/assign/` | `assign_officer` | `coe_assign_officer` | `coe_desk_assign` |
| `/coe/process/<pk>/` | `processing_workstation` | `coe_process` | `processing_officer` |
| `/coe/process/<pk>/fetch-admission/` | `fetch_admission_api` | `coe_fetch_admission` | `processing_officer` |
| `/coe/process/<pk>/fetch-board/` | `fetch_board_api` | `coe_fetch_board` | `processing_officer` |
| `/coe/process/<pk>/request-reupload/` | `request_reupload` | `coe_request_reupload` | `processing_officer` |
| `/coe/process/<pk>/ready/` | `mark_ready` | `coe_mark_ready` | `processing_officer` |
| `/coe/delivery/` | `delivery_dashboard` | `coe_delivery_dashboard` | `delivery_desk` |
| `/coe/delivery/<pk>/verify-otp/` | `verify_otp` | `coe_verify_otp` | `delivery_desk` |
| `/coe/delivery/<pk>/deliver/` | `mark_delivered` | `coe_mark_delivered` | `delivery_desk` |
| `/coe/export/` | `export_excel` | `coe_export` | `export_data` |
| `/coe/settings/` | `coe_settings` | `coe_settings` | `manage_settings` |
| `/coe/ajax/<pk>/attachments/` | `ajax_attachments` | `coe_ajax_attachments` | Various |

---

### Component 5: Views (`coe/views.py`)

**Public Views (no login required):**

1. **`submit_application`** — 4-step HTMX wizard:
   - Step 1: Application Type selector (radio cards, each shows required fields + attachments preview)
   - Step 2: Student & Academic info fields (dynamic fields per type via HTMX swap)
   - Step 3: Attachment upload section (file size < 2MB validated, inline preview)
   - Step 4: Payment confirmation + Review & Submit
   - On submit: generates `APP-YYYY-XXXX` tracking ID + 4-digit PIN, sends SMS, creates audit log entry.

2. **`track_application`** — Public tracking portal:
   - Input: Tracking ID + Mobile Number or Student ID
   - Output: Horizontal step-progress bar showing current stage. Displays officer notes if any. If `ACTION_REQUIRED`: shows SMS query text + re-upload link.

**Staff Views:**

3. **`dashboard`** — Master KPI panel:
   - Cards: Today's Submissions, Pending at HoD, Pending Assignment (CoE), In Processing, Ready for Delivery, Delivered Today.
   - Bottleneck warnings: applications stalled > 48 hours.
   - Recent activity table + mini-chart of submissions per type.

4. **`hod_dashboard`** — Department-scoped applications table:
   - Filtered automatically to logged-in HoD's department.
   - Quick-action buttons: "Approve & Forward" / "Hold" / "Reject" per row.
   - Multi-select checkboxes for bulk-approve.

5. **`hod_review`** — HTMX modal:
   - Shows student data summary + attachments list.
   - Action: Approve with note / Hold with note / Reject with mandatory reason.

6. **`kanban_board`** — CoE Desk Kanban:
   - Columns: Pending Assignment | In Processing | Ready for Delivery.
   - Each card: Student name, application type, department, submission date, assigned officer.
   - Bottleneck warning badge if > 48 hrs stalled.
   - "Assign" button opens officer picker modal (lists users with `processing_officer` permission).
   - Performance analytics row: avg processing time per officer.

7. **`processing_workstation`** — Split-screen layout:
   - **Left Panel:** Student submitted data (read-only), inline attachment previewer (PDF/image).
   - **Right Panel:** Verification Tools drawer:
     - "One-Click Fetch Admission Record" button → `fetch_admission_api` (hits existing student DB)
     - Board Verification form: Roll, Registration, Board, Year → `fetch_board_api` (hits existing BTEB external API module)
     - Shows cached API results from `ProcessingVerification`.
   - Action bar: "Request Student Re-Upload" (sends SMS, sets `ACTION_REQUIRED`) | "Mark as Ready for Delivery" (sets OTP generation + SMS).

8. **`delivery_dashboard`** — Clerk delivery queue:
   - Search bar (tracking ID or student name, supports QR scan input).
   - Table of `READY_FOR_DELIVERY` applications.
   - Each row: Student name, type, assigned tracking ID, OTP status.
   - Identity verification note prompt.

9. **`verify_otp`** — OTP entry modal:
   - Shows student photo (from student DB if available), document type, payment status.
   - 6-digit OTP input (dispatched via SMS when marked ready).
   - On correct OTP → enables "Mark Delivered" final button.

---

### Component 6: Utils (`coe/utils.py`)

Key utility functions:
- `generate_tracking_number(year)` → `APP-2026-XXXX` (sequential per year)
- `generate_pin()` → 4-digit random PIN
- `generate_delivery_otp()` → 6-digit OTP
- `send_coe_sms(mobile, template, context)` → uses existing SMS gateway from `SystemSettings`
- `purge_attachments(application)` → deletes files, sets `is_purged=True` on records
- `cleanup_rejected_applications()` → cron task: purge files + soft-delete after N days
- `cleanup_delivered_applications()` → cron task: purge files after 90 days post-delivery

**SMS Templates:**
| Event | Template |
|---|---|
| Submission | `"আপনার আবেদন গৃহীত হয়েছে। ট্র্যাকিং আইডি: {id}, পিন: {pin}"` |
| HoD Approved | `"আপনার আবেদন বিভাগীয় প্রধান অনুমোদন করেছেন। প্রক্রিয়াকরণ চলমান।"` |
| Action Required | `"আপনার আবেদনে সমস্যা: {note}। পুনরায় ডকুমেন্ট আপলোড করুন: {link}"` |
| Ready for Delivery | `"আপনার {doc_type} প্রস্তুত। CoE ডেস্ক থেকে সংগ্রহ করুন।"` |
| OTP for Delivery | `"CoE ডেলিভারি OTP: {otp}। এটি ক্লার্ককে দিন।"` |

---

### Component 7: Templates (`templates/coe/`)

| Template | Description |
|---|---|
| `submit_wizard.html` | Public 4-step HTMX-powered submission wizard |
| `submit_step1.html` | Partial: Application type selector cards |
| `submit_step2.html` | Partial: Dynamic academic info fields |
| `submit_step3.html` | Partial: File upload section with previewer |
| `submit_step4.html` | Partial: Review & payment confirmation |
| `submit_success.html` | Tracking ID + PIN display page |
| `track_application.html` | Public tracking portal with step-progress bar |
| `dashboard.html` | Staff dashboard with KPI cards + bottleneck alerts |
| `application_list.html` | Full filterable applications table |
| `application_detail.html` | Full detail view with timeline + attachments + audit log |
| `hod_dashboard.html` | HoD batch-review table |
| `hod_review_modal.html` | HTMX partial: Approve/Hold/Reject modal |
| `kanban_board.html` | CoE Kanban assignment panel |
| `assign_modal.html` | HTMX partial: Officer picker for assignment |
| `processing_workstation.html` | Split-screen processing UI |
| `delivery_dashboard.html` | Delivery queue with search |
| `delivery_otp_modal.html` | OTP entry + identity verification modal |
| `settings.html` | CoE module configuration |
| `print_summary.html` | Print-friendly application summary |
| `export_excel.html` | (generates .xlsx via openpyxl) |

---

### Component 8: Sidebar Navigation (`templates/base.html`)

#### [MODIFY] `templates/base.html`

Rename section header and add CoE sub-menu:

```
▸ OFFICE OF THE CONTROLLER OF EXAMINATIONS (CoE)
   ├── [Exam Billing] ─── UNCHANGED ───────────────
   │     ├── Dashboard
   │     ├── Exams
   │     ├── Faculty Directory
   │     ├── Fundamentals
   │     ├── Individual Bills
   │     └── Bill Settings
   └── [CoE — Document Processing] ── NEW ─────────
         ├── CoE Dashboard        (view_all_applications)
         ├── Application List     (view_all_applications)
         ├── ─────────────────────────────────────────
         ├── HoD Dashboard        (dept_head_review)
         ├── Kanban / Assignment  (coe_desk_assign)
         ├── Processing Workstation (processing_officer)
         ├── Delivery Desk        (delivery_desk)
         └── Settings             (manage_settings)
```

**Public links** (visible to unauthenticated users — in top navbar or footer):
- Submit Application → `/coe/submit/`
- Track My Application → `/coe/track/`

---

### Component 9: Data Storage & Automated Cleanup

**Storage:**
- Attachments stored in `media/coe/attachments/` (local) with SHA-256 hash filename.
- `is_purged` flag on `ApplicationAttachment` marks cleaned records.
- File size validated at < `CoeSettings.attachment_max_mb` MB on upload.

**Automated Cleanup (`/coe/utils.py` — run via Django management command or cron):**
- `python manage.py coe_cleanup` → two passes:
  - **Rejected/Cancelled:** after `rejected_purge_days` (default 15), purge files, soft-delete record (set `is_deleted=True`).
  - **Delivered:** after `delivered_purge_days` (default 90), purge files, preserve metadata.

**Model approach:** `is_deleted=True` applications excluded from regular querysets via a custom `ActiveManager`.

---

### Component 10: App Registration

#### [MODIFY] `admission_system/settings.py`
```python
INSTALLED_APPS = [
    ...
    'exam_billing',
    'coe',           # NEW
    ...
]
```

#### [MODIFY] `admission_system/urls.py`
```python
path('coe/', include('coe.urls')),
```

---

### Component 11: Bangla Translations

#### [MODIFY] `locale/bn/LC_MESSAGES/django.po`

Key new strings:
| English | Bangla |
|---|---|
| Controller of Examinations (CoE) | পরীক্ষা নিয়ন্ত্রণ অধিদপ্তর (CoE) |
| Submit Application | আবেদন জমা দিন |
| Track My Application | আবেদন অনুসন্ধান করুন |
| Application Tracking ID | আবেদন ট্র্যাকিং আইডি |
| Under HoD Review | বিভাগীয় প্রধানের পর্যালোচনায় |
| Pending CoE Assignment | CoE নিয়োগ প্রক্রিয়াধীন |
| In Processing | প্রক্রিয়াকরণ চলমান |
| Action Required by Student | শিক্ষার্থীর পদক্ষেপ প্রয়োজন |
| Ready for Delivery | বিতরণের জন্য প্রস্তুত |
| Delivered | বিতরণ সম্পন্ন |
| Mark as Delivered | বিতরণ সম্পন্ন হিসেবে চিহ্নিত করুন |
| Delivery OTP | বিতরণ ওটিপি |
| Main/Original Certificate | মূল সনদপত্র |
| Provisional / Main Academic Transcript | সাময়িক / মূল একাডেমিক ট্রান্সক্রিপ্ট |
| Grade Sheet | গ্রেড শিট |
| Recommendation Letter | প্রশংসাপত্র |
| Duplicate Documents | নকল দলিলপত্র |
| Approve & Forward | অনুমোদন ও অগ্রেষণ |

---

## Security Design

| Concern | Solution |
|---|---|
| Forged payment slips | Payment slip image upload + manual officer verification at processing desk. (Future: bKash/SSLCommerz integration) |
| Invalid/unreadable attachments | `ACTION_REQUIRED` state: officer sends structured SMS query with re-upload link; timer paused |
| Fraud at delivery desk | OTP dispatched to student's mobile when marked ready. Clerk must enter correct OTP to complete delivery. Physical NID/Student ID check logged as note. |
| Application impersonation | Tracking lookup requires Tracking ID + Mobile Number or Student ID (two-factor identification) |
| Stale data buildup | Automated cleanup cron purges files after retention windows |

---

## Verification Plan

### Automated Tests
```bash
python manage.py check
python manage.py test coe
python manage.py makemigrations coe --check
```

### Manual Smoke Tests
1. ✅ Submit application of each of the 8 types via public wizard → receive tracking ID + PIN via SMS
2. ✅ Track application using tracking ID + mobile number → see correct stage
3. ✅ HoD approves application → status advances to `pending_coe_assignment`
4. ✅ HoD bulk-approves 3 applications → all advance
5. ✅ CoE assigns to processing officer → officer sees it in their workstation queue
6. ✅ Processing officer fetches admission API → cached data saved
7. ✅ Processing officer runs board verification → data saved
8. ✅ Processing officer clicks "Request Re-Upload" → status = `action_required`, SMS sent
9. ✅ Processing officer marks "Ready for Delivery" → OTP generated, SMS dispatched
10. ✅ Delivery clerk finds application by tracking ID → enters correct OTP → marks delivered
11. ✅ Verify full audit timeline in `application_detail` view
12. ✅ Verify `coe_cleanup` management command purges rejected files after 15 days
13. ✅ Verify Access Registry shows 9 CoE tasks in Role Management UI
14. ✅ Verify sidebar shows CoE section correctly for each role
15. ✅ Bangla UI renders correctly when language = bn

---

## Implementation Order

| Phase | Steps |
|---|---|
| **Phase 1 — Foundation** | App scaffold, models.py, migrations, admin.py, apps.py, settings.py, urls.py |
| **Phase 2 — Access & Registry** | access_registry.py updated, sidebar in base.html |
| **Phase 3 — Public Submission** | submit_wizard + track_application views + templates |
| **Phase 4 — Staff Backend** | dashboard, application_list, application_detail views |
| **Phase 5 — HoD Interface** | hod_dashboard + review modal + bulk-action |
| **Phase 6 — CoE Kanban** | kanban_board + assign modal + bottleneck logic |
| **Phase 7 — Processing Workstation** | split-screen + API fetch + ACTION_REQUIRED flow |
| **Phase 8 — Delivery Desk** | OTP generation + delivery_dashboard + verify + mark_delivered |
| **Phase 9 — Utilities** | utils.py (SMS, OTP, cleanup), management command |
| **Phase 10 — Polish** | Bangla translations, Excel export, print view, system check |
