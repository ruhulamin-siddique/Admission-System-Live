"""
Central registry defining all modules and their granular tasks for the RBAC system.
"""

ACCESS_REGISTRY = {
    "dashboard": {
        "display": "Dashboard",
        "icon": "fas fa-tachometer-alt",
        "tasks": {
            "view": ("View Dashboard", "Allows access to the main dashboard and summary widgets."),
        }
    },
    "students": {
        "display": "Student Management",
        "icon": "fas fa-users",
        "tasks": {
            "view_directory": ("Intelligence Search & Directory", "Access the Global Search and browse the student database."),
            "add_student": ("Admit New Student", "Process new admissions and enroll students."),
            "edit_profile": ("Edit Student Profile", "Update student biographical and academic info."),
            "manage_migrations": ("Program Migrations", "Manage department changes and student program history."),
            "cancel_admission": ("Admission Cancellation", "Manage individual and bulk admission cancellations."),
            "delete_record": ("Delete Student", "Permanently remove student records from system."),
            "export_excel": ("Export to Excel", "Generate and download the 44-column Excel master list."),
            "bulk_import": ("Bulk Excel Import", "Upload and process mass student registrations."),
            "data_integrity": ("Data Integrity Scanner", "Scan the database and merge duplicate records."),
            "bulk_update": ("Mass Data Harmonizer", "Modify fields across multiple selected students at once."),
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
    "security": {
        "display": "Security & Staff",
        "icon": "fas fa-user-shield",
        "tasks": {
            "manage_roles": ("Manage Roles & Permissions", "Define user roles and assign registry tasks to them."),
            "manage_users": ("Manage System Users", "Create and manage system login accounts and their roles."),
            "manage_settings": ("Manage System Branding", "Update institutional name, logo, and theme colors."),
            "manage_academic_settings": ("Manage Academic Master Data", "Configure Programs, Halls, Batches, and Session settings."),
            "manage_api": ("Manage External API", "Issue API credentials and inspect external request audit logs."),
        }
    }
}
