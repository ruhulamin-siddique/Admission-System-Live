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

### 🏢 Command Center Header
- **Global Intelligence Search**: Real-time "Google-style" search engine (ID, Name, Mobile, Email) powered by HTMX.
- **Live Notification Feed**: Instant activity tracking (New Admissions, Updates, Security) directly in the navbar.
- **Theme Engine**: Persistent **Dark Mode** toggle with AdminLTE native integration.
- **Sticky Layout**: One-click "Pin/Unpin" header toggle preserved across sessions.

### 👤 Staff Identity Hub 2.0
- **Premium Dashboards**: Every staff member has a glassmorphism-styled personal dashboard.
- **Work Analytics**: Individual stats tracking (Total Admissions Performed, Account Age).
- **Personal Timeline**: A vertical history of the specific user's latest actions for accountability.
- **Avatar Management**: Full support for professional profile photos with fallback initial avatars.

### 🛡️ Security & Performance
- **RBAC (Role-Based Access Control)**: Granular permission system for modules and specific tasks.
- **Identity Security**: Redesigned password management portal with "Security-First" aesthetics.
- **Universal Database Engine**: Seamlessly switches between **MySQL (Production)** and **SQLite (Local Development)**.
- **Security by Default**: Global authentication enforcement and session hardening.

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Django 5.x/6.x
- **Database**: MySQL (Production - cPanel) / SQLite (Local)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (**HTMX** for real-time reactivity)
- **Styling**: Premium custom CSS with glassmorphism and modern UI/UX patterns.

## 📂 Project Structure

```text
Admission/
├── admission_system/      # Project configuration (settings, main URLs)
├── core/                  # Security, RBAC, User Profiles, Activity Logging
│   ├── middleware.py      # Login required & activity enforcement
│   ├── context_processors # Global system settings & live notifications
│   ├── models.py          # Role, UserProfile, ActivityLog, SystemSettings
│   └── views.py           # Security, Theme toggles, Profile management
├── students/              # Main application module
│   ├── models.py          # Student, SMSHistory, ProgramChangeHistory
│   ├── reports.py         # Reporting & export logic
│   └── views.py           # Dashboard, Intelligence Search, Transfers
├── static/                # Global static assets (css, js, images)
├── templates/             # Global templates and layout components
├── .env                   # Environment variables (Not in Version Control)
├── passenger_wsgi.py      # cPanel Entry Point
└── manage.py              # Django management script
```

## 🔐 Deployment Workflow

1. **Local Development**: Work on PC using SQLite for speed and offline capability.
2. **Push**: `git push origin main` to the GitHub repository.
3. **Deploy**: `git pull origin main` on the cPanel terminal.
4. **Finalize**: Restart the Python App in the cPanel "Setup Python App" interface.

---
Developed with ❤️ by **Ruhulamin Siddique**.
