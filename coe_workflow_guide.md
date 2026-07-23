# 🎓 CoE Academic Document Processing — Complete Workflow Guide

> **Office of the Controller of Examinations (CoE)**
> BAUST Student Document Application Portal

---

## 📋 What is this system?

Students at BAUST who need official academic documents (certificates, transcripts, grade sheets, recommendation letters, etc.) must formally apply through the **CoE Portal**. This system manages the entire journey — from the student's online application all the way to physical document handover at the CoE Desk — with SMS notifications at every major step.

---

## 🗂️ Supported Document Types

| # | Document | Who Needs It |
|---|----------|-------------|
| 1 | **Main / Original Certificate** | Final year graduates |
| 2 | **Provisional / Main Academic Transcript** | Job or higher study applications |
| 3 | **Incomplete Academic Transcript** | Mid-study applications |
| 4 | **Student's Name Correction** | Name mismatch with NID/Board certificate |
| 5 | **Father/Mother Name Correction** | Parent name mismatch |
| 6 | **Recommendation Letter** | Scholarship, visa, job purpose |
| 7 | **Grade Sheet** | Specific semester/term grade record |
| 8 | **Duplicate Documents (as per GD)** | Replacement for lost documents |

---

## 👥 Who is Involved?

```mermaid
graph LR
    A["🎓 Student\n(Public — No Login)"] --> B["🏫 Department Head\n(HoD)"]
    B --> C["🏛️ CoE / Deputy CoE\n(Assignment Desk)"]
    C --> D["⚙️ Processing Officer\n(IT / Section Officer)"]
    D --> E["📦 Delivery Clerk\n(Counter Operator)"]
    E --> A

    style A fill:#4f46e5,color:#fff,stroke:none
    style B fill:#0891b2,color:#fff,stroke:none
    style C fill:#7c3aed,color:#fff,stroke:none
    style D fill:#059669,color:#fff,stroke:none
    style E fill:#d97706,color:#fff,stroke:none
```

---

## 🔄 Full Application Lifecycle — At a Glance

```mermaid
flowchart TD
    START(["🎓 Student visits CoE Portal\n/coe/submit/"]) --> W1

    W1["📋 Step 1\nChoose Document Type"] --> W2
    W2["📝 Step 2\nFill Academic Information"] --> W3
    W3["📎 Step 3\nUpload Required Attachments\n(Max 2MB each)"] --> W4
    W4["✅ Step 4\nReview & Confirm Payment"] --> SUBMIT

    SUBMIT(["📤 Application Submitted\nSystem generates Tracking ID & PIN\n📱 SMS sent to student"]) --> HOD

    HOD{"🏫 Department Head\nReviews Application"}
    HOD -- "✅ Approve & Forward" --> PEND_COE
    HOD -- "⏸️ Hold" --> ACTION_HOD["📋 Student notified\nApplication on hold"]
    HOD -- "❌ Reject with Reason" --> REJECTED

    PEND_COE["🏛️ CoE Desk\nPending Assignment Pool"] --> ASSIGN

    ASSIGN{"👨‍💼 CoE / DCoE\nAssigns to Processing Officer"}
    ASSIGN --> PROCESSING

    PROCESSING["⚙️ Processing Officer\nWorkstation\n(Split-screen verification)"]

    PROCESSING --> VERIFY{"🔍 Verification Steps"}
    VERIFY --> API1["📡 Fetch Admission Portal Record\n(One-click)"]
    VERIFY --> API2["🏫 Board API Verification\n(SSC/HSC — Roll, Reg, Year)"]
    API1 --> DOC_READY
    API2 --> DOC_READY

    PROCESSING -- "⚠️ Bad/Missing Attachment" --> ACTION_REQ
    ACTION_REQ["📱 SMS to Student:\nPlease re-upload document\n+ Re-upload link\n\nStatus: Action Required"] --> PROCESSING

    DOC_READY["📄 Document Prepared &\nVerification Complete"] --> MARK_READY

    MARK_READY(["✅ Mark as Ready for Delivery\n📱 OTP SMS dispatched to student's mobile"])

    MARK_READY --> DELIVERY

    DELIVERY["📦 Delivery Clerk Desk\nStudent arrives at CoE Counter"]
    DELIVERY --> SCAN["🔍 Clerk searches by\nTracking ID or QR Scan"]
    SCAN --> OTP_CHECK{"🔐 Student presents\n6-digit OTP (from SMS)"}
    OTP_CHECK -- "✅ OTP Correct" --> ID_CHECK
    OTP_CHECK -- "❌ OTP Wrong / Expired" --> OTP_RETRY["Resend OTP to student"]
    OTP_RETRY --> OTP_CHECK

    ID_CHECK["👁️ Clerk verifies\nStudent ID Card / NID\n(Logged in system)"] --> DELIVERED

    DELIVERED(["🎉 DELIVERED\nApplication marked complete\n📱 Confirmation SMS sent"])

    REJECTED(["❌ REJECTED\nRejection reason saved\nFiles purged after 15 days"])

    style START fill:#4f46e5,color:#fff,stroke:none
    style SUBMIT fill:#4f46e5,color:#fff,stroke:none
    style HOD fill:#0891b2,color:#fff,stroke:none
    style PEND_COE fill:#7c3aed,color:#fff,stroke:none
    style ASSIGN fill:#7c3aed,color:#fff,stroke:none
    style PROCESSING fill:#059669,color:#fff,stroke:none
    style MARK_READY fill:#059669,color:#fff,stroke:none
    style DELIVERY fill:#d97706,color:#fff,stroke:none
    style DELIVERED fill:#16a34a,color:#fff,stroke:none
    style REJECTED fill:#dc2626,color:#fff,stroke:none
    style ACTION_REQ fill:#ea580c,color:#fff,stroke:none
```

---

## 🔢 Application Status — Complete State Map

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED : Student submits form

    SUBMITTED --> UNDER_HOD_REVIEW : Auto-routed to HoD

    UNDER_HOD_REVIEW --> PENDING_COE_ASSIGNMENT : HoD Approves
    UNDER_HOD_REVIEW --> REJECTED : HoD Rejects
    UNDER_HOD_REVIEW --> UNDER_HOD_REVIEW : HoD Holds (waits)

    PENDING_COE_ASSIGNMENT --> IN_PROCESSING : CoE assigns officer

    IN_PROCESSING --> ACTION_REQUIRED_BY_STUDENT : Officer requests re-upload
    ACTION_REQUIRED_BY_STUDENT --> IN_PROCESSING : Student re-uploads

    IN_PROCESSING --> READY_FOR_DELIVERY : Officer marks complete
    IN_PROCESSING --> REJECTED : Officer rejects (fraud/invalid)

    READY_FOR_DELIVERY --> DELIVERED : Clerk verifies OTP + ID

    DELIVERED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]

    note right of ACTION_REQUIRED_BY_STUDENT
        SMS sent to student
        Timer paused — not counted
        against processing SLA
    end note

    note right of READY_FOR_DELIVERY
        6-digit OTP dispatched
        via SMS to student
    end note
```

---

## 🎓 Role 1 — Student (Public Portal, No Login Required)

```mermaid
flowchart LR
    S1["🌐 Visit\n/coe/submit/"] --> S2
    S2["Step 1️⃣\nSelect Document Type\n(8 options shown as cards)"] --> S3
    S3["Step 2️⃣\nFill Your Details\n(Fields change based on\ndocument type selected)"] --> S4
    S4["Step 3️⃣\nUpload Documents\n📎 Max 2MB per file\nInline preview shown"] --> S5
    S5["Step 4️⃣\nPayment Confirmation\n+ Final Review"] --> S6

    S6{"Submit?"}
    S6 -- Yes --> S7
    S6 -- Edit --> S3

    S7(["✅ Application Submitted!\n\n📋 Your Tracking ID: APP-2026-XXXX\n🔑 Your PIN: XXXX\n📱 SMS confirmation sent"])

    S7 --> TRACK

    TRACK["🔍 Track Your Application\n/coe/track/\n\nEnter: Tracking ID + Mobile\nor Student ID"]
    TRACK --> STATUS["📊 See your current stage\non a progress bar:\n\nSubmitted → HoD Review\n→ In Processing\n→ Ready → Delivered"]

    style S7 fill:#16a34a,color:#fff,stroke:none
    style TRACK fill:#4f46e5,color:#fff,stroke:none
```

---

## 🏫 Role 2 — Department Head (HoD)

```mermaid
flowchart TD
    H1["🏫 HoD opens dashboard\nSees only their department's applications"] --> H2

    H2["📋 Application List\nFiltered by own department\n\nColumns: Student, Type, Submission Date, Status"]

    H2 --> H3{"Review Action"}

    H3 -- "Single Application" --> H4["Click application row\nSee student info +\nattachment summary"]
    H4 --> H5{"Decision"}
    H5 -- "✅ Approve & Forward" --> H6["Application moves to\nCoE Assignment Pool\n📱 Student notified"]
    H5 -- "⏸️ Hold" --> H7["Add note\nApplication stays\nin HoD queue"]
    H5 -- "❌ Reject" --> H8["Mandatory rejection reason\nApplication closed\n📱 Student notified"]

    H3 -- "Bulk Action\n(Multiple selected)" --> H9["Select checkboxes\nClick Bulk Approve"]
    H9 --> H6

    style H6 fill:#16a34a,color:#fff,stroke:none
    style H8 fill:#dc2626,color:#fff,stroke:none
```

---

## 🏛️ Role 3 — CoE / Deputy CoE (Assignment Kanban Desk)

```mermaid
flowchart TD
    C1["🏛️ CoE opens Kanban Board"] --> C2

    C2["📊 Three Columns Visible:\n\n| Pending Assignment | In Processing | Ready for Delivery |"]

    C2 --> C3["Each card shows:\n• Student name\n• Application type\n• Department\n• Days since submission\n⚠️ Red badge if > 48 hrs stalled"]

    C3 --> C4{"Action"}

    C4 -- "Assign Application" --> C5["Click 'Assign' on card\nPicker shows available\nProcessing Officers"]
    C5 --> C6["Select Officer\nClick Confirm"]
    C6 --> C7["Application moves to\n'In Processing' column\nOfficer notified"]

    C4 -- "Re-route if stalled" --> C8["Reassign to different\nofficer (bottleneck warning)"]

    C4 -- "View Analytics" --> C9["📈 Performance panel:\n• Avg processing time per officer\n• Applications completed this week\n• Bottleneck map"]

    style C7 fill:#059669,color:#fff,stroke:none
```

---

## ⚙️ Role 4 — Processing Officer (Verification Workstation)

```mermaid
flowchart TD
    P1["⚙️ Officer opens assigned application\nSplit-screen workstation loads"]

    P1 --> P2

    subgraph LEFT ["👈 LEFT PANEL — Student Data"]
        P2["📋 Student's submitted information\n(read-only)\n\n📎 Attachment Previewer\n(PDF / Image inline view)"]
    end

    subgraph RIGHT ["👉 RIGHT PANEL — Verification Tools"]
        P3["🔍 Verification Drawer"]
        P3 --> P4["📡 One-Click: Fetch\nAdmission Portal Record\n→ Auto-fills student data\nfrom BAUST database"]
        P3 --> P5["🏫 Board API Verification\nEnter: Roll, Registration,\nBoard Name, Year\n→ Fetches SSC/HSC results\nfrom national board API"]
    end

    P2 --> P6{"All Clear?"}
    P4 --> P6
    P5 --> P6

    P6 -- "✅ Everything verified" --> P7
    P6 -- "⚠️ Bad/missing document" --> P8

    P7["📄 Prepare physical document\nAdd verification notes"] --> P9
    P9(["✅ Mark as Ready for Delivery\n📱 OTP automatically\nSMS'd to student"])

    P8["Send Re-Upload Request\nType query message to student"] --> P10
    P10(["📱 SMS to student:\nDocument issue description\n+ Re-upload link\n\nStatus → Action Required\n(timer paused)"])
    P10 --> P11["Student re-uploads\nOfficer reviews again"]
    P11 --> P6

    style P9 fill:#059669,color:#fff,stroke:none
    style P10 fill:#ea580c,color:#fff,stroke:none
```

---

## 📦 Role 5 — Delivery Clerk (Counter Desk)

```mermaid
flowchart TD
    D1["📦 Clerk opens Delivery Dashboard\nShows all 'Ready for Delivery' applications"]

    D1 --> D2{"Find Application"}
    D2 -- "Type tracking ID" --> D3["Search results appear"]
    D2 -- "Scan QR from student's SMS" --> D3

    D3 --> D4["Identity Verification Pop-up appears:\n\n• Student photo (from DB)\n• Document type requested\n• Payment status indicator"]

    D4 --> D5["Ask student for 6-digit OTP\n(sent to their mobile\nwhen document was ready)"]

    D5 --> D6{"OTP Correct?"}
    D6 -- "✅ Correct" --> D7
    D6 -- "❌ Wrong" --> D8["Resend OTP option\nor refer to supervisor"]
    D8 --> D5

    D7["Physical ID Verification:\nCheck Student ID Card or Original NID\nLog verification note in system"] --> D9

    D9(["🎉 Click 'Mark as Delivered'\n\nApplication closed\nTimestamp recorded\nClerk name logged\n📱 Confirmation SMS to student"])

    style D9 fill:#16a34a,color:#fff,stroke:none
    style D8 fill:#dc2626,color:#fff,stroke:none
```

---

## 📱 SMS Notifications — Full Reference

| Event | Who Receives | Message (in Bangla) |
|-------|-------------|---------------------|
| 📤 Application Submitted | Student | Tracking ID + PIN provided |
| ✅ HoD Approved | Student | Application forwarded to CoE |
| ⚠️ Action Required | Student | Issue description + re-upload link |
| 📄 Ready for Delivery | Student | Document ready to collect + OTP |
| 🔁 OTP Resent | Student | New 6-digit OTP |
| 🎉 Delivered | Student | Confirmation of document handover |
| ❌ Rejected | Student | Rejection reason |

---

## 🗄️ Data Retention Policy

```mermaid
flowchart LR
    A["📤 Application\nSubmitted"] --> B{"Final Outcome"}

    B -- "✅ Delivered" --> C["📂 Attachments kept\nduring active period\n\n⏳ 90 days after delivery:\nFiles permanently deleted\nMetadata preserved forever"]

    B -- "❌ Rejected" --> D["⏳ 15–30 days after rejection:\nFiles permanently deleted\nRecord soft-deleted\nCore log preserved forever"]

    B -- "🚫 Cancelled" --> D

    style C fill:#059669,color:#fff,stroke:none
    style D fill:#dc2626,color:#fff,stroke:none
```

> **Why?** To keep server storage lean while preserving historical reporting integrity. All transaction records (who applied, what was processed, dates) remain permanently — only uploaded files are removed after the retention window.

---

## 🔐 Security Measures Summary

| Risk | Protection |
|------|-----------|
| Anyone claiming a document at counter | **6-digit OTP** must be provided (sent only to student's registered mobile) |
| Forged payment slips | Officer manually verifies at Processing Workstation; future: bKash/SSLCommerz integration |
| Unreadable/fraudulent attachments | `Action Required` state with officer query + student re-upload (workflow paused, not cancelled) |
| Application tracking without login | Requires **Tracking ID + Mobile Number** (two-factor lookup) |
| Stale data accumulating | Automated cron cleanup after retention windows |

---

## 📌 Quick Reference — Department Head Checklist

- [ ] Log in to the portal
- [ ] Go to **CoE → HoD Dashboard**
- [ ] Review pending applications in your department
- [ ] Check attached documents in each application
- [ ] Click **Approve & Forward** / **Hold** / **Reject with Reason**
- [ ] For bulk clear cases: use **Select All → Bulk Approve**

---

## 📌 Quick Reference — Processing Officer Checklist

- [ ] Log in to the portal
- [ ] Go to **CoE → Processing Workstation**
- [ ] Open your assigned application
- [ ] Click **Fetch Admission Record** (right panel)
- [ ] Fill in Board details → Click **Verify Board**
- [ ] Review all attachments in the left panel
- [ ] If issue: click **Request Re-Upload** → type message
- [ ] When all clear: click **Mark as Ready for Delivery**

---

## 📌 Quick Reference — Delivery Clerk Checklist

- [ ] Student arrives at CoE Counter
- [ ] Open **CoE → Delivery Desk**
- [ ] Search by Tracking ID or scan QR
- [ ] Identity verification pop-up appears — confirm student matches
- [ ] Ask student for the 6-digit OTP from their SMS
- [ ] Enter OTP → if correct, click **Mark as Delivered**
- [ ] System logs delivery with your name, time, and OTP confirmation
