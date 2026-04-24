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
            "view_directory": ("View Student Directory", "Browse and search the student database."),
            "add_student": ("Admit New Student", "Process new admissions and enroll students."),
            "edit_profile": ("Edit Student Profile", "Update student biographical and academic info."),
            "delete_record": ("Delete Student", "Permanently remove student records from system."),
            "bulk_cancel": ("Bulk Admission Cancel", "Allows administrators to cancel multiple admissions at once."),
            "export_excel": ("Export to Excel", "Generate and download the 44-column Excel master list."),
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
    "security": {
        "display": "Security & Staff",
        "icon": "fas fa-user-shield",
        "tasks": {
            "manage_roles": ("Manage Roles & Permissions", "Define user roles and assign registry tasks to them."),
            "manage_users": ("Manage System Users", "Create and manage system login accounts and their roles."),
            "manage_settings": ("Manage System Branding", "Update institutional name, logo, and theme colors."),
        }
    }
}
