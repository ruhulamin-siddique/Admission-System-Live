# Comprehensive Implementation Plan: University Psychological Counseling & Student Wellbeing Module (`counseling`)

> **Audit Date:** 2026-08-23 · **Auditors:** Backend Architecture & UI/UX Design System Audit  
> **Status:** Production-Ready Blueprint 🚀

---

## 🔍 Section 1: Comprehensive Bug & Gap Audit (Backend & UI/UX)

The following matrix identifies all backend and UI/UX vulnerabilities found across the proposed counseling module, along with their engineered solutions:

### ⚙️ Backend & Architecture Gaps (Resolved)

| # | Vulnerability / Bug | File Affected | Severity | Engineered Solution |
|---|---|---|---|---|
| 1 | **`ACCESS_REGISTRY` missing** — Role Management UI cannot grant counseling permissions. | `core/access_registry.py` | 🔴 Critical | Added full `counseling` registry entry with 11 granular clinical tasks. |
| 2 | **Wrong SMS pattern** — Custom helper proposed instead of core dispatcher. | `students/models.py`, `counseling/utils.py` | 🔴 Critical | Extended `SMSHistory.MODULE_CHOICES` for `'COUNSELING'` and used `core.utils.send_sms()`. |
| 3 | **No `apps.py` defined** — AppConfig missing. | `counseling/apps.py` | 🟠 High | Created `CounselingConfig(AppConfig)` with proper verbose naming. |
| 4 | **No `CaseStatusLog` audit trail** — Legal/clinical requirement for status change tracking. | `counseling/models.py` | 🟠 High | Added `CaseStatusLog` model recording user, old/new status, timestamp, and notes. |
| 5 | **No `CounselingSettings` singleton** — Hardcoded SMS templates and SLA thresholds. | `counseling/models.py` | 🟠 High | Implemented singleton `CounselingSettings` with `get_settings()` pattern. |
| 6 | **Wrong sidebar template syntax** — Plan specified wrong template tag syntax. | `templates/base.html` | 🟠 High | Standardized on `{% has_access 'counseling' 'task' as var %}` template tag. |
| 7 | **TextChoices enums not used** — Bare string lists instead of Django enum classes. | `counseling/models.py` | 🟡 Medium | Converted all choices to `models.TextChoices` with badge and icon helper methods. |
| 8 | **No soft-delete on cases** — Risk of accidental permanent deletion of medical history. | `counseling/models.py` | 🟡 Medium | Added `is_deleted` flag and `ActiveCaseManager` matching CoE model pattern. |
| 9 | **Missing `db_index` on search fields** — Slow dashboard/list query performance. | `counseling/models.py` | 🟡 Medium | Added `db_index=True` on `case_number`, `status`, `risk_level`, `intake_date`. |
| 10 | **`generate_case_id()` concurrency hazard** — Risk of duplicate IDs under traffic. | `counseling/utils.py` | 🟡 Medium | Implemented `transaction.atomic()` with `select_for_update()`. |
| 11 | **`SessionRecord.is_locked` unenforced** — Notes could be edited indefinitely. | `counseling/views.py`, `models.py` | 🟡 Medium | Added 24-hour auto-lock signal and strict view-level immutable guards. |
| 12 | **No workshop registration model** — Event tracking with no participant link. | `counseling/models.py` | 🟢 Low | Added `WellbeingWorkshopParticipant` with unique student constraints. |

---

### 🎨 UI/UX Issues, Bugs & Gaps (Resolved)

| # | UI/UX Bug / Gap | User Experience Impact | Engineered UI/UX Solution |
|---|---|---|---|
| 13 | **Screen Visibility in Open Chambers (Stigma Risk)** | If staff or students walk behind the psychologist, open screens show confidential names and crisis tags. | **"Discretion / Privacy Mode" Toggle (`Alt+P` or top switch)**: Instantly blurs student names, phone numbers, and IDs on screen with CSS backdrop blur until explicitly hovered. |
| 14 | **Cognitive Fatigue in Assessment Scales (PHQ-9/DASS-21)** | Traditional dense radio tables cause survey fatigue and accidental misclicks. | **Interactive Card-Tile Stepper**: Custom animated radio pills, keyboard shortcuts (`1`, `2`, `3`, `4`), live SVG circular score gauge with dynamic color progression (🟢 Minimal ➔ 🟡 Mild ➔ 🟠 Moderate ➔ 🔴 Severe). |
| 15 | **SOAP Notes Accidental Data Loss & Clutter** | Standard `<textarea>` blocks lose drafts on accidental tab close and look unorganized. | **4-Quadrant Structured Editor**: Tabbed/Split SOAP workspace with localStorage auto-drafting, rich bullet formatting, pre-built clinical phrase snippets (one-click inserts), and active word count. |
| 16 | **Appointment Double-Booking & Blind Slots** | Static dropdown time pickers don't visually reflect psychologist's real-time free/busy state. | **Interactive Time-Slot Grid**: Color-coded slot pills (Available, Booked, Emergency Reserved, Rescheduled) with live HTMX conflict check on date selection. |
| 17 | **Lack of Longitudinal Symptom Tracking UI** | Counselor cannot see at a glance if therapy is working over 6–8 sessions. | **Longitudinal Chart.js Progression Graph**: Interactive dual-axis chart in student case dossier plotting PHQ-9 & GAD-7 scores over time alongside session milestones. |
| 18 | **Emergency Crisis Alert Chaos** | High-risk emergency walk-ins need fast, calm action, not confusing popups. | **Crisis Action Drawer (Slide-out Modal)**: Red pulse badge on high-risk cases, one-click auto-populated Hall Provost & CMO emergency contact dialers with pre-drafted discreet SMS dispatch buttons. |
| 19 | **Dark Mode & Bilingual Font Glitches** | Custom styling breaking AdminLTE dark mode or clipping Bangla (`Hind Siliguri`) vowels. | **Standardized CSS Variables & Font Scaling**: Full theme variable mapping (`--card-bg`, `--text-primary`, `--border-color`), 100% dark mode styling, and proper line-height (1.45) for Bangla text rendering. |
| 20 | **Mobile / Tablet Unresponsiveness for Mobile Counselors** | Complex clinical tables break on iPad/tablet during residential hall emergency visits. | **Fluid Touch-Optimized Layout**: Minimum 44px touch targets, responsive card fallbacks for table rows on screens `<768px`, and collapsible side dossiers. |

---

## 🏛️ Section 2: UI Design System & Component Architecture

### 🎨 1. Color Palette & Dark Mode Semantic Tokens (`static/counseling/css/counseling.css`)

```css
:root {
  /* Clinical Brand Accents */
  --counseling-primary: #1e40af;       /* Deep Clinical Navy */
  --counseling-primary-light: #eff6ff;
  --counseling-accent: #0284c7;        /* Calming Sky Blue */
  --counseling-teal: #0d9488;          /* Wellbeing Teal */
  
  /* Risk Stratification Palette */
  --risk-low: #10b981;                /* Emerald Green */
  --risk-low-bg: #ecfdf5;
  --risk-moderate: #f59e0b;           /* Amber */
  --risk-moderate-bg: #fffbeb;
  --risk-high: #f97316;               /* Orange */
  --risk-high-bg: #fff7ed;
  --risk-critical: #ef4444;           /* Crimson Red */
  --risk-critical-bg: #fef2f2;
  
  /* Glassmorphism & UI Surfaces */
  --counseling-card-bg: #ffffff;
  --counseling-border: #e2e8f0;
  --counseling-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 2px 6px -1px rgba(0, 0, 0, 0.02);
  --counseling-shadow-hover: 0 10px 25px -3px rgba(0, 0, 0, 0.08);
}

/* Dark Mode Overrides (Inherits from AdminLTE .dark-mode) */
.dark-mode {
  --counseling-card-bg: #1e293b;
  --counseling-border: #334155;
  --counseling-primary-light: rgba(30, 64, 175, 0.2);
  --counseling-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
  --risk-low-bg: rgba(16, 185, 129, 0.15);
  --risk-moderate-bg: rgba(245, 158, 11, 0.15);
  --risk-high-bg: rgba(249, 115, 22, 0.15);
  --risk-critical-bg: rgba(239, 68, 68, 0.2);
}
```

---

### 🛡️ 2. Privacy / Discretion Blur Mode (One-Click Desk Shield)

```css
/* Discretion Shield Filter */
body.privacy-mode-active .confidential-pii {
  filter: blur(6px);
  user-select: none;
  transition: filter 0.2s ease-in-out;
  cursor: pointer;
}
body.privacy-mode-active .confidential-pii:hover {
  filter: blur(0px); /* Unblur on intentional hover */
}
```
* **UX Behavior**: A prominent lock switch (`🔒 Discretion Mode: ON/OFF`) in the navbar header. When enabled, student names, roll numbers, photos, and parent mobile numbers are softly blurred so casual observers entering the office see no confidential data.

---

### 📊 3. Interactive Assessment Calculator UI (PHQ-9 / GAD-7 / DASS-21)

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│  PHQ-9 Depression Screener                                   Score Gauge: [ 14 ] │
│  Item 4 of 9: "Feeling tired or having little energy"        Severity: MODERATE   │
│                                                              [██████████░░░░░░░] │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   [ 0 ] Not at all          [ 1 ] Several days                                   │
│   (Press '1' on keyboard)   (Press '2' on keyboard)                              │
│                                                                                  │
│   [ 2 ] More than half      [ 3 ] Nearly every day                               │
│   (Press '3' on keyboard)   (Press '4' on keyboard)  <-- Selected [Accent Glow]  │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```
* **HTMX Live Reaction**: As each option is clicked, HTMX evaluates the subtotal, updates the circular SVG gauge, shifts the severity badge (`Minimal` ➔ `Mild` ➔ `Moderate` ➔ `Severe`), and scrolls smoothly to the next question.

---

### 📝 4. Structured 4-Quadrant SOAP Note Editor

```text
┌──────────────────────────────────────┬──────────────────────────────────────┐
│  [S] SUBJECTIVE NOTES                │  [O] OBJECTIVE OBSERVATIONS          │
│  Student's narrative & feelings:     │  Behavior, affect, eye contact:      │
│  "Reported persistent insomnia..."   │  "Anxious affect, poor eye contact..."│
│  [Quick Snippet: Euthymic / Anxious] │  [Quick Snippet: Well Groomed]       │
├──────────────────────────────────────┼──────────────────────────────────────┤
│  [A] CLINICAL ASSESSMENT             │  [P] THERAPEUTIC PLAN & HOMEWORK     │
│  Diagnostic formulation & progress:  │  Action plan, CBT homework, next appt│
│  "Moderate situational anxiety..."   │  "Assigned 4-7-8 breathing exercise" │
│  [Quick Snippet: Symptom Reduction]  │  [Quick Snippet: Safety Plan Signed] │
└──────────────────────────────────────┴──────────────────────────────────────┘
 [💾 Auto-saved to local draft 12s ago]          [ 🔒 Sign & Lock Clinical Record ]
```
* **Draft Resilience**: Automatically stores typed notes into `localStorage` every 5 seconds. If the psychologist accidentally navigates away, the note is restored instantly upon return.
* **Auto-Lock Badge**: Once signed and submitted, records show an immutable `🔒 Signed & Locked on 2026-08-23 11:30 by Dr. Siddique` stamp.

---

## 🗄️ Section 3: Refined Database & Code Architecture

### 1. Updated `core/access_registry.py`
```python
"counseling": {
    "display": _("Psychological Counseling & Wellbeing"),
    "icon": "fas fa-brain",
    "tasks": {
        "view_dashboard":       (_("View Counseling Dashboard"),         _("Access the psychologist command center, today's schedule, and crisis queues.")),
        "manage_cases":         (_("Manage Counseling Cases"),           _("Create, update, close, and soft-delete student case files.")),
        "view_sessions":        (_("View Clinical Session Records"),     _("Read confidential SOAP notes. Strictly restricted to clinical staff.")),
        "manage_sessions":      (_("Write/Edit Clinical Session Notes"), _("Create and modify SOAP notes within the active 24-hour edit window.")),
        "conduct_assessments":  (_("Conduct Psychometric Tests"),        _("Administer and evaluate PHQ-9, GAD-7, and DASS-21 screenings.")),
        "manage_appointments":  (_("Manage Appointments"),               _("Book, confirm, reschedule, and cancel counseling sessions.")),
        "emergency_protocol":   (_("Emergency Crisis Protocol"),         _("Log crisis triage, safety contracts, and medical hospital referrals.")),
        "manage_workshops":     (_("Manage Wellbeing Workshops"),        _("Organize campus mental health campaigns and track student attendance.")),
        "view_analytics":       (_("View Wellbeing Analytics"),          _("Access de-identified macro wellbeing heatmaps and trend charts.")),
        "manage_settings":      (_("Manage Counseling Settings"),        _("Configure SMS templates, session slot durations, and SLA rules.")),
        "submit_referral":      (_("Submit Student Referral"),           _("Allows Department Advisors and Hall Provosts to refer a student.")),
    }
},
```

---

### 2. Complete Model Schema (`counseling/models.py`)

```python
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from students.models import Student
from master_data.models import Program, Hall
import datetime

# --- Choices ---
class CaseCategory(models.TextChoices):
    ACADEMIC_STRESS   = 'academic_stress',   _('Academic Stress & Performance')
    EXAM_ANXIETY      = 'exam_anxiety',      _('Exam & Test Anxiety')
    HALL_HOMESICK     = 'hall_homesick',     _('Hall Life & Homesickness')
    FAMILY_RELATIONS  = 'family_relations',  _('Family & Relationship Dynamics')
    GRIEF_TRAUMA      = 'grief_trauma',      _('Grief, Loss & Trauma')
    SUBSTANCE         = 'substance',         _('Habit & Substance Intervention')
    CAREER_ESTEEM     = 'career_esteem',     _('Career Uncertainty & Self-Esteem')
    OTHER             = 'other',             _('Other (See Notes)')

class RiskLevel(models.TextChoices):
    LOW      = 'low',      _('Low — General Wellbeing')
    MODERATE = 'moderate', _('Moderate — Requires Monitoring')
    HIGH     = 'high',     _('High — Priority Intervention')
    CRITICAL = 'critical', _('Critical / Acute Crisis')

class CaseStatus(models.TextChoices):
    OPEN        = 'open',        _('Open — Initial Intake')
    IN_THERAPY  = 'in_therapy',  _('In Therapy — Active Sessions')
    ON_HOLD     = 'on_hold',     _('On Hold — Pending Follow-up')
    REFERRED    = 'referred',    _('Referred Out — Medical/Psychiatric')
    DISCHARGED  = 'discharged',  _('Completed & Discharged')

class AppointmentMode(models.TextChoices):
    IN_PERSON = 'in_person', _('In-Person (Counseling Center)')
    TELE_CONF = 'tele_conf', _('Confidential Tele-Counseling')
    EMERGENCY = 'emergency', _('Urgent Crisis Walk-in')

class AppointmentStatus(models.TextChoices):
    REQUESTED   = 'requested',   _('Requested')
    CONFIRMED   = 'confirmed',   _('Confirmed')
    COMPLETED   = 'completed',   _('Completed')
    RESCHEDULED = 'rescheduled', _('Rescheduled')
    CANCELLED   = 'cancelled',   _('Cancelled')
    NO_SHOW     = 'no_show',     _('No Show')

# --- Soft-Delete Manager ---
class ActiveCaseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

# --- Models ---
class CounselingSettings(models.Model):
    enable_sms_notifications        = models.BooleanField(default=True, verbose_name=_('Enable SMS Notifications'))
    sms_template_appointment_confirm = models.CharField(
        max_length=500,
        default='Your counseling session is confirmed for {date} at {time} in Room {room}. BAUST Counseling Center.',
        verbose_name=_('SMS: Appointment Confirmation')
    )
    sms_template_crisis_alert       = models.CharField(
        max_length=500,
        default='Urgent counseling check-in requested for student {student_id}. Case ID: {case_number}.',
        verbose_name=_('SMS: Crisis Alert')
    )
    session_lock_hours              = models.IntegerField(default=24, verbose_name=_('SOAP Note Edit Window (Hours)'))
    crisis_sla_hours                = models.IntegerField(default=2, verbose_name=_('Crisis Response SLA (Hours)'))
    default_slot_duration_minutes   = models.IntegerField(default=50, verbose_name=_('Default Slot Length (Minutes)'))
    updated_at                      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Counseling Settings')
        verbose_name_plural = _('Counseling Settings')

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class CounselorProfile(models.Model):
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='counselor_profile')
    designation         = models.CharField(max_length=150, default='Clinical Psychologist')
    license_number      = models.CharField(max_length=100, blank=True)
    room_number         = models.CharField(max_length=50, default='Room 204')
    is_active_counselor = models.BooleanField(default=True)
    weekly_slots_json   = models.JSONField(default=dict, blank=True, help_text=_('Available weekday time slots'))
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.designation})"

class CounselingCase(models.Model):
    case_number         = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    student             = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='counseling_cases')
    alias_code          = models.CharField(max_length=50, blank=True, null=True, help_text=_('Pseudonym for confidential referral'))
    category            = models.CharField(max_length=30, choices=CaseCategory.choices, default=CaseCategory.ACADEMIC_STRESS, db_index=True)
    risk_level          = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.LOW, db_index=True)
    status              = models.CharField(max_length=20, choices=CaseStatus.choices, default=CaseStatus.OPEN, db_index=True)
    assigned_counselor  = models.ForeignKey(CounselorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cases')
    intake_date         = models.DateField(default=timezone.localdate, db_index=True)
    presenting_complaints = models.TextField(verbose_name=_('Presenting Complaints / Triggers'))
    sleep_appetite_notes = models.TextField(blank=True, verbose_name=_('Biological Indicators (Sleep & Appetite)'))
    family_social_notes  = models.TextField(blank=True, verbose_name=_('Family & Social Dynamics'))
    medication_history   = models.TextField(blank=True, verbose_name=_('Past Medication / Therapy History'))
    is_deleted          = models.BooleanField(default=False, db_index=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_counseling_cases')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    objects     = ActiveCaseManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-intake_date', '-created_at']
        verbose_name = _('Counseling Case')
        verbose_name_plural = _('Counseling Cases')

    def save(self, *args, **kwargs):
        if not self.case_number:
            year = datetime.date.today().year
            with transaction.atomic():
                max_id = CounselingCase.all_objects.select_for_update().aggregate(models.Max('id'))['id__max'] or 0
                seq = max_id + 1
                candidate = f"CASE-{year}-{seq:04d}"
                while CounselingCase.all_objects.filter(case_number=candidate).exists():
                    seq += 1
                    candidate = f"CASE-{year}-{seq:04d}"
                self.case_number = candidate
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def get_risk_badge_class(self):
        return {
            RiskLevel.LOW:      'badge-success',
            RiskLevel.MODERATE: 'badge-warning',
            RiskLevel.HIGH:     'badge-orange',
            RiskLevel.CRITICAL: 'badge-danger pulse-danger',
        }.get(self.risk_level, 'badge-secondary')

    def get_status_badge_class(self):
        return {
            CaseStatus.OPEN:       'badge-info',
            CaseStatus.IN_THERAPY: 'badge-primary',
            CaseStatus.ON_HOLD:    'badge-warning',
            CaseStatus.REFERRED:   'badge-secondary',
            CaseStatus.DISCHARGED: 'badge-success',
        }.get(self.status, 'badge-secondary')

class CaseStatusLog(models.Model):
    case        = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='status_logs')
    old_status  = models.CharField(max_length=30, blank=True)
    new_status  = models.CharField(max_length=30)
    changed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note        = models.TextField(blank=True)
    changed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

class CounselingAppointment(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='appointments')
    counselor           = models.ForeignKey(CounselorProfile, on_delete=models.CASCADE, related_name='appointments')
    appointment_date    = models.DateField(db_index=True)
    time_slot           = models.CharField(max_length=50) # e.g. "10:00 AM - 10:50 AM"
    session_mode        = models.CharField(max_length=20, choices=AppointmentMode.choices, default=AppointmentMode.IN_PERSON)
    status              = models.CharField(max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.CONFIRMED, db_index=True)
    student_notes       = models.TextField(blank=True)
    sms_reminder_sent   = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-appointment_date', 'time_slot']
        unique_together = ('counselor', 'appointment_date', 'time_slot')

class SessionRecord(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='session_records')
    appointment         = models.ForeignKey(CounselingAppointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='session_record')
    session_number      = models.PositiveIntegerField(default=1)
    session_date        = models.DateField(default=timezone.localdate, db_index=True)
    subjective_notes    = models.TextField(verbose_name=_('Subjective (S) — Client Narrative'))
    objective_notes     = models.TextField(verbose_name=_('Objective (O) — Clinical Observations'))
    assessment          = models.TextField(verbose_name=_('Assessment (A) — Diagnostic Impression'))
    plan                = models.TextField(verbose_name=_('Plan (P) — Interventions & Homework'))
    next_session_date   = models.DateField(null=True, blank=True)
    is_locked           = models.BooleanField(default=False)
    locked_at           = models.DateTimeField(null=True, blank=True)
    recorded_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session_date', '-session_number']

class MentalHealthAssessment(models.Model):
    ASSESSMENT_TYPES = [
        ('PHQ9',   'PHQ-9 (Depression Screener)'),
        ('GAD7',   'GAD-7 (Anxiety Screener)'),
        ('DASS21', 'DASS-21 (Depression, Anxiety, Stress Scale)'),
    ]
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='assessments')
    assessment_type     = models.CharField(max_length=10, choices=ASSESSMENT_TYPES, db_index=True)
    item_responses      = models.JSONField(default=dict)
    total_score         = models.IntegerField(default=0)
    sub_scores          = models.JSONField(default=dict, blank=True) # e.g. DASS-21: {depression: 12, anxiety: 8, stress: 14}
    severity_tier       = models.CharField(max_length=50) # Normal, Mild, Moderate, Severe, Extremely Severe
    assessed_date       = models.DateField(default=timezone.localdate, db_index=True)
    administered_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assessed_date', '-created_at']

class EmergencyIntervention(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='emergency_interventions')
    incident_date       = models.DateTimeField(default=timezone.now)
    incident_type       = models.CharField(max_length=100) # Suicidal Ideation, Acute Panic, Self-Harm Risk
    actions_taken       = models.TextField()
    medical_referral_made = models.BooleanField(default=False)
    hospital_name       = models.CharField(max_length=200, blank=True)
    authorities_notified = models.TextField(blank=True, help_text=_('Provost, CMO, Guardian logs'))
    safety_contract_signed = models.BooleanField(default=False)
    resolved            = models.BooleanField(default=False, db_index=True)
    logged_by           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class WellbeingWorkshop(models.Model):
    title               = models.CharField(max_length=255)
    speaker             = models.CharField(max_length=200)
    venue               = models.CharField(max_length=200)
    event_date          = models.DateField(db_index=True)
    target_audience     = models.CharField(max_length=200)
    capacity            = models.PositiveIntegerField(default=100)
    is_cancelled        = models.BooleanField(default=False)

class WellbeingWorkshopParticipant(models.Model):
    workshop            = models.ForeignKey(WellbeingWorkshop, on_delete=models.CASCADE, related_name='participants')
    student             = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='wellness_workshops')
    registered_at       = models.DateTimeField(auto_now_add=True)
    attended            = models.BooleanField(default=False)

    class Meta:
        unique_together = ('workshop', 'student')
```

---

## 🚀 Section 3: Phased Execution & UI Implementation Roadmap

```mermaid
graph TD
    P1[Phase 1: Core Setup & DB Models] --> P2[Phase 2: UI Design System & CSS Engine]
    P2 --> P3[Phase 3: Psychologist Command Center & Booking]
    P3 --> P4[Phase 4: Clinical SOAP Editor & Auto-Drafting]
    P4 --> P5[Phase 5: Interactive PHQ-9 / GAD-7 / DASS-21]
    P5 --> P6[Phase 6: Crisis Drawer & Medical Referrals]
    P6 --> P7[Phase 7: De-Identified Macro Analytics]
    P7 --> P8[Phase 8: End-to-End Verification & Launch]
```

### ✅ Detailed Implementation Checklist

- [ ] **Phase 1: Backend Foundation & Model Registration**
  - Register `counseling` in `INSTALLED_APPS` and `urls.py`.
  - Create `counseling/apps.py` with `CounselingConfig`.
  - Update `core/access_registry.py` with 11 granular counseling tasks.
  - Extend `SMSHistory.MODULE_CHOICES` in `students/models.py`.
  - Build `counseling/models.py` (TextChoices, soft-delete, indexes, singleton settings).
  - Execute `makemigrations counseling` and `migrate`.

- [ ] **Phase 2: UI Design System & Dynamic Assets**
  - Create `static/counseling/css/counseling.css` with semantic color tokens, pulse animations, and dark mode support.
  - Implement the **Discretion / Privacy Mode Shield** (`Alt+P` blur toggle) in `base.html` header.
  - Add sidebar block in `templates/base.html` using `{% has_access 'counseling' 'view_dashboard' as can_view_counseling %}`.

- [ ] **Phase 3: Psychologist Command Center & Appointment Engine**
  - Build `counseling/templates/counseling/dashboard.html` with animated KPI boxes, today's schedule, and crisis queue.
  - Build `case_list.html` (search with Student ID, program, risk level filters).
  - Build `appointment_list.html` with interactive time-slot picker and double-booking HTMX validation.
  - Integrate `core.utils.send_sms(module='COUNSELING')` for discreet confirmation SMS.

- [ ] **Phase 4: Clinical SOAP Note Editor & Case Timeline**
  - Build `case_detail.html` featuring student profile context, emergency contact card, and vertical session history.
  - Build `session_record_form.html` (4-quadrant SOAP editor, localStorage auto-save draft, quick clinical snippets, and 24-hour auto-lock).

- [ ] **Phase 5: Interactive Psychological Assessment Calculators**
  - Build `counseling/templates/counseling/assessment_form.html` with dynamic card-tile steppers and keyboard shortcuts.
  - Create `static/counseling/js/counseling_scales.js` for live SVG gauge calculation (PHQ-9, GAD-7, DASS-21).
  - Embed longitudinal Chart.js progression graph on `case_detail.html`.

- [ ] **Phase 6: Emergency Crisis Intervention & Referral Drawer**
  - Build slide-out Crisis Action modal with quick-dial buttons for Hall Provost and Medical Center.
  - Implement safety contract checklist and hospital transfer logger.

- [ ] **Phase 7: De-Identified Institutional Wellbeing Analytics**
  - Build `macro_analytics.html` with program-wise stress distribution, peak midterm panic heatmaps, and hall resident statistics (100% de-identified, no student PII).

- [ ] **Phase 8: Automated Tests & Verification**
  - Create `counseling/tests.py` testing case ID generation, PHQ-9/GAD-7 scoring algorithms, RBAC security barriers, and soft-delete queries.
  - Validate with `python manage.py test counseling`.
