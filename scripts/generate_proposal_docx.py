import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    """Sets background color for a table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets padding/margins for a table cell in dxa (1 pt = 20 dxa)."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def set_cell_border(cell, **kwargs):
    """
    Set cell borders.
    kwargs: top, bottom, left, right
    values: dict(sz=12, val='single', color='1B365D')
    """
    tcPr = cell._element.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            b_element = parse_xml(f'<w:{edge} {nsdecls("w")} w:val="{edge_data.get("val", "single")}" w:sz="{edge_data.get("sz", 4)}" w:space="0" w:color="{edge_data.get("color", "auto")}"/>')
            tcBorders.append(b_element)
    tcPr.append(tcBorders)

def create_report():
    doc = Document()
    
    # Configure Page Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)

    # Color Palette
    PRIMARY_COLOR = RGBColor(27, 54, 93)      # Deep Navy #1B365D
    SECONDARY_COLOR = RGBColor(41, 128, 185)  # Soft Blue #2980B9
    DARK_TEXT = RGBColor(44, 62, 80)          # Slate Charcoal #2C3E50
    MUTED_TEXT = RGBColor(100, 116, 139)      # Slate Grey #64748B
    HIGHLIGHT_BG = "F1F5F9"                   # Light Slate Fill
    HEADER_BG = "1B365D"                      # Navy Header Fill
    ALERT_BG = "FEF3C7"                       # Soft Gold/Amber Fill
    ALERT_BORDER = "D97706"

    # Set normal style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = DARK_TEXT
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # DOCUMENT COVER / HEADER
    # -------------------------------------------------------------
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(10)
    p_title.paragraph_format.space_after = Pt(2)
    run_title = p_title.add_run("BANGLADESH ARMY UNIVERSITY OF SCIENCE AND TECHNOLOGY (BAUST)")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(13)
    run_title.font.bold = True
    run_title.font.color.rgb = SECONDARY_COLOR

    p_main = doc.add_paragraph()
    p_main.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_main.paragraph_format.space_after = Pt(4)
    run_main = p_main.add_run("STRATEGIC PROJECT PROPOSAL & CONCEPT PAPER")
    run_main.font.name = 'Calibri'
    run_main.font.size = Pt(20)
    run_main.font.bold = True
    run_main.font.color.rgb = PRIMARY_COLOR

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(18)
    run_sub = p_sub.add_run("University Psychological Counseling & Student Wellbeing Management System")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(14)
    run_sub.font.italic = True
    run_sub.font.color.rgb = DARK_TEXT

    # Metadata Card (Table)
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    
    meta_data = [
        ("Target Leadership", "Vice-Chancellor, Registrar, Dean of Student Affairs, Proctorial Body, Chief Medical Officer"),
        ("Project Champion", "University Psychologist & Student Counseling Center"),
        ("System Architecture & Dev", "Ruhulamin Siddique (System Architect & Administrator)"),
        ("Project Status & Target", "Proposed Extension to Integrated University Admission & Student Life Cycle Suite"),
    ]

    for i, (k, v) in enumerate(meta_data):
        row = meta_table.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        
        set_cell_background(c0, "E2E8F0")
        set_cell_background(c1, "F8FAFC")
        set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
        set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(k)
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = PRIMARY_COLOR
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(v)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # HELPER FUNCTIONS FOR SECTIONS
    # -------------------------------------------------------------
    def add_section_header(title, level=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(title)
        run.font.name = 'Calibri'
        run.font.bold = True
        if level == 1:
            run.font.size = Pt(15)
            run.font.color.rgb = PRIMARY_COLOR
            # Add subtle underline or border effect
        elif level == 2:
            run.font.size = Pt(13)
            run.font.color.rgb = SECONDARY_COLOR
        else:
            run.font.size = Pt(11.5)
            run.font.bold = True
            run.font.color.rgb = PRIMARY_COLOR
        return p

    def add_callout_box(text, title="CRITICAL POLICY NOTE", bg_color=HIGHLIGHT_BG, border_color="1B365D"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        set_cell_border(cell, left={"val": "single", "sz": 24, "color": border_color},
                              top={"val": "none"}, right={"val": "none"}, bottom={"val": "none"})
        
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(4)
        r_title = p.add_run(f"🔒 {title}\n")
        r_title.font.bold = True
        r_title.font.size = Pt(10.5)
        r_title.font.color.rgb = PRIMARY_COLOR
        
        r_body = p.add_run(text)
        r_body.font.size = Pt(10)
        r_body.font.italic = True
        r_body.font.color.rgb = DARK_TEXT
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE SUMMARY
    # -------------------------------------------------------------
    add_section_header("1. Executive Summary & Strategic Rationale", 1)
    
    p = doc.add_paragraph(
        "University life brings transformative intellectual and personal growth, but it also exposes students to "
        "heightened academic rigor, competitive pressure, social adjustments, residential hall life away from home, "
        "and career uncertainties. In contemporary higher education, mental health support is no longer a secondary luxury; "
        "it is a cornerstone of student retention, institutional reputation, academic excellence, and campus safety."
    )
    
    p = doc.add_paragraph(
        "The proposed Psychological Counseling & Student Wellbeing Module is a specialized, clinical-grade digital extension "
        "to the existing University Admission & Student Life Cycle Management Suite. Designed from a non-technical, human-centric "
        "standpoint, this system equips the University Psychologist and Counseling Center with modern case management tools, "
        "standardized psychometric screenings, and crisis triage protocols, while ensuring that student confidentiality is guarded "
        "with the highest clinical and technological standards."
    )

    add_callout_box(
        "The primary objective of this module is to transition the university's mental health support from an ad-hoc, "
        "paper-bound service into a proactive, confidential, and scientifically structured student wellbeing ecosystem.",
        title="CORE MISSION STATEMENT"
    )

    # -------------------------------------------------------------
    # SECTION 2: STUDENT FACILITIES & SERVICES OFFERED
    # -------------------------------------------------------------
    add_section_header("2. Student Facilities & Core Services Offered", 1)
    
    doc.add_paragraph(
        "The module introduces structured, dignified, and accessible touchpoints for students seeking psychological, "
        "emotional, or academic guidance:"
    )

    services = [
        ("Dignified & Discreet Appointment Scheduling", 
         "Students can privately book counseling sessions online through their portal, selecting available dates, time slots, and meeting modes (In-Person Office Session or Confidential Online Tele-counseling). This eliminates the awkwardness of standing in waiting lines or physical appointment logbooks."),
        
        ("Self-Triage & Urgent Crisis Walk-in", 
         "When requesting an appointment, students can indicate urgency level (Routine, Priority, or Acute Crisis). Severe flags (e.g., severe panic, acute distress) immediately alert the psychologist for priority intervention."),
        
        ("Standardized Scientific Psychological Assessments", 
         "Integrated interactive clinical screening tools (PHQ-9 for Depression, GAD-7 for Anxiety, and DASS-21 for Stress) allow students and psychologists to evaluate symptoms scientifically, track progress over time, and visualize healing."),
        
        ("Dedicated Support Categories", 
         "Specialized therapy tracks tailored for university challenges: (a) Academic Stress & Exam Anxiety, (b) Hall Life & Homesickness, (c) Relationship & Family Dynamics, (d) Grief & Trauma, (e) Career & Self-Confidence, and (f) Habit / Substance Intervention."),
        
        ("Confidential Automated SMS Notifications", 
         "Discreet SMS alerts remind students of their upcoming session time and room number without displaying any sensitive clinical terminology on their phone screen."),
        
        ("Campus Wellness & Preventive Mental Health Campaigns", 
         "Management of university-wide workshops, meditation sessions, anti-bullying drives, and stress management seminars prior to Midterm and Final examinations.")
    ]

    for title, desc in services:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(4)
        run_bullet = p.add_run(f"•  {title}: ")
        run_bullet.font.bold = True
        run_bullet.font.color.rgb = PRIMARY_COLOR
        run_desc = p.add_run(desc)

    # -------------------------------------------------------------
    # SECTION 3: HOW EXISTING DATA HELPS COUNSELING
    # -------------------------------------------------------------
    add_section_header("3. Leveraging Existing University Student Data", 1)
    
    doc.add_paragraph(
        "One of the greatest operational strengths of building this module directly inside our existing Admission & Student Management "
        "Suite is that the psychologist does not have to collect repetitive demographic or academic data. The system automatically "
        "and securely links key profile parameters to provide vital clinical context:"
    )

    data_table = doc.add_table(rows=1, cols=3)
    data_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    data_table.autofit = False

    headers = ["Existing Data Field", "Clinical Context & Practical Value in Counseling", "Benefit to Student & Center"]
    hdr_row = data_table.rows[0]
    for idx, text in enumerate(headers):
        cell = hdr_row.cells[idx]
        set_cell_background(cell, HEADER_BG)
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    hdr_row.cells[0].width = Inches(1.8)
    hdr_row.cells[1].width = Inches(2.7)
    hdr_row.cells[2].width = Inches(2.0)

    existing_data_items = [
        ("Academic Program, Batch & Current Semester", 
         "Identifies critical academic transition phases (e.g. Level 1 Term 1 orientation shock vs. final-year thesis/capstone pressure). Helps counselor correlate stress with academic workload.", 
         "No need to re-enter academic history; contextualized guidance."),
        
        ("Residential Hall & Physical Room Status", 
         "Distinguishes residential hall boarders from day commuters. Vital for identifying hall adjustment issues, roommate conflicts, or midnight crisis escalations with Hall Provosts.", 
         "Immediate liaison with residential authorities during emergencies."),
        
        ("Home District, Division & Upazila", 
         "Provides geographic and cultural background. Helps counselor understand regional relocation stress, language transition, and homesickness severity.", 
         "Culturally sensitive, empathetic counseling."),
        
        ("Guardian & Emergency Contact Numbers", 
         "Instantly available verified phone numbers of parents/guardians and emergency contacts.", 
         "Crucial life-saving asset during acute psychiatric or self-harm crises."),
        
        ("Blood Group & Medical Profile", 
         "Readily available for immediate hospital transport or psychiatric medical referral (e.g., CMH / University Medical Center).", 
         "Zero delay during physical medical emergencies."),
        
        ("Special Quota Categories (Freedom Fighter, Military, July 2024 Joddha)", 
         "Recognizes unique psychosocial backgrounds, potential trauma history, or specialized scholarship/financial pressures.", 
         "Tailored psychological care without intrusive repetitive questioning.")
    ]

    for row_data in existing_data_items:
        row = data_table.add_row()
        for idx, val in enumerate(row_data):
            cell = row.cells[idx]
            cell.width = hdr_row.cells[idx].width
            bg = "F8FAFC" if len(data_table.rows) % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if idx == 0:
                r.font.bold = True
                r.font.color.rgb = PRIMARY_COLOR

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------
    # SECTION 4: NEW DATA FIELDS TO BE COLLECTED & PRESERVED
    # -------------------------------------------------------------
    add_section_header("4. New Clinical & Counseling Data to Collect & Preserve", 1)
    
    doc.add_paragraph(
        "To maintain professional psychiatric and counseling standards, the system introduces new, highly confidential data entities:"
    )

    new_data_categories = [
        ("A. Master Case File Information", [
            ("Case Identifier", "Unique confidential code (e.g., CASE-2026-0042) to de-identify records in public discussions."),
            ("Case Status", "Active, In-Progress, On-Hold, Completed/Discharged, or Externally Referred."),
            ("Risk Stratification", "Clinical assessment of risk: Low, Moderate, High, or Critical / Immediate Crisis."),
            ("Primary Presenting Concern", "Academic anxiety, depression, social adjustment, trauma, substance use, etc.")
        ]),
        ("B. Clinical Intake & Psychosocial History", [
            ("Symptom Duration & Triggers", "When the distress began and specific triggering life events."),
            ("Biological Sleep & Appetite Patterns", "Insomnia, hypersomnia, appetite loss (key biological indicators of depression)."),
            ("Family & Developmental History", "Family dynamics, past mental health history, parental loss or conflict."),
            ("Current Medication / Psychiatric History", "Any ongoing psychotropic medication or past therapy history.")
        ]),
        ("C. Standardized Psychometric Test Records", [
            ("PHQ-9 Depression Inventory", "Score 0–27 indicating severity (Minimal, Mild, Moderate, Moderately Severe, Severe)."),
            ("GAD-7 Anxiety Scale", "Score 0–21 measuring generalized anxiety and panic indicators."),
            ("DASS-21 Multi-Scale", "Holistic assessment separating Depression, Anxiety, and Stress dimensions."),
            ("Session-by-Session Progress Logs", "Longitudinal score charts showing whether symptoms are decreasing over time.")
        ]),
        ("D. Clinical Session Records (SOAP Notes)", [
            ("Subjective (S)", "Student's personal account of their emotions, thoughts, and recent struggles."),
            ("Objective (O)", "Psychologist's observations of affect, eye contact, body language, and speech pattern."),
            ("Assessment (A)", "Psychologist's professional diagnostic formulation and progress evaluation."),
            ("Plan (P)", "Agreed therapeutic homework (CBT exercises, sleep schedule, mindfulness) and next review date.")
        ]),
        ("E. Emergency Escalation & External Referral Records", [
            ("Suicide Risk Screening & Safety Contract", "Documented safety commitments and protective factors."),
            ("Medical & Hospital Referral Logs", "Formal records of referrals made to CMH, District Hospital, or Private Psychiatrists."),
            ("Institutional Referral Records", "Private notes submitted by Department Heads, Advisors, or Provosts requesting support for a student.")
        ])
    ]

    for cat_title, fields in new_data_categories:
        add_section_header(cat_title, 2)
        for fname, fdesc in fields:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_after = Pt(2)
            rf = p.add_run(f"•  {fname}: ")
            rf.font.bold = True
            rf.font.color.rgb = DARK_TEXT
            rd = p.add_run(fdesc)
            rd.font.size = Pt(10)

    # -------------------------------------------------------------
    # SECTION 5: SECURITY, CONFIDENTIALITY & ACCESS CONTROL
    # -------------------------------------------------------------
    add_section_header("5. Data Privacy, Strict Confidentiality & Multi-Tier Access Control", 1)
    
    doc.add_paragraph(
        "In psychological counseling, data confidentiality is not merely a technical requirement—it is a legal, ethical, "
        "and medical imperative. Students will only use the service if they trust that their deeply personal vulnerabilities "
        "will NEVER be seen by their course teachers, department heads, or peer students."
    )

    add_callout_box(
        "STRICT ETHICAL SEPARATION RULE: Academic and administrative staff (including Deans, HODs, and Course Teachers) "
        "have ZERO access to clinical therapy notes, diagnosis, or psychological screening scores. Clinical records are completely "
        "isolated from academic transcripts.",
        title="THE GOLDEN PRINCIPLE OF COUNSELING PRIVACY",
        bg_color="FEF3C7",
        border_color=ALERT_BORDER
    )

    # RBAC Matrix Table
    rbac_table = doc.add_table(rows=1, cols=4)
    rbac_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    rbac_table.autofit = False

    rbac_headers = ["User Role", "Booking / Referral", "Clinical Notes & Tests", "Macro Analytics"]
    for idx, text in enumerate(rbac_headers):
        cell = rbac_table.rows[0].cells[idx]
        set_cell_background(cell, HEADER_BG)
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    rbac_table.rows[0].cells[0].width = Inches(1.8)
    rbac_table.rows[0].cells[1].width = Inches(1.6)
    rbac_table.rows[0].cells[2].width = Inches(1.8)
    rbac_table.rows[0].cells[3].width = Inches(1.3)

    rbac_rows = [
        ("University Psychologist / Counselor", "Full Management", "Full Read/Write Access", "Full Access"),
        ("Student (Self)", "Book / View Own Appointments", "View Own Prescribed Exercises", "No Access"),
        ("Dept Advisor / Hall Provost", "Submit Referral Only", "NO ACCESS (Strictly Blocked)", "No Access"),
        ("General Faculty / Academic Staff", "NO ACCESS", "NO ACCESS (Strictly Blocked)", "No Access"),
        ("Vice-Chancellor / Higher Management", "High-Level Summaries", "NO ACCESS (Patient Privacy)", "Full De-Identified Reports"),
        ("Chief Medical Officer (CMH/Medical)", "Emergency Referral Liaison", "Medical Referral Notes Only", "Macro Health Stats")
    ]

    for rdata in rbac_rows:
        row = rbac_table.add_row()
        for idx, val in enumerate(rdata):
            cell = row.cells[idx]
            cell.width = rbac_table.rows[0].cells[idx].width
            bg = "F8FAFC" if len(rbac_table.rows) % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if idx == 0:
                r.font.bold = True
                r.font.color.rgb = PRIMARY_COLOR
            if "NO ACCESS" in val:
                r.font.color.rgb = RGBColor(185, 28, 28) # Red
                r.font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    doc.add_paragraph(
        "Technical Security Layers Implemented:"
    )
    security_bullets = [
        ("Cryptographic Database Shielding", "Session records and clinical notes are isolated in protected tables with granular object-level permission verification on every HTTP request."),
        ("Audit Logging & Tamper Trail", "Every single view, edit, or export of a case record generates an unalterable activity log capturing the exact User ID, timestamp, and IP address."),
        ("Discreet SMS Gateway Integration", "Appointment confirmation SMS messages use generic neutral phrasing (e.g. 'Session Confirmed at Center Room 204') so that casual observers cannot infer clinical details."),
        ("Pseudonymized Student Option", "For students dealing with high stigma (e.g., severe domestic trauma), the system allows assigning a confidential Case Token instead of displaying the student's name on physical doors or public lists.")
    ]
    for b_title, b_desc in security_bullets:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(3)
        rb = p.add_run(f"✔  {b_title}: ")
        rb.font.bold = True
        rb.font.color.rgb = PRIMARY_COLOR
        rd = p.add_run(b_desc)
        rd.font.size = Pt(10)

    # -------------------------------------------------------------
    # SECTION 6: INSTITUTIONAL BENEFITS & ROI FOR THE UNIVERSITY
    # -------------------------------------------------------------
    add_section_header("6. Strategic Value & Institutional Benefits for University Leadership", 1)
    
    doc.add_paragraph(
        "Implementing a digital psychological counseling ecosystem provides quantifiable institutional dividends across several key dimensions:"
    )

    benefits = [
        ("1. Proactive Dropout Prevention & Revenue Retention",
         "Mental health breakdown is a leading cause of sudden semester drops and permanent university dropouts. Early counseling intervention retains students who might otherwise withdraw, directly preserving institutional tuition revenue."),
        
        ("2. Life-Saving Crisis Intervention & Risk Mitigation",
         "A structured emergency escalation protocol ensures immediate, coordinated response to suicidal ideation, self-harm, or severe acute trauma, mitigating tragic campus incidents and legal/reputational liabilities."),
        
        ("3. UGC & International Accreditation Compliance (BAC / Washington Accord)",
         "National and international accreditation bodies (including Bangladesh Accreditation Council, UGC, and BAETE/IEB) heavily emphasize institutional student support, mental wellbeing facilities, and holistic campus care. This system produces verifiable accreditation evidence."),
        
        ("4. Enhanced Academic Performance & Reduced Exam Failures",
         "Students with managed stress, overcome exam phobia, and stabilized sleep patterns consistently achieve higher GPAs, lower backlog course rates, and superior graduation timeliness."),
        
        ("5. Residential Hall Harmony & Discipline",
         "Hall Provosts gain a formal, constructive referral avenue for students exhibiting severe behavioral isolation, roommate friction, or emotional distress, preventing hall violence and disciplinary crises."),
        
        ("6. Evidence-Based University Policy (Anonymized Macro Intelligence)",
         "University leadership receives aggregated, de-identified quarterly reports revealing when and where stress peaks (e.g., specific batch pressure, pre-exam panic), enabling proactive scheduling of academic calendars and mental health weeks.")
    ]

    for b_title, b_desc in benefits:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(4)
        rb = p.add_run(f"★  {b_title}\n")
        rb.font.bold = True
        rb.font.color.rgb = PRIMARY_COLOR
        rd = p.add_run(b_desc)
        rd.font.size = Pt(10)

    # -------------------------------------------------------------
    # SECTION 7: ADDITIONAL INNOVATIVE FEATURES
    # -------------------------------------------------------------
    add_section_header("7. Value-Added Features Beyond Standard Counseling", 1)
    
    doc.add_paragraph(
        "To build a truly progressive and world-class student support center, the following advanced features are proposed:"
    )

    extra_features = [
        ("Student Peer Wellbeing Ambassadors", 
         "A program where trained senior student volunteers in residential halls can flag early warning signs of distress in peers and guide them to book a session through the portal."),
        
        ("Digital Mental Health Self-Help Vault", 
         "A resource library within the portal containing audio guided breathing exercises, sleep hygiene checklists, exam anxiety management guides, and downloadable cognitive journaling worksheets."),
        
        ("Anonymous 'Ask a Psychologist' Q&A Forum", 
         "A moderated digital bulletin board where students can post anonymous general mental health questions, and the university psychologist posts public educational answers for all students to learn from."),
        
        ("Post-Session Student Experience Rating", 
         "After completing a therapy cycle, students receive an optional, 100% anonymous 3-question survey evaluating how supported they felt. This ensures continuous quality improvement of the counseling center.")
    ]

    for ef_title, ef_desc in extra_features:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(4)
        re = p.add_run(f"❖  {ef_title}: ")
        re.font.bold = True
        re.font.color.rgb = SECONDARY_COLOR
        rd = p.add_run(ef_desc)
        rd.font.size = Pt(10)

    # -------------------------------------------------------------
    # SECTION 8: IMPLEMENTATION ROADMAP & ROLLOUT PHASES
    # -------------------------------------------------------------
    add_section_header("8. Phased Implementation Roadmap & Rollout Plan", 1)
    
    doc.add_paragraph(
        "The project will be executed in five structured phases to ensure zero disruption to current university operations:"
    )

    roadmap_table = doc.add_table(rows=1, cols=3)
    roadmap_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    roadmap_table.autofit = False

    rm_headers = ["Phase & Timeline", "Key Milestones & Deliverables", "Stakeholders Involved"]
    for idx, text in enumerate(rm_headers):
        cell = roadmap_table.rows[0].cells[idx]
        set_cell_background(cell, HEADER_BG)
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        r.font.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    roadmap_table.rows[0].cells[0].width = Inches(1.8)
    roadmap_table.rows[0].cells[1].width = Inches(3.2)
    roadmap_table.rows[0].cells[2].width = Inches(1.5)

    roadmap_rows = [
        ("Phase 1: Architecture & RBAC Isolation\n(Weeks 1 – 2)", 
         "• Creation of 'counseling' Django app.\n• Strict DB schema setup for Case Files, SOAP Notes & Assessments.\n• Implementation of RBAC permission locks.", 
         "System Architect, Lead Developer"),
        
        ("Phase 2: Psychologist Center & Appointments\n(Weeks 3 – 4)", 
         "• Counselor daily schedule management.\n• Student private booking interface.\n• Automated confidential SMS reminders integration.", 
         "University Psychologist, ICT Wing"),
        
        ("Phase 3: Clinical & Assessment Engine\n(Weeks 5 – 6)", 
         "• Interactive PHQ-9, GAD-7 & DASS-21 scoring engines.\n• Dynamic SOAP clinical note editor.\n• Student progress trend visual charts.", 
         "University Psychologist, Medical Team"),
        
        ("Phase 4: Emergency Protocols & Referrals\n(Weeks 7 – 8)", 
         "• High-risk emergency notification workflows.\n• External medical/psychiatrist referral tracking.\n• Faculty/Provost confidential referral pipeline.", 
         "Proctorial Body, Hall Provosts, Medical Center"),
        
        ("Phase 5: Pilot Testing & Campus Launch\n(Weeks 9 – 10)", 
         "• End-to-end security penetration & privacy testing.\n• Counselor onboarding & staff briefing.\n• Campus-wide mental health awareness orientation.", 
         "University Leadership, All Students")
    ]

    for rm in roadmap_rows:
        row = roadmap_table.add_row()
        for idx, val in enumerate(rm):
            cell = row.cells[idx]
            cell.width = roadmap_table.rows[0].cells[idx].width
            bg = "F8FAFC" if len(roadmap_table.rows) % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size = Pt(9)
            if idx == 0:
                r.font.bold = True
                r.font.color.rgb = PRIMARY_COLOR

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # SECTION 9: CONCLUSION & RECOMMENDATION
    # -------------------------------------------------------------
    add_section_header("9. Conclusion & Recommendation for Approval", 1)
    
    p = doc.add_paragraph(
        "The proposed University Psychological Counseling & Student Wellbeing System is a strategic investment in the "
        "human capital of our institution. By seamlessly uniting our existing student database with modern, secure, and "
        "clinically validated mental health workflows, BAUST / our University will lead by example as a compassionate, "
        "forward-thinking, and student-centered center of excellence."
    )
    
    p = doc.add_paragraph(
        "Approval is respectfully requested from University Leadership to proceed with Phase 1 development and technical setup."
    )

    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(24)
    p_sign.paragraph_format.keep_with_next = True
    r_sign = p_sign.add_run("Prepared & Submitted by:\n\n___________________________________\n")
    r_sign.font.bold = True
    r_name = p_sign.add_run("Ruhulamin Siddique\n")
    r_name.font.bold = True
    r_name.font.color.rgb = PRIMARY_COLOR
    r_role = p_sign.add_run("System Architect & Administrator\nBangladesh Army University of Science and Technology (BAUST)")
    r_role.font.size = Pt(9.5)
    r_role.font.color.rgb = MUTED_TEXT

    # Save the file
    output_path = os.path.join(os.path.dirname(__file__), "University_Psychological_Counseling_Module_Proposal.docx")
    doc.save(output_path)
    print(f"Document successfully created at: {output_path}")

if __name__ == "__main__":
    create_report()
