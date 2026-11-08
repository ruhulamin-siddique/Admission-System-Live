"""
Central registry defining all modules and their granular tasks for the RBAC system.
"""

from django.utils.translation import gettext_lazy as _

ACCESS_REGISTRY = {
    "dashboard": {
        "display": "Dashboard",
        "icon": "fas fa-tachometer-alt",
        "tasks": {
            "view": ("View Dashboard", "Allows access to the main dashboard and summary widgets."),
        }
    },
    "coe": {
        "display": "Controller of Examinations (CoE)",
        "icon": "fas fa-graduation-cap",
        "tasks": {
            "dept_head_review":      ("Dept. Head Review & Approval",     "Review, approve, hold, or reject applications as Dept. Head. Supports bulk actions."),
            "coe_desk_assign":       ("CoE Desk — Assignment & Kanban",   "Review pending assignments, view Kanban board, assign to processing officers."),
            "processing_officer":    ("Processing Officer Workstation",   "Verify records via board/admission API, request re-uploads, mark ready for delivery."),
            "delivery_desk":         ("Delivery Desk — OTP Handover",     "Search applications by tracking ID, verify OTP, log physical delivery."),
            "view_all_applications": ("View All Applications",            "View and search all applications across departments and statuses."),
            "export_data":           ("Export & Print",                   "Export application data to Excel and generate print-formatted summaries."),
            "manage_settings":       ("Manage CoE Settings",              "Configure tracking ID prefix, SMS rules, and retention policies."),
        }
    },
    "exam_billing": {
        "display": "Exam Billing",
        "icon": "fas fa-file-invoice-dollar",
        "tasks": {
            "view_dashboard": ("View Billing Dashboard", "Access exam billing dashboards and summaries."),
            "manage_exams": ("Manage Billing Exams", "Create exams and open departments/programs for billing."),
            "delete_exam": ("Delete Exam", "Permanently remove an exam and all associated billing data."),
            "manage_department_data": ("Manage Department Billing Data", "Enter faculty, courses, and committee duty sheets."),
            "manage_global_settings": ("Manage Billing Settings", "Configure global default bill rates and rules."),
            "approve_finalize": ("Approve and Finalize Bills", "Approve, lock, reopen, and finalize department bills."),
            "view_all_departments": ("View All Departments", "See billing data across all departments/programs."),
            "export_print": ("Export and Print Bills", "Print individual bills and export billing summaries."),
            "bulk_import_faculty": ("Bulk Import Faculty", "Upload faculty profiles in bulk using Excel templates."),
        }
    },
    "students": {
        "display": "Admission",
        "icon": "fas fa-users",
        "tasks": {
            "view_directory": ("Admission Search & Directory", "Access the Global Search and browse the student database."),
            "add_student": ("Admit New Student", "Process new admissions and enroll students."),
            "edit_profile": ("Edit Student Profile", "Update student biographical and academic info."),
            "view_migrations": ("View Migration Center", "Allows browsing, searching, and viewing academic migrations directory."),
            "manage_migrations": ("Execute Academic Migration", "Allows processing a program migration/department change."),
            "export_migrations": ("Export Migration History", "Allows downloading Excel logs of academic migrations."),
            "view_cancellations": ("View Cancellation Hub", "Allows access to search, browse, and view cancelled students lists."),
            "cancel_admission": ("Cancel/Modify Admission", "Allows executing individual and bulk admission cancellations/suspensions."),
            "export_cancellations": ("Export & Print Cancellations", "Allows generating Excel downloads of cancelled student directories."),
            "delete_record": ("Delete Student", "Permanently remove student records from system."),
            "export_excel": ("Export to Excel", "Generate and download the 44-column Excel master list."),
            "bulk_import": ("Bulk Excel Import", "Upload and process mass student registrations."),
            "data_integrity": ("Duplicate Record Scanner", "Identify and merge duplicate student profiles."),
            "academic_audit": ("Academic Board Audit", "Verify student SSC/HSC data against official education board portals."),
            "mobile_repair": ("Mobile Number Repair", "Identify and fix incorrectly formatted mobile numbers missing leading zeros."),
            "bulk_update": ("Mass Data Harmonizer", "Modify fields across multiple selected students at once."),
            "manage_references": ("Reference Hub Manager", "Access, update, and merge standardized Reference Hub nodes."),
            "patch_academic_data": ("Academic Data Patch", "Upload scoped Excel to patch SSC/HSC academic data for a batch or program."),
            "view_applications": ("Student Applications Desk", "Review, filter, verify, and update submitted admission applications."),
            "manage_application_templates": ("Manage Application Templates", "Upload, replace, and remove DOCX/PDF templates and toggle validation policy."),
            "delete_application": ("Delete Student Application", "Permanently remove submitted admission applications from the desk (Super Admin and authorized officers only)."),
            "manage_online_applicants": ("Online Applicants Hub", "View, filter, verify board data, verify payment, edit, print, and manage online admission applicants."),
            "manage_admission_intakes": ("Manage Admission Intakes", "Create, edit, open/close admission intake sessions, set fees, bKash numbers, exam venue, and deadlines."),
        }
    },
    "reports": {
        "display": "Reports & Analytics",
        "icon": "fas fa-chart-line",
        "tasks": {
            "view_analytics": ("View Academic Analytics", "Access intake quality and GPA distribution reports."),
            "view_finance": ("View Financial Dashboard", "Access payment, waiver, and installment summaries."),
            "generate_pdf": ("Generate PDF Profiles", "Export individual student master sheets to PDF."),
        }
    },
    "ict_wing": {
        "display": "ICT Wing",
        "icon": "fas fa-network-wired",
        "tasks": {
            "view_devices": ("View Registered Devices", "Browse and search user device registrations."),
            "manage_devices": ("Approve/Bind Devices", "Approve, reject, edit notes, and assign IP addresses to devices."),
        }
    },
    "public_relations": {
        "display": _("Public Relations"),
        "icon": "fas fa-newspaper",
        "tasks": {
            "view_dashboard": (_("View PR Dashboard"), _("Access the PR Office dashboard with KPI statistics and recent entries.")),
            "view_archive": (_("View Press Release Archive"), _("Browse, search, and view individual press release entries.")),
            "add_archive": (_("Add Press Release"), _("Create new press release archive entries with coverage and asset rows.")),
            "edit_archive": (_("Edit Press Release"), _("Modify existing press release entries and their media coverage rows.")),
            "delete_archive": (_("Delete Press Release"), _("Permanently remove press release entries and all linked data.")),
            "export_data": (_("Export PR Data"), _("Download Excel reports and generate printable PDF press releases.")),
            "manage_media_houses": (_("Manage Media Houses"), _("Add, edit, and maintain the media outlet directory.")),
        }
    },
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
    "security": {
        "display": "Security & Staff",
        "icon": "fas fa-user-shield",
        "tasks": {
            "manage_roles": ("Manage Roles & Permissions", "Define user roles and assign registry tasks to them."),
            "manage_users": ("Manage System Users", "Create and manage system login accounts and their roles."),
            "manage_settings": ("Manage System Branding", "Update institutional name, logo, and theme colors."),
            "manage_academic_settings": ("Manage Academic Master Data", "Configure Programs, Halls, Batches, and Session settings."),
            "manage_sms": ("SMS Gateway Hub", "Access live balance checker, SMS profiles, dispatch test messages, and logs."),
            "manage_api": ("Manage External API", "Issue API credentials and inspect external request audit logs."),
            "download_backup_json": ("Download Database JSON Backup", "Allows downloading a JSON dump of all system data."),
            "download_backup_sqlite": ("Download Database SQLite Backup", "Allows downloading a pre-compiled SQLite database binary."),
        }
    },
}
