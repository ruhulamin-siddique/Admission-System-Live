# Admission Suite - Professional Admission Management System

> **Developed by**: Ruhulamin Siddique  
> **Last Updated**: 2026-04-25  
> **Status**: Production Ready 🚀

A high-performance, secure, and modern Django-based web application designed for managing student admissions, academic records, and institutional reporting.

## 👨‍💻 Developer Information
- **Lead Developer**: Ruhulamin Siddique
- **Organization**: BAUST (Bangladesh Army University of Science and Technology)
- **Role**: Administrator & System Architect

## 🚀 Key Features

- **Professional Deployment**: Optimized for cPanel with a Git-based automated workflow.
- **Universal Database Engine**: Seamlessly switches between **MySQL (Production)** and **SQLite (Local Development)**.
- **RBAC (Role-Based Access Control)**: Granular permission system for modules and specific tasks.
- **Environment Hardening**: Secure `.env` based configuration for sensitive credentials.
- **Student Lifecycle Management**: Comprehensive tracking from intake to graduation.
- **Security by Default**: Global authentication enforcement and session hardening.
- **Premium UI**: Modern, iconized navigation and mobile-responsive layouts.

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Django 5.x/6.x
- **Database**: MySQL (Production - cPanel) / SQLite (Local)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (AJAX / HTMX)
- **Styling**: Premium custom CSS with modern aesthetics.

## 📂 Project Structure

```text
Admission/
├── admission_system/      # Project configuration (settings, main URLs)
├── core/                  # Security, RBAC, User Profiles, and System Settings
│   ├── middleware.py      # Login required & activity enforcement
│   ├── decorators.py      # RBAC permission decorators
│   ├── models.py          # Role, Permission, UserProfile, SystemSettings
│   └── views.py           # Security management views
├── students/              # Main application module
│   ├── models.py          # Student, SMSHistory, ProgramChangeHistory
│   ├── reports.py         # Reporting & export logic
│   ├── utils.py           # ID generation and utility functions
│   └── views.py           # Dashboard, Student profile, Transfers
├── static/                # Global static assets (css, js, images)
├── templates/             # Global templates and layout components
├── .env                   # Environment variables (Not in Version Control)
├── passenger_wsgi.py      # cPanel Entry Point
└── manage.py              # Django management script
```

## 🔐 Security & RBAC

The system implements a custom RBAC layer:
- **Roles**: Logical groupings of permissions (e.g., "Registrar", "Accounts").
- **Permissions**: Defined by `module` and `task` strings matching the `@require_access` decorators in views.
- **Self-Service**: Every staff member can manage their own profile and security credentials via a dedicated portal.

## 📊 Deployment Workflow

1. **Local Development**: Work on PC using SQLite for speed and offline capability.
2. **Push**: `git push origin main` to the GitHub repository.
3. **Deploy**: `git pull origin main` on the cPanel terminal.
4. **Finalize**: Restart the Python App in the cPanel "Setup Python App" interface.

---
Developed with ❤️ by **Ruhulamin Siddique**.
