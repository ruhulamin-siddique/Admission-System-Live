from collections import defaultdict
from decimal import Decimal


ZERO = Decimal('0.00')
ENGINEERING_PREFIXES = ('CE', 'IP', 'CS', 'ME', 'EE', 'IC')


def money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


def is_engineering_course(course):
    if getattr(course, 'is_engineering', None) is not None:
        return bool(course.is_engineering)
    code = (getattr(course, 'course_code', '') or '').upper()
    return code.startswith(ENGINEERING_PREFIXES)


def part_multiplier(part):
    return Decimal('2.00') if part == 'A+B' else Decimal('1.00')


def full_or_half(assignments, assignment):
    same_course = [
        item for item in assignments
        if item.course_id == assignment.course_id and not getattr(item, 'is_deleted', False)
    ]
    return 'full' if len(same_course) == 1 or assignment.part == 'A+B' else 'half'


def question_setter_rate(settings, assignment, all_assignments):
    size = full_or_half(all_assignments, assignment)
    course_type = 'engineering' if is_engineering_course(assignment.course) else 'non_engineering'
    return getattr(settings, f'qsetter_{size}_{course_type}_rate')


def examiner_rate(settings, assignment, all_assignments):
    size = full_or_half(all_assignments, assignment)
    course_type = 'engineering' if is_engineering_course(assignment.course) else 'non_engineering'
    return getattr(settings, f'examiner_{size}_{course_type}_rate')


def scrutinizer_rate(settings, assignment, all_assignments):
    size = full_or_half(all_assignments, assignment)
    course_type = 'engineering' if is_engineering_course(assignment.course) else 'non_engineering'
    return getattr(settings, f'scrutinizer_{size}_{course_type}_rate')


def calculate_exam_program_summary(exam_program):
    settings = getattr(exam_program.exam, 'settings', None)
    if settings is None:
        # No billing settings configured for this exam — return empty summary
        return {'rows': [], 'grand_total': ZERO}

    totals = defaultdict(lambda: defaultdict(lambda: ZERO))
    details = defaultdict(list)

    for item in exam_program.cecc_assignments.select_related('faculty').filter(is_deleted=False):
        role = (item.role or '').lower()
        amount = settings.cecc_chairman_rate if 'chair' in role or 'advisor' in role or 'invigilator' in role else settings.cecc_member_rate
        _add(details, totals, item.faculty, 'cecc', amount, item.role or 'CECC')

    for item in exam_program.ec_members.select_related('faculty').filter(is_deleted=False):
        role = (item.role or '').lower()
        amount = settings.ec_chairman_rate if 'chair' in role else settings.ec_member_rate
        _add(details, totals, item.faculty, 'ec', amount, item.role or 'EC')

    rpsc_counts = {f"{s.level}-{s.term}": s.total_students for s in exam_program.level_term_summaries.all()}
    total_all_students = sum(rpsc_counts.values())
    for item in exam_program.rpsc_assignments.select_related('faculty').filter(is_deleted=False):
        role = (item.role or '').lower()
        rate = settings.rpsc_chairman_rate if 'chair' in role else settings.rpsc_member_rate
        students = total_all_students if item.level == 'All' else rpsc_counts.get(f"{item.level}-{item.term}", 0)
        amount = money(students) * rate
        label = 'All Levels/Terms' if item.level == 'All' else f'{item.level}-{item.term}'
        _add(details, totals, item.faculty, 'rpsc', amount, f'{label} RPSC')

    for item in exam_program.qmsc_assignments.select_related('faculty', 'course').filter(is_deleted=False):
        if not item.faculty_id:
            continue  # external-only display entry — not billed
        role = (item.role or '').lower()
        amount = settings.qmsc_chairman_rate if 'chair' in role else settings.qmsc_member_rate
        desc = 'QMSC Chairman' if 'chair' in role else f'{item.course.course_code if item.course else "?"} QMSC'
        _add(details, totals, item.faculty, 'qmsc', amount, desc)

    qpsc_members = list(exam_program.qpsc_members.select_related('faculty').filter(is_deleted=False))
    member_count = len(qpsc_members) or 1
    for item in qpsc_members:
        amount = (money(item.question_count) * settings.qpsc_member_rate) / member_count
        _add(details, totals, item.faculty, 'qpsc', amount, item.role or 'QPSC')

    qsetters = list(exam_program.question_setters.select_related('faculty', 'course').filter(is_deleted=False))
    for item in qsetters:
        amount = question_setter_rate(settings, item, qsetters) * part_multiplier(item.part)
        _add(details, totals, item.faculty, 'question_setting', amount, f'{item.course.course_code} Part {item.part}')

    examiners = list(exam_program.script_examiners.select_related('faculty', 'course').filter(is_deleted=False))
    for item in examiners:
        amount = examiner_rate(settings, item, examiners) * money(item.course.no_of_scripts) * part_multiplier(item.part)
        _add(details, totals, item.faculty, 'script_examining', amount, f'{item.course.course_code} Part {item.part}')

    scrutinizers = list(exam_program.script_scrutinizers.select_related('faculty', 'course').filter(is_deleted=False))
    for item in scrutinizers:
        amount = scrutinizer_rate(settings, item, scrutinizers) * money(item.course.no_of_scripts) * part_multiplier(item.part)
        _add(details, totals, item.faculty, 'scrutiny', amount, f'{item.course.course_code} Part {item.part}')

    rows = []
    for faculty_id, buckets in totals.items():
        faculty = details[faculty_id][0]['faculty']
        row = {
            'faculty': faculty,
            'designation': faculty.designation,
            'cecc': money(buckets['cecc']),
            'ec': money(buckets['ec']),
            'rpsc': money(buckets['rpsc']),
            'qmsc': money(buckets['qmsc']),
            'qpsc': money(buckets['qpsc']),
            'question_setting': money(buckets['question_setting']),
            'script_examining': money(buckets['script_examining']),
            'scrutiny': money(buckets['scrutiny']),
            'details': details[faculty_id],
        }
        row['committee_total'] = row['cecc'] + row['ec'] + row['rpsc'] + row['qmsc'] + row['qpsc']
        row['total'] = sum(
            row[key] for key in ['cecc', 'ec', 'rpsc', 'qmsc', 'qpsc', 'question_setting', 'script_examining', 'scrutiny']
        )
        row['committee_total'] = sum(row[key] for key in ['cecc', 'ec', 'rpsc', 'qmsc', 'qpsc'])
        rows.append(row)

    rows.sort(key=lambda item: item['faculty'].name)
    grand_total = sum((row['total'] for row in rows), ZERO)
    return {'rows': rows, 'grand_total': money(grand_total)}


def calculate_faculty_bill(exam_program, faculty_id):
    summary = calculate_exam_program_summary(exam_program)
    for row in summary['rows']:
        if row['faculty'].id == int(faculty_id):
            row['amount_in_words'] = taka_in_words(row['total'])
            return row
    return None


def _add(details, totals, faculty, bucket, amount, description):
    amount = money(amount)
    totals[faculty.id][bucket] += amount
    details[faculty.id].append({
        'faculty': faculty,
        'bucket': bucket,
        'description': description,
        'amount': amount,
    })


ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
        'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen',
        'Eighteen', 'Nineteen']
TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def taka_in_words(amount):
    amount = money(amount)
    taka = int(amount)
    paisa = int((amount - taka) * 100)
    words = _number_to_words(taka) or 'Zero'
    paisa_words = _number_to_words(paisa) if paisa else 'Zero'
    return f'Taka {words} {paisa_words} Paisa'


def _number_to_words(number):
    number = int(number)
    if number == 0:
        return ''
    parts = []
    crore, number = divmod(number, 10000000)
    lakh, number = divmod(number, 100000)
    thousand, number = divmod(number, 1000)
    hundred, number = divmod(number, 100)
    if crore:
        parts.append(f'{_under_hundred(crore)} Crore')
    if lakh:
        parts.append(f'{_under_hundred(lakh)} Lakh')
    if thousand:
        parts.append(f'{_under_hundred(thousand)} Thousand')
    if hundred:
        parts.append(f'{ONES[hundred]} Hundred')
    if number:
        parts.append(_under_hundred(number))
    return ' '.join(part for part in parts if part).strip()


def _under_hundred(number):
    number = int(number)
    if number < 20:
        return ONES[number]
    ten, one = divmod(number, 10)
    return f'{TENS[ten]} {ONES[one]}'.strip()
