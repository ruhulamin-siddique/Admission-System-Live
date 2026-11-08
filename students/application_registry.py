"""
Application Registry: Defines all 15 official BAUST student admission application formats,
their bilingual metadata, letterhead recipient configuration, body templates, and dynamic fields schema.
"""

from students.models import AdmissionApplicationType

APPLICATION_DEFINITIONS = [
    {
        "code": "scholarship_admission",
        "order": 1,
        "title_en": "Application for Scholarship at the time of Admission",
        "title_bn": "ভর্তিকালীন বৃত্তির জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": False,
        "subject": "Application for Scholarship at the time of Admission.",
        "body_template": (
            "With due respect and humble submission, I would like to state that I have taken admission "
            "in the Department of {{ department }} at BAUST in Batch {{ batch|default:'N/A' }}. "
            "I obtained {{ ssc_result }} in SSC and {{ hsc_result }} in HSC examination. "
            "My father's profession is {{ father_profession }}. Due to financial constraints, it is difficult "
            "for my family to bear the full educational expenses. Therefore, I humbly request a scholarship/financial waiver."
        ),
        "fields_schema": [
            {"name": "program", "label_en": "Program / Degree", "label_bn": "প্রোগ্রাম / ডিগ্রি", "type": "text", "required": True, "col_class": "col-md-6"},
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": False, "col_class": "col-md-6"},
            {"name": "ssc_result", "label_en": "SSC Result (GPA or Division)", "label_bn": "এসএসসি ফলাফল (জিপিএ / বিভাগ)", "type": "text", "placeholder": "e.g. GPA 5.00 or 1st Division", "required": True, "col_class": "col-md-4"},
            {"name": "hsc_result", "label_en": "HSC Result (GPA or Division)", "label_bn": "এইচএসসি ফলাফল (জিপিএ / বিভাগ)", "type": "text", "placeholder": "e.g. GPA 5.00 or 1st Division", "required": True, "col_class": "col-md-4"},
            {"name": "father_profession", "label_en": "Father's / Guardian's Profession", "label_bn": "পিতা / অভিভাবকের পেশা", "type": "text", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "two_installments",
        "order": 2,
        "title_en": "Application for Paying Semester Fees in Two Installments",
        "title_bn": "সেমিস্টার ফি দুই কিস্তিতে প্রদানের জন্য আবেদন",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for paying semester fee in two installments.",
        "body_template": (
            "With due respect and humble submission, I beg to state that I am a student of {{ department }}, "
            "Batch {{ batch }}, Semester {{ semester }}, Student ID: {{ student_id }}. "
            "My father/guardian is {{ father_profession }}. Due to temporary financial difficulties, "
            "it is not possible for my family to pay the entire semester fee at one time. "
            "I would like to pay the fee in two installments: 1st installment of Tk. {{ first_installment_tk }} "
            "immediately, and 2nd installment of Tk. {{ second_installment_tk }} by {{ second_installment_date }}."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "semester", "label_en": "Semester", "label_bn": "সেমিস্টার", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "father_profession", "label_en": "Father's Profession", "label_bn": "পিতার পেশা", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "first_installment_tk", "label_en": "1st Installment (Tk)", "label_bn": "১ম কিস্তি (টাকা)", "type": "number", "inputmode": "decimal", "required": True, "col_class": "col-md-4"},
            {"name": "second_installment_tk", "label_en": "2nd Installment (Tk)", "label_bn": "২য় কিস্তি (টাকা)", "type": "number", "inputmode": "decimal", "required": True, "col_class": "col-md-4"},
            {"name": "second_installment_date", "label_en": "Proposed Date for 2nd Installment", "label_bn": "২য় কিস্তির প্রস্তাবিত তারিখ", "type": "date", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "army_waiver",
        "order": 3,
        "title_en": "Application for Army/Military Personnel Waiver (10%)",
        "title_bn": "সেনাবাহিনী/সামরিক কোটায় ১০% ফি মওকুফের আবেদন",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for waiver on tuition fees as child of Armed Forces Personnel (10%).",
        "body_template": (
            "With due respect and humble submission, I state that I am a student of {{ department }}, "
            "ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "My father {{ father_name }} is serving/retired in the {{ armed_force_branch }} (Rank: {{ father_rank }}, "
            "Badge No: {{ father_badge_no }}). As per BAUST policy, children of Armed Forces personnel are entitled "
            "to a 10% tuition fee waiver. I request you to kindly grant me this waiver."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "armed_force_branch", "label_en": "Armed Forces Branch", "label_bn": "বাহিনীর নাম", "type": "select", "options": ["Bangladesh Army", "Bangladesh Navy", "Bangladesh Air Force"], "required": True, "col_class": "col-md-6"},
            {"name": "father_name", "label_en": "Father's / Mother's Name", "label_bn": "পিতা / মাতার নাম", "type": "text", "required": True, "col_class": "col-md-6"},
            {"name": "father_rank", "label_en": "Rank / Designation", "label_bn": "পদবি", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "father_badge_no", "label_en": "Army No / Badge No / P No", "label_bn": "আর্মি নং / ব্যাজ নং / পি নং", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "father_phone", "label_en": "Parent's Phone Number", "label_bn": "পিতা/মাতার মোবাইল নম্বর", "type": "text", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "direct_admission",
        "order": 4,
        "title_en": "Application for Direct Admission",
        "title_bn": "সরাসরি ভর্তির জন্য আবেদনপত্র",
        "addressed_to": "Chairman, Admission Committee",
        "through_dept_head": True,
        "subject": "Application for Direct Admission in {{ department }}.",
        "body_template": (
            "With due respect and humble submission, I would like to inform you that I wish to take direct admission "
            "in the Department of {{ department }} at BAUST. I completed SSC with {{ ssc_gpa }} and HSC with {{ hsc_gpa }} "
            "(Total/Combined: {{ total_cgpa }}). I fulfill all the academic eligibility criteria specified by the university. "
            "I kindly request your approval for my direct admission."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": False, "col_class": "col-md-4"},
            {"name": "semester", "label_en": "Semester", "label_bn": "সেমিস্টার", "type": "text", "required": False, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": False, "col_class": "col-md-4"},
            {"name": "ssc_gpa", "label_en": "SSC Result (GPA / Division)", "label_bn": "এসএসসি ফলাফল (জিপিএ / বিভাগ)", "type": "text", "placeholder": "e.g. GPA 5.00 or 1st Division", "required": True, "col_class": "col-md-4"},
            {"name": "hsc_gpa", "label_en": "HSC Result (GPA / Division)", "label_bn": "এইচএসসি ফলাফল (জিপিএ / বিভাগ)", "type": "text", "placeholder": "e.g. GPA 5.00 or 1st Division", "required": True, "col_class": "col-md-4"},
            {"name": "total_cgpa", "label_en": "Combined / Total Result", "label_bn": "মোট ফলাফল", "type": "text", "placeholder": "e.g. 10.00 or 1st Div", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "studentship_certificate",
        "order": 5,
        "title_en": "Application for Studentship Certificate",
        "title_bn": "ছাত্রত্ব সনদের (Studentship Certificate) জন্য আবেদন",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Studentship Certificate.",
        "body_template": (
            "With due respect and humble submission, I state that I am a regular student of {{ department }}, "
            "ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "I require an official Studentship Certificate for the purpose of {{ reason }}. "
            "{% if reason_detail %}Details: {{ reason_detail }}{% endif %} "
            "My father's name is {{ father_name_capital }} and mother's name is {{ mother_name_capital }}. "
            "I therefore pray and hope that you would kindly issue me a Studentship Certificate."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "reason", "label_en": "Purpose / Reason", "label_bn": "উদ্দেশ্য / কারণ", "type": "chips", "options": ["Govt Scholarship", "Bank Account", "Passport / Visa", "National ID / Voter", "Personal / Family"], "required": True, "col_class": "col-md-6"},
            {"name": "reason_detail", "label_en": "Additional Details (Optional)", "label_bn": "অতিরিক্ত বিবরণ (ঐচ্ছিক)", "type": "text", "required": False, "col_class": "col-md-6"},
            {"name": "sex", "label_en": "Sex / Gender", "label_bn": "লিঙ্গ", "type": "select", "options": ["Male", "Female", "Other"], "required": True, "col_class": "col-md-4"},
            {"name": "father_name_capital", "label_en": "Father's Name (in Capital Letters)", "label_bn": "পিতার নাম (ইংরেজি বড় অক্ষরে)", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "mother_name_capital", "label_en": "Mother's Name (in Capital Letters)", "label_bn": "মাতার নাম (ইংরেজি বড় অক্ষরে)", "type": "text", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "dept_change",
        "order": 6,
        "title_en": "Application for Department / Program Change",
        "title_bn": "বিভাগ / প্রোগ্রাম পরিবর্তনের জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Department Change from {{ department }} to {{ target_dept }}.",
        "body_template": (
            "With due respect, I beg to state that I was admitted to the Department of {{ department }}, "
            "Student ID: {{ student_id }}, Batch: {{ batch }}. However, based on my academic interests and career goals, "
            "I earnestly desire to change my department to {{ target_dept }}. "
            "I have obtained my guardian's full consent for this change. I pray that you will kindly allow my department change."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "target_dept", "label_en": "Target Department Desired", "label_bn": "আকাঙ্ক্ষিত নতুন বিভাগ", "type": "select", "options": ["CSE", "EEE", "ME", "IPE", "CE", "DBA", "English", "AIS"], "required": True, "col_class": "col-md-6"},
            {"name": "reason", "label_en": "Reason for Change", "label_bn": "পরিবর্তনের কারণ", "type": "textarea", "required": False, "col_class": "col-md-6"},
        ]
    },
    {
        "code": "drop_semester",
        "order": 7,
        "title_en": "Application for Dropping Semester",
        "title_bn": "সেমিস্টার ড্রপ / স্থগিতের জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Dropping Semester.",
        "body_template": (
            "With due respect and humble submission, I state that I am a student of {{ department }}, "
            "ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "Due to unavoidable circumstances ({{ reason }}), I am unable to continue my academic studies "
            "in the current semester. Reason details: {{ reason_detail|default:'As explained' }}. "
            "Therefore, I humbly request you to kindly grant me permission to drop the current semester."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "sex", "label_en": "Sex / Gender", "label_bn": "লিঙ্গ", "type": "select", "options": ["Male", "Female", "Other"], "required": True, "col_class": "col-md-4"},
            {"name": "reason", "label_en": "Primary Reason", "label_bn": "প্রধান কারণ", "type": "chips", "options": ["Personal", "Family Crisis", "Sickness / Medical", "Financial"], "required": True, "col_class": "col-md-4"},
            {"name": "reason_detail", "label_en": "Reason Explanation", "label_bn": "কারণের বিস্তারিত", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "father_mother_name_capital", "label_en": "Father/Mother's Name (Capital)", "label_bn": "পিতা/মাতার নাম (ইংরেজি বড় অক্ষরে)", "type": "text", "required": True, "col_class": "col-md-12"},
        ]
    },
    {
        "code": "remission_tuition_fees",
        "order": 8,
        "title_en": "Application for Remission of Tuition Fees",
        "title_bn": "বকেয়া টিউশন ফি মওকুফের জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Remission of Tuition Fees.",
        "body_template": (
            "With due respect, I state that I am a regular student of {{ department }}, Student ID: {{ student_id }}, "
            "Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. My father's occupation is {{ father_profession }}. "
            "Presently, my total dues amount to Tk. {{ dues_amount }}. Due to extreme financial hardship ({{ financial_hardship_reason }}), "
            "my family cannot clear the full amount without institutional concession. I humbly request a remission of my fees."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "father_profession", "label_en": "Father's Occupation", "label_bn": "পিতার পেশা", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "dues_amount", "label_en": "Total Dues (Tk)", "label_bn": "মোট বকেয়ার পরিমাণ (টাকা)", "type": "number", "inputmode": "decimal", "required": True, "col_class": "col-md-4"},
            {"name": "financial_hardship_reason", "label_en": "Reason for Hardship", "label_bn": "আর্থিক অস্বচ্ছলতার কারণ", "type": "text", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "sibling_waiver",
        "order": 9,
        "title_en": "Application for Sibling Waiver (20%)",
        "title_bn": "সহোদর ভাই/বোন (Sibling) ২০% ওয়েভারের আবেদন",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Sibling Tuition Fee Waiver (20%).",
        "body_template": (
            "With due respect and humble submission, I state that I am a student of {{ department }}, "
            "Student ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "My sibling {{ sibling_name }} is also a regular student at BAUST in the Department of {{ sibling_dept }}, "
            "Student ID: {{ sibling_id }}, Batch: {{ sibling_batch }}. "
            "As per university rules, siblings studying concurrently at BAUST are eligible for a 20% waiver on tuition fees. "
            "I therefore pray that you will kindly sanction the 20% sibling waiver for me."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "sibling_id", "label_en": "Sibling's Student ID", "label_bn": "সহোদর ভাই/বোনের আইডি", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "sibling_name", "label_en": "Sibling's Full Name", "label_bn": "সহোদর ভাই/বোনের নাম", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "sibling_dept", "label_en": "Sibling's Department", "label_bn": "সহোদরের বিভাগ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "sibling_batch", "label_en": "Sibling's Batch", "label_bn": "সহোদরের ব্যাচ", "type": "text", "required": False, "col_class": "col-md-4"},
            {"name": "sibling_level", "label_en": "Sibling's Level", "label_bn": "সহোদরের লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": False, "col_class": "col-md-4"},
            {"name": "sibling_term", "label_en": "Sibling's Term", "label_bn": "সহোদরের টার্ম", "type": "select", "options": ["I", "II"], "required": False, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "withdraw_academic_papers",
        "order": 10,
        "title_en": "Application for Withdrawing Academic Papers (Temporarily)",
        "title_bn": "মূল সনদ/কাগজপত্র সাময়িক উত্তোলনের জন্য আবেদন",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for temporarily withdrawing original academic certificates/papers.",
        "body_template": (
            "With due respect, I state that I am a student of {{ department }}, ID: {{ student_id }}, "
            "Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "I urgently need to withdraw my original academic certificates ({{ papers_list|default:'Original SSC/HSC certificates' }}) "
            "temporarily for {{ duration_days }} for the purpose of {{ withdraw_reason }}. "
            "I give my solemn undertaking that I will resubmit all papers to the Admission Office by {{ resubmit_date }}. "
            "I pray that you will kindly permit the temporary withdrawal."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "withdraw_reason", "label_en": "Reason for Withdrawal", "label_bn": "উত্তোলনের কারণ", "type": "chips", "options": ["Family / Visa / Passport", "Name Correction in Board", "Personal / Official Verification"], "required": True, "col_class": "col-md-6"},
            {"name": "papers_list", "label_en": "Papers to Withdraw", "label_bn": "কাগজপত্রের বিবরণ", "type": "text", "required": True, "col_class": "col-md-6"},
            {"name": "duration_days", "label_en": "Duration", "label_bn": "সময়সীমা", "type": "chips", "options": ["7 Days", "15 Days", "30 Days"], "required": True, "col_class": "col-md-6"},
            {"name": "resubmit_date", "label_en": "Commitment Date to Resubmit", "label_bn": "পুনরায় জমা দেওয়ার প্রতিশ্রুতি তারিখ", "type": "date", "required": True, "col_class": "col-md-6"},
        ]
    },
    {
        "code": "admission_cancel",
        "order": 11,
        "title_en": "Application for Admission Cancellation",
        "title_bn": "ভর্তি বাতিলের জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Cancellation of Admission and Return of Original Papers.",
        "body_template": (
            "With due respect and humble submission, I state that I was admitted to the Department of {{ department }}, "
            "Student ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "Due to {{ cancel_reason }} (Details: {{ reason_detail }}), I am unable to continue my academic studies at BAUST. "
            "I have obtained complete clearance and my guardian has consented to this decision. "
            "I therefore pray that you will kindly cancel my admission and return my original academic papers."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "cancel_reason", "label_en": "Primary Reason", "label_bn": "প্রধান কারণ", "type": "chips", "options": ["Personal", "Family Affairs", "Migration to Public University", "Financial Inability", "Health / Sickness"], "required": True, "col_class": "col-md-6"},
            {"name": "reason_detail", "label_en": "Reason Details", "label_bn": "কারণের বিস্তারিত", "type": "textarea", "required": True, "col_class": "col-md-6"},
        ]
    },
    {
        "code": "hall_cancel",
        "order": 12,
        "title_en": "Application for Cancellation of Hall Seat / Mess",
        "title_bn": "হল সিট / মেস বাতিলের জন্য আবেদনপত্র",
        "addressed_to": "The Hall Provost",
        "through_dept_head": False,
        "subject": "Application for Cancellation of Hall Seat in {{ hall_name }}.",
        "body_template": (
            "With due respect, I state that I am a residential student of {{ hall_name }}, Department of {{ department }}, "
            "ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "Due to {{ cancellation_reason|default:'personal and private accommodation arrangements' }}, "
            "I wish to cancel my allocated hall seat with effect from {{ effective_date }}. "
            "I have cleared all hall dues up to date. I kindly pray that you will approve my hall seat cancellation."
        ),
        "fields_schema": [
            {"name": "hall_name", "label_en": "Residential Hall", "label_bn": "আবাসিক হল", "type": "select", "options": ["Dr. Zikrul Haque Hall", "Abbas Uddin Hall", "Taramon Bibi Hall"], "required": True, "col_class": "col-md-4"},
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "effective_date", "label_en": "Effective Cancellation Date", "label_bn": "বাতিলের কার্যকর তারিখ", "type": "date", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "cancellation_reason", "label_en": "Reason for Hall Release", "label_bn": "হল ছাড়ার কারণ", "type": "text", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "seat_in_hostel",
        "order": 13,
        "title_en": "Application for Allotment of Seat in Hostel/Hall",
        "title_bn": "হোস্টেল / হলে সিট বরাদ্দের জন্য আবেদনপত্র",
        "addressed_to": "The Hall Provost",
        "through_dept_head": False,
        "subject": "Application for Allotment of Residential Seat in {{ hall_name }}.",
        "body_template": (
            "With due respect and humble submission, I state that I am a student of {{ department }}, "
            "Student ID: {{ student_id }}, Batch: {{ batch }}, Level: {{ level }}, Term: {{ term }}. "
            "My home town/permanent residence is located far from the university ({{ permanent_address }}). "
            "It is extremely arduous and time-consuming for me to commute daily. "
            "I therefore pray that you would kindly allot me a residential seat in {{ hall_name }}."
        ),
        "fields_schema": [
            {"name": "hall_name", "label_en": "Desired Hall", "label_bn": "কাঙ্ক্ষিত হল", "type": "select", "options": ["Dr. Zikrul Haque Hall", "Abbas Uddin Hall", "Taramon Bibi Hall"], "required": True, "col_class": "col-md-4"},
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "guardian_name", "label_en": "Guardian's Name", "label_bn": "অভিভাবকের নাম", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": True, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": True, "col_class": "col-md-4"},
            {"name": "guardian_contact", "label_en": "Guardian's Contact No", "label_bn": "অভিভাবকের যোগাযোগ নং", "type": "text", "required": True, "col_class": "col-md-4"},
            {"name": "permanent_address", "label_en": "Permanent Home District / Address", "label_bn": "স্থায়ী জেলা / ঠিকানা", "type": "text", "required": True, "col_class": "col-md-12"},
        ]
    },
    {
        "code": "submitted_papers",
        "order": 14,
        "title_en": "Application for Submitted Academic Papers / Provisional Admission",
        "title_bn": "মূল কাগজপত্র জমা দান / সাময়িক ভর্তির অঙ্গীকারপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": False,
        "subject": "Application for Submitting Academic Papers and Regularizing Provisional Admission.",
        "body_template": (
            "With due respect, I state that I was provisionally admitted to the Department of {{ department }}, "
            "Batch: {{ batch|default:'N/A' }}, Student ID: {{ student_id|default:'Provisional' }}. "
            "At the time of admission, the following academic document(s) were pending: {{ missing_papers_list }}. "
            "Today, on {{ submit_date }}, I am formally submitting the required original documents to complete my admission file. "
            "I request you to kindly accept the papers and regularize my admission record."
        ),
        "fields_schema": [
            {"name": "batch", "label_en": "Batch", "label_bn": "ব্যাচ", "type": "text", "required": False, "col_class": "col-md-4"},
            {"name": "level", "label_en": "Level", "label_bn": "লেভেল", "type": "select", "options": ["1", "2", "3", "4"], "required": False, "col_class": "col-md-4"},
            {"name": "term", "label_en": "Term", "label_bn": "টার্ম", "type": "select", "options": ["I", "II"], "required": False, "col_class": "col-md-4"},
            {"name": "missing_papers_list", "label_en": "Submitted Papers List", "label_bn": "জমা দেওয়া কাগজপত্রের তালিকা", "type": "text", "required": True, "col_class": "col-md-8"},
            {"name": "submit_date", "label_en": "Date of Submission", "label_bn": "জমা দেওয়ার তারিখ", "type": "date", "required": True, "col_class": "col-md-4"},
        ]
    },
    {
        "code": "credit_transfer",
        "order": 15,
        "title_en": "Application for Credit Transfer / Course Exemption",
        "title_bn": "ক্রেডিট ট্রান্সফার / কোর্স মওকুফের জন্য আবেদনপত্র",
        "addressed_to": "The Registrar",
        "through_dept_head": True,
        "subject": "Application for Credit Transfer and Course Exemption in {{ department }}.",
        "body_template": (
            "With due respect and humble submission, I state that I was a student at {{ prev_university }} in {{ prev_program }}, "
            "where I completed {{ credits_completed }} credit hours with satisfactory academic standing. "
            "Due to {{ transfer_reason }}, I wish to transfer to BAUST and enroll in the Department of {{ department }}. "
            "I submit herewith my official academic transcripts and course syllabi for evaluation. "
            "I therefore pray that you will kindly allow credit transfer and course exemptions as applicable."
        ),
        "fields_schema": [
            {"name": "prev_university", "label_en": "Previous University / Institute", "label_bn": "পূর্ববর্তী বিশ্ববিদ্যালয় / প্রতিষ্ঠান", "type": "text", "required": True, "col_class": "col-md-6"},
            {"name": "prev_program", "label_en": "Previous Program / Department", "label_bn": "পূর্ববর্তী বিভাগ / প্রোগ্রাম", "type": "text", "required": True, "col_class": "col-md-6"},
            {"name": "credits_completed", "label_en": "Completed Credits", "label_bn": "সম্পন্নকৃত ক্রেডিট", "type": "number", "inputmode": "decimal", "required": True, "col_class": "col-md-4"},
            {"name": "transfer_reason", "label_en": "Reason for Transfer", "label_bn": "স্থানান্তরের কারণ", "type": "chips", "options": ["Personal Choice", "Health Issue", "Family Relocation / Father Transfer", "Better Academic Environment"], "required": True, "col_class": "col-md-8"},
        ]
    },
]


def seed_admission_application_types():
    """Seeds or updates all 15 default admission application types in the database."""
    created_count = 0
    updated_count = 0

    for item in APPLICATION_DEFINITIONS:
        obj, created = AdmissionApplicationType.objects.update_or_create(
            code=item["code"],
            defaults={
                "order": item["order"],
                "title_en": item["title_en"],
                "title_bn": item["title_bn"],
                "addressed_to": item["addressed_to"],
                "through_dept_head": item["through_dept_head"],
                "subject": item["subject"],
                "body_template": item["body_template"],
                "fields_schema": item["fields_schema"],
                "is_active": True,
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count
