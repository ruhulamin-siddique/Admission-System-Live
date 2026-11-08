"""
counseling/utils.py
===================
Calculators, scale questions, SMS notification dispatches, and clinical utility helpers.
"""

from django.utils.translation import gettext_lazy as _
from core.utils import send_sms
from .models import CounselingSettings

# ============================================================================
# Standardized Psychological Scale Questionnaires
# ============================================================================

PHQ9_QUESTIONS = [
    {"id": "q1", "text": _("Little interest or pleasure in doing things?")},
    {"id": "q2", "text": _("Feeling down, depressed, or hopeless?")},
    {"id": "q3", "text": _("Trouble falling or staying asleep, or sleeping too much?")},
    {"id": "q4", "text": _("Feeling tired or having little energy?")},
    {"id": "q5", "text": _("Poor appetite or overeating?")},
    {"id": "q6", "text": _("Feeling bad about yourself — or that you are a failure or have let yourself or your family down?")},
    {"id": "q7", "text": _("Trouble concentrating on things, such as reading the newspaper or watching television?")},
    {"id": "q8", "text": _("Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual?")},
    {"id": "q9", "text": _("Thoughts that you would be better off dead, or of hurting yourself in some way?")},
]

PHQ9_OPTIONS = [
    {"val": 0, "label": _("Not at all"), "hint": "0"},
    {"val": 1, "label": _("Several days"), "hint": "1"},
    {"val": 2, "label": _("More than half the days"), "hint": "2"},
    {"val": 3, "label": _("Nearly every day"), "hint": "3"},
]

GAD7_QUESTIONS = [
    {"id": "q1", "text": _("Feeling nervous, anxious, or on edge?")},
    {"id": "q2", "text": _("Not being able to stop or control worrying?")},
    {"id": "q3", "text": _("Worrying too much about different things?")},
    {"id": "q4", "text": _("Trouble relaxing?")},
    {"id": "q5", "text": _("Being so restless that it is hard to sit still?")},
    {"id": "q6", "text": _("Becoming easily annoyed or irritable?")},
    {"id": "q7", "text": _("Feeling afraid, as if something awful might happen?")},
]

GAD7_OPTIONS = [
    {"val": 0, "label": _("Not at all"), "hint": "0"},
    {"val": 1, "label": _("Several days"), "hint": "1"},
    {"val": 2, "label": _("More than half the days"), "hint": "2"},
    {"val": 3, "label": _("Nearly every day"), "hint": "3"},
]

DASS21_QUESTIONS = [
    {"id": "q1",  "scale": "stress",     "text": _("I found it hard to wind down.")},
    {"id": "q2",  "scale": "anxiety",    "text": _("I was aware of dryness of my mouth.")},
    {"id": "q3",  "scale": "depression", "text": _("I couldn't seem to experience any positive feeling at all.")},
    {"id": "q4",  "scale": "anxiety",    "text": _("I experienced breathing difficulty (e.g. excessively rapid breathing, breathlessness in the absence of physical exertion).")},
    {"id": "q5",  "scale": "depression", "text": _("I found it difficult to work up the initiative to do things.")},
    {"id": "q6",  "scale": "stress",     "text": _("I tended to over-react to situations.")},
    {"id": "q7",  "scale": "anxiety",    "text": _("I experienced trembling (e.g. in the hands).")},
    {"id": "q8",  "scale": "stress",     "text": _("I felt that I was using a lot of nervous energy.")},
    {"id": "q9",  "scale": "anxiety",    "text": _("I was worried about situations in which I might panic and make a fool of myself.")},
    {"id": "q10", "scale": "depression", "text": _("I felt that I had nothing to look forward to.")},
    {"id": "q11", "scale": "stress",     "text": _("I found myself getting agitated.")},
    {"id": "q12", "scale": "stress",     "text": _("I found it difficult to relax.")},
    {"id": "q13", "scale": "depression", "text": _("I felt down-hearted and blue.")},
    {"id": "q14", "scale": "stress",     "text": _("I was intolerant of anything that kept me from getting on with what I was doing.")},
    {"id": "q15", "scale": "anxiety",    "text": _("I felt I was close to panic.")},
    {"id": "q16", "scale": "depression", "text": _("I was unable to become enthusiastic about anything.")},
    {"id": "q17", "scale": "depression", "text": _("I felt I wasn't worth much as a person.")},
    {"id": "q18", "scale": "stress",     "text": _("I felt that I was rather touchy.")},
    {"id": "q19", "scale": "anxiety",    "text": _("I was aware of the action of my heart in the absence of physical exertion (e.g. sense of heart rate increase, heart missing a beat).")},
    {"id": "q20", "scale": "anxiety",    "text": _("I felt scared without any good reason.")},
    {"id": "q21", "scale": "depression", "text": _("I felt that life was meaningless.")},
]

DASS21_OPTIONS = [
    {"val": 0, "label": _("Did not apply to me at all")},
    {"val": 1, "label": _("Applied to me to some degree, or some of the time")},
    {"val": 2, "label": _("Applied to me to a considerable degree or a good part of time")},
    {"val": 3, "label": _("Applied to me very much or most of the time")},
]

CLINICAL_SNIPPETS = {
    "subjective": [
        "Reports persistent insomnia (2-3 hrs sleep/night) for the past 2 weeks.",
        "Experiencing acute test anxiety, palpitations before examination halls.",
        "Reports severe homesickness and difficulty adjusting to residential hall mess/environment.",
        "Reports interpersonal friction with roommate; feeling socially isolated.",
        "Reports improved mood and better emotional stability since last session.",
    ],
    "objective": [
        "Affect: Anxious, tearful at times, speech rapid but coherent.",
        "Affect: Euthymic, well-groomed, good eye contact throughout session.",
        "Affect: Constricted, blunted, minimal eye contact, psychomotor retardation noted.",
        "Alert and oriented x3. Thought process logical and goal-directed.",
        "Demonstrated deep relaxation breathing technique effectively during session.",
    ],
    "assessment": [
        "Situational adjustment disorder with anxious mood secondary to academic transition.",
        "Moderate generalized anxiety disorder (GAD-7 score: 13), symptoms worsening prior to finals.",
        "Mild depressive episode with biological vegetative symptoms (insomnia, poor appetite).",
        "Significant symptom reduction observed compared to baseline intake.",
        "No acute suicidal ideation, intent, or plan expressed today. Safety contract active.",
    ],
    "plan": [
        "Taught Progressive Muscle Relaxation (PMR) and 4-7-8 breathing exercise for pre-sleep.",
        "Assigned cognitive journaling: Identify and reframe automatic negative thoughts (CBT).",
        "Advised strict sleep hygiene: Zero screens 1 hour before bed, fixed wake-up time.",
        "Recommended consultation with University Medical Officer for physical insomnia evaluation.",
        "Follow-up individual counseling session scheduled in 7 days.",
    ]
}


# ============================================================================
# Score Computation Engines
# ============================================================================

def calculate_phq9_score(responses: dict) -> dict:
    """
    Computes total PHQ-9 score (0-27) and clinical severity classification.
    """
    total = 0
    for i in range(1, 10):
        key = f"q{i}"
        val = responses.get(key, 0)
        try:
            total += int(val)
        except (ValueError, TypeError):
            pass

    if total <= 4:
        tier = "Minimal / No Depression"
        badge_class = "success"
    elif total <= 9:
        tier = "Mild Depression"
        badge_class = "info"
    elif total <= 14:
        tier = "Moderate Depression"
        badge_class = "warning"
    elif total <= 19:
        tier = "Moderately Severe Depression"
        badge_class = "orange"
    else:
        tier = "Severe Depression"
        badge_class = "danger"

    has_suicidal_flag = int(responses.get('q9', 0)) > 0

    return {
        "total_score": total,
        "max_score": 27,
        "severity_tier": tier,
        "badge_class": badge_class,
        "has_suicidal_flag": has_suicidal_flag,
        "sub_scores": {}
    }


def calculate_gad7_score(responses: dict) -> dict:
    """
    Computes total GAD-7 score (0-21) and anxiety severity classification.
    """
    total = 0
    for i in range(1, 8):
        key = f"q{i}"
        val = responses.get(key, 0)
        try:
            total += int(val)
        except (ValueError, TypeError):
            pass

    if total <= 4:
        tier = "Minimal Anxiety"
        badge_class = "success"
    elif total <= 9:
        tier = "Mild Anxiety"
        badge_class = "info"
    elif total <= 14:
        tier = "Moderate Anxiety"
        badge_class = "warning"
    else:
        tier = "Severe Anxiety"
        badge_class = "danger"

    return {
        "total_score": total,
        "max_score": 21,
        "severity_tier": tier,
        "badge_class": badge_class,
        "sub_scores": {}
    }


def calculate_dass21_score(responses: dict) -> dict:
    """
    Computes DASS-21 subscale scores (multiplied by 2 for standard 42-pt scale comparison).
    """
    scales = {"depression": 0, "anxiety": 0, "stress": 0}
    for q in DASS21_QUESTIONS:
        qid = q["id"]
        scale = q["scale"]
        val = responses.get(qid, 0)
        try:
            scales[scale] += int(val)
        except (ValueError, TypeError):
            pass

    # Multiply by 2 as per standard DASS-21 protocol
    dep_score = scales["depression"] * 2
    anx_score = scales["anxiety"] * 2
    str_score = scales["stress"] * 2

    def _dep_tier(s):
        if s <= 9: return "Normal"
        if s <= 13: return "Mild"
        if s <= 20: return "Moderate"
        if s <= 27: return "Severe"
        return "Extremely Severe"

    def _anx_tier(s):
        if s <= 7: return "Normal"
        if s <= 9: return "Mild"
        if s <= 14: return "Moderate"
        if s <= 19: return "Severe"
        return "Extremely Severe"

    def _str_tier(s):
        if s <= 14: return "Normal"
        if s <= 18: return "Mild"
        if s <= 25: return "Moderate"
        if s <= 33: return "Severe"
        return "Extremely Severe"

    sub_scores = {
        "depression": {"raw": scales["depression"], "scaled": dep_score, "tier": _dep_tier(dep_score)},
        "anxiety":    {"raw": scales["anxiety"],    "scaled": anx_score, "tier": _anx_tier(anx_score)},
        "stress":     {"raw": scales["stress"],     "scaled": str_score, "tier": _str_tier(str_score)},
    }

    total_score = dep_score + anx_score + str_score
    overall_tier = f"Dep: {_dep_tier(dep_score)}, Anx: {_anx_tier(anx_score)}, Str: {_str_tier(str_score)}"

    return {
        "total_score": total_score,
        "max_score": 126,
        "severity_tier": overall_tier,
        "badge_class": "info",
        "sub_scores": sub_scores
    }


# ============================================================================
# Automated Discreet SMS Dispatch Helper
# ============================================================================

def send_counseling_notification_sms(student, message_type="appointment_confirm", context=None):
    """
    Dispatches a discreet, stigma-free SMS reminder via core.utils.send_sms.
    Uses configurable database templates from CounselingSettings.
    """
    settings = CounselingSettings.get_settings()
    if not settings.enable_sms_notifications:
        return False, "SMS notifications disabled in settings."

    if not student or not student.student_mobile:
        return False, "No student mobile number available."

    ctx = context or {}
    format_kwargs = {
        'date': ctx.get('date', 'Tomorrow'),
        'time': ctx.get('time', 'Scheduled Time'),
        'room': ctx.get('room', settings.counselor_room_default),
        'student_id': getattr(student, 'student_id', ''),
        'student_name': getattr(student, 'student_name', ''),
        'case_number': ctx.get('case_number', ''),
    }

    if message_type == "appointment_confirm":
        tpl = settings.sms_template_appointment_confirm or "Your counseling session is confirmed for {date} at {time} in Room {room}. BAUST Counseling Center."
        try:
            msg = tpl.format(**format_kwargs)
        except Exception:
            msg = f"Your session at BAUST Counseling Center is confirmed for {format_kwargs['date']} at {format_kwargs['time']} ({format_kwargs['room']})."
        event = "appointment_confirmed"
    elif message_type == "crisis_alert":
        tpl = settings.sms_template_crisis_alert or "Urgent counseling check-in requested for student {student_id}. Case ID: {case_number}."
        try:
            msg = tpl.format(**format_kwargs)
        except Exception:
            msg = f"BAUST Crisis Care: Check-in requested for Student ID {student.student_id}. Case #{format_kwargs['case_number']}."
        event = "crisis_alert"
    else:
        msg = f"Reminder: Counseling appointment scheduled for {format_kwargs['date']} at {format_kwargs['time']} ({format_kwargs['room']})."
        event = "appointment_reminder"

    return send_sms(
        number=student.student_mobile,
        message=msg,
        module='COUNSELING',
        use_case_event=event,
        recipient_name=student.student_name,
        student_id=student.student_id
    )
