# Admission Suite - Professional Admission Management System

> **Developed by**: Ruhulamin Siddique  
> **Last Updated**: 2026-05-16
> **Status**: Production Ready 🚀

A high-performance, secure, and modern Django-based web application designed for managing student admissions, academic records, and institutional examination billing.

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

### 💰 Exam Billing & Remuneration
- **Automated Calculations**: Sophisticated engine for computing faculty remuneration across multiple exam parts.
- **Premium Analytics**: Real-time projected payable tracking and departmental progress monitoring.
- **Document Generation**: One-click generation of professional PDF bills, attendance sheets, and summary statements.

### 👤 Student Life Cycle 360
- **Unified Timeline**: A vertical history showing every event from admission and migration to board verification and status changes.
- **Academic Board Verification**: Human-in-the-loop scraping engine for automated SSC/HSC verification from official board portals.
- **Program Migrations**: Automated handling of department changes with full historical tracking.
- **Identity Hub**: Advanced ID rectification tools that preserve data integrity across the entire suite.

### 📊 Strategic Intelligence
- **Geographic Insights**: Dynamic heatmaps and district-wise recruitment analytics.
- **Institutional Intelligence**: Top feeder school/college tracking with intake quality analysis.
- **Financial Analytics**: Comprehensive revenue, waiver, and installment tracking.
- **Subject Performance**: Deep-dive analysis of science subject marks (Phy/Che/Mat) by intake batch.

### 🛡️ Security & Performance
- **Granular RBAC**: Role-Based Access Control with task-level precision (Manage Audit, Manage Roles, Manage API, etc.).
- **Audit Logging**: Comprehensive activity tracking with session handshakes and IP logging.
- **Universal Database Engine**: Seamlessly switches between **MySQL (Production)** and **SQLite (Local Development)**.

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Django 5.x/6.x
- **Database**: MySQL (Production - cPanel) / SQLite (Local)
- **Frontend**: HTML5, Vanilla CSS, JavaScript (**HTMX** for real-time reactivity)
- **Styling**: Premium custom CSS with glassmorphism and modern UI/UX patterns.

## 📂 Project Structure

```text
Admission/
├── admission_system/      # Project configuration
├── core/                  # Security, RBAC, User Profiles, Activity Logging
├── exam_billing/          # Remuneration module
├── students/              # Admission & Verification module
├── master_data/           # Academic master data (Programs, Halls, etc.)
├── static/                # Global static assets
├── templates/             # Premium layout components
├── .env                   # Environment variables
└── manage.py              # Django management script
```

## 🔐 Deployment Workflow

1. **Local Development**: Work on PC using SQLite for speed and offline capability.
2. **Push**: `git push origin main` to the GitHub repository.
3. **Deploy**: `git pull origin main` on the cPanel terminal.
4. **Finalize**: Restart the Python App in the cPanel "Setup Python App" interface.

---
Developed with ❤️ by **Ruhulamin Siddique**.
