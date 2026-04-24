# Admission Suite - Modern Admission Management System

> **Last Updated**: 2026-04-21  
> **Status**: Active Development

A high-performance, secure, and modern Django-based web application designed for managing student admissions, academic records, and institutional reporting.

## 📜 Maintenance Policy

To maintain the system's "Self-Documenting" nature, this `README.md` **must** be updated immediately following any significant change to:
- Database Models
- API Endpoints/URL structures
- Security/RBAC Logic
- Environment Variables
- Core Utility functions

*This ensures that both human developers and AI coding assistants always have the correct context to work efficiently.*


## 🚀 Key Features

- **Student Lifecycle Management**: Comprehensive tracking from intake to graduation.
- **RBAC (Role-Based Access Control)**: Granular permission system for modules and specific tasks.
- **Academic Reporting**: Dynamic intake reports, master sheets, and analytics dashboards.
- **Security by Default**: Global authentication enforcement and session hardening.
- **Program Change History**: Audit logs for student program transfers.
- **SMS/Email History**: Integrated communication logging for all student notifications.

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Django 5.x/6.x
- **Database**: PostgreSQL (Supabase) / SQLite (Development)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (AJAX)
- **Styling**: Premium custom CSS with a focus on modern aesthetics.

## 📂 Project Structure

```text
Admission/
├── admission_system/      # Project configuration (settings, main URLs)
├── core/                  # Security, RBAC, User Profiles, and System Settings
│   ├── middleware.py      # Login required & activity enforcement
│   ├── decorators.py       # RBAC permission decorators
│   ├── models.py          # Role, Permission, UserProfile, SystemSettings
│   └── views.py           # Security management views
├── students/              # Main application module
│   ├── models.py          # Student, SMSHistory, ProgramChangeHistory
│   ├── reports.py         # Reporting & export logic
│   ├── utils.py           # ID generation and utility functions
│   └── views.py           # Dashboard, Student profile, Transfers
├── static/                # Global static assets (css, js, images)
├── templates/             # Global templates and layout components
└── manage.py              # Django management script
```

## 🔐 Security & RBAC

The system implements a custom RBAC layer:
- **Roles**: Logical groupings of permissions (e.g., "Registrar", "Accounts").
- **Permissions**: Defined by `module` and `task` strings matching the `@require_access` decorators in views.
- **Department Scope**: Optional field in `UserProfile` to restrict users to specific department data.

## 📊 Database Schema Summary

### `students` App
- **`Student`**: Primary record containing academic, personal, family, and financial details.
- **`ProgramChangeHistory`**: Stores logs of program transfers.
- **`SMSHistory`**: Logs of all communication sent via the system.

### `core` App
- **`Role` / `RolePermission`**: Defines the RBAC hierarchy.
- **`UserProfile`**: Ties Django `User` to a `Role` and scope.
- **`SystemSettings`**: Global branding (Logo, Theme Color, Institution Name).

## 🤖 AI Agent Context

This section provides critical pointers for AI coding assistants:
- **ID Logic**: `students/utils.py` handles UGC-compliant student ID generation.
- **Access Control**: Use `@require_access('students', 'task_name')` from `core.decorators` to protect views.
- **Query Filtering**: Most views should use `.filter(program=user.profile.department_scope)` if the user is not a superuser and has a scope defined.
- **Global Auth**: `core.middleware.LoginRequiredMiddleware` ensures all pages except `/login/` are restricted.

## 🛠️ Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Configuration**:
   Ensure `.env` contains:
   - `SECRET_KEY`
   - `DEBUG`
   - `DATABASE_URL` (For Supabase/Postgres)
4. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```
5. **Run Development Server**:
   ```bash
   python manage.py run dev
   ```

---
*Created by Antigravity AI Assistant.*
