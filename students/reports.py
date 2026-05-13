from django.db.models import Count, Sum, Avg, Case, When, IntegerField, Q, Value
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from datetime import timedelta
from .models import Student

def get_academic_analytics(year=None, program=None, batch=None):
    """
    Returns aggregated academic performance and demographic data.
    """
    queryset = Student.objects.all()
    if batch: 
        queryset = queryset.filter(batch=batch)
    elif year: 
        queryset = queryset.filter(admission_year=year)
        
    if program: 
        queryset = queryset.filter(program=program)

    # GPA Distribution (SSC & HSC)
    gpa_stats = queryset.aggregate(
        ssc_avg=Avg('ssc_gpa'),
        hsc_avg=Avg('hsc_gpa'),
        total_count=Count('student_id'),
        ssc_5=Count(Case(When(ssc_gpa=5.0, then=1), output_field=IntegerField())),
        ssc_4=Count(Case(When(ssc_gpa__gte=4.0, ssc_gpa__lt=5.0, then=1), output_field=IntegerField())),
        hsc_5=Count(Case(When(hsc_gpa=5.0, then=1), output_field=IntegerField())),
        hsc_4=Count(Case(When(hsc_gpa__gte=4.0, hsc_gpa__lt=5.0, then=1), output_field=IntegerField())),
    )

    # Demographic Splits
    gender_split = queryset.values('gender').annotate(count=Count('student_id'))
    religion_split = queryset.values('religion').annotate(count=Count('student_id'))
    blood_split = queryset.values('blood_group').annotate(count=Count('student_id'))
    program_split = queryset.values('program').annotate(count=Count('student_id'))
    hall_split = queryset.values('hall_attached').annotate(count=Count('student_id'))

    return {
        'gpa_stats': gpa_stats,
        'gender_split': list(gender_split),
        'religion_split': list(religion_split),
        'blood_split': list(blood_split),
        'program_split': list(program_split),
        'hall_split': list(hall_split),
    }

def get_institutional_intelligence(year=None, batch=None, program=None):
    """
    Aggregates top feeder schools and colleges.
    """
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    top_schools = queryset.exclude(ssc_school__isnull=True).exclude(ssc_school='') \
        .values('ssc_school').annotate(count=Count('student_id')).order_by('-count')[:20]
    
    top_colleges = queryset.exclude(hsc_college__isnull=True).exclude(hsc_college='') \
        .values('hsc_college').annotate(count=Count('student_id')).order_by('-count')[:20]

    return {
        'top_schools': list(top_schools),
        'top_colleges': list(top_colleges),
        'total_students': queryset.count()
    }

def get_geographic_insights(year=None, batch=None, program=None):
    """
    Aggregates student distribution by Division and District.
    """
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    division_split = queryset.values('present_division').annotate(count=Count('student_id')).order_by('-count')
    district_split = queryset.values('present_district').annotate(count=Count('student_id')).order_by('-count')

    return {
        'division_split': list(division_split),
        'district_split': list(district_split),
        'total_students': queryset.count()
    }

def get_research_demographics(year=None, batch=None, program=None):
    """
    Provides advanced research splits like parental occupation and waiver distribution.
    """
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    parent_occupation = queryset.values('father_occupation').annotate(count=Count('student_id')).order_by('-count')
    
    waiver_stats = queryset.aggregate(
        total_waiver=Sum('waiver'),
        avg_waiver=Avg('waiver'),
        significant_waiver=Count(Case(When(waiver__gte=5000, then=1), output_field=IntegerField())),
        any_waiver=Count(Case(When(waiver__gt=0, then=1), output_field=IntegerField())),
        no_waiver=Count(Case(When(waiver=0, then=1), output_field=IntegerField())),
    )

    return {
        'occupation_split': list(parent_occupation),
        'waiver_stats': waiver_stats,
        'total_students': queryset.count()
    }

def get_financial_summary(year=None):
    """
    Returns financial collection and waiver summaries.
    """
    queryset = Student.objects.all()
    if year:
        queryset = queryset.filter(admission_year=year)

    summary = queryset.aggregate(
        total_admission_paid=Sum('admission_payment'),
        total_second_installment=Sum('second_installment'),
        total_waivers=Sum('waiver'),
        total_others=Sum('others'),
        projected_total=Avg('admission_payment') * Count('student_id') # Placeholder for target logic
    )
    
    # Fill Nones with 0
    for key in summary:
        if summary[key] is None:
            summary[key] = 0.0
            
    return summary

def get_subject_performance(year=None, program=None, batch=None):
    """Aggregates science subject marks (Physics, Chemistry, Math) by Program and Batch."""
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    # Global Averages
    global_stats = queryset.aggregate(
        avg_ssc_phy=Avg('ssc_physics'), avg_ssc_che=Avg('ssc_chemistry'), avg_ssc_mat=Avg('ssc_math'),
        avg_hsc_phy=Avg('hsc_physics'), avg_hsc_che=Avg('hsc_chemistry'), avg_hsc_mat=Avg('hsc_math')
    )

    # Program-wise Performance
    program_stats = queryset.values('program').annotate(
        phy=Avg('hsc_physics'), che=Avg('hsc_chemistry'), mat=Avg('hsc_math'),
        count=Count('student_id')
    ).exclude(program='').order_by('program')

    # Batch-wise Performance
    batch_stats = queryset.values('batch', 'program').annotate(
        phy=Avg('hsc_physics'), che=Avg('hsc_chemistry'), mat=Avg('hsc_math'),
        count=Count('student_id')
    ).exclude(batch='').order_by('batch', 'program')

    return {
        'global': global_stats,
        'programs': list(program_stats),
        'batches': list(batch_stats),
        'total_count': queryset.count()
    }

def get_reference_intelligence(year=None, program=None, batch=None):
    """Analyzes recruitment references and sources."""
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    refs = queryset.values('reference').annotate(count=Count('student_id')).exclude(reference='').order_by('-count')
    return {
        'references': list(refs),
        'total': queryset.count()
    }

def get_financial_intelligence(year=None, program=None, batch=None):
    """Calculates revenue, waivers, and financial impact."""
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    stats = queryset.aggregate(
        gross_admission=Sum('admission_payment'),
        total_waiver=Sum('waiver'), # Note: Waiver might be %, need to check logic
        total_others=Sum('others'),
        total_second=Sum('second_installment')
    )
    
    # Financial trend by batch
    batch_revenue = queryset.values('batch').annotate(
        revenue=Sum('admission_payment'),
        waiver=Sum('waiver')
    ).exclude(batch='').order_by('batch')

    return {
        'summary': stats,
        'batch_trends': list(batch_revenue),
        'total_students': queryset.count()
    }

def get_diversity_intelligence(year=None, program=None, batch=None):
    """Analyzes gender and religious diversity."""
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    gender = queryset.values('gender').annotate(count=Count('student_id'))
    religion = queryset.values('religion').annotate(count=Count('student_id'))
    
    return {
        'gender': list(gender),
        'religion': list(religion),
        'total': queryset.count()
    }

def get_age_gap_analysis(year=None, program=None, batch=None):
    """Analyzes student age and gap-year (HSC vs Admission)."""
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
        
    if program:
        queryset = queryset.filter(program=program)

    # Gap Year calculation: admission_year - hsc_year
    # This requires some complex aggregation or post-processing
    students = queryset.values('student_id', 'hsc_year', 'admission_year')
    gaps = {}
    for s in students:
        try:
            gap = int(s['admission_year']) - int(s['hsc_year'])
            gaps[gap] = gaps.get(gap, 0) + 1
        except: continue
    
    gap_data = [{'gap': k, 'count': v} for k, v in sorted(gaps.items())]
    
    return {
        'gap_distribution': gap_data,
        'total': queryset.count()
    }

def get_migration_intelligence():
    """Analyzes student migration patterns between programs."""
    from .models import ProgramChangeHistory
    migrations = ProgramChangeHistory.objects.all()
    
    # Analyze From -> To
    patterns = {}
    for m in migrations:
        key = (m.old_program, m.new_program)
        patterns[key] = patterns.get(key, 0) + 1
    
    pattern_data = [
        {'old': k[0], 'new': k[1], 'count': v} 
        for k, v in patterns.items()
    ]
    return {
        'patterns': sorted(pattern_data, key=lambda x: x['count'], reverse=True),
        'total': migrations.count()
    }

def get_intake_performance_analysis():
    """Provides a comprehensive performance analysis across last 10 batches."""
    import re
    all_batches_raw = list(Student.objects.values_list('batch', flat=True).distinct().exclude(batch=''))
    
    # Parse batches and sort them numerically
    batch_objects = []
    for b in all_batches_raw:
        nums = re.findall(r'\d+', b)
        if nums:
            batch_objects.append({'name': b, 'num': int(nums[0])})
    
    # Sort by number descending and take top 10
    batch_objects.sort(key=lambda x: x['num'], reverse=True)
    top_batches = batch_objects[:10]
    top_batches.reverse() # Chronological for charts
    
    analysis_data = []
    for b_obj in top_batches:
        qs = Student.objects.filter(batch=b_obj['name'])
        stats = qs.aggregate(
            count=Count('student_id'),
            avg_ssc=Avg('ssc_gpa'),
            avg_hsc=Avg('hsc_gpa'),
            female_count=Count(Case(When(gender='Female', then=1), output_field=IntegerField())),
            golden_count=Count(Case(When(ssc_gpa=5.0, hsc_gpa=5.0, then=1), output_field=IntegerField())),
            revenue=Sum('admission_payment')
        )
        
        # Calculate Female %
        female_perc = (stats['female_count'] / stats['count'] * 100) if stats['count'] > 0 else 0
        
        analysis_data.append({
            'batch': b_obj['name'],
            'count': stats['count'],
            'avg_ssc': stats['avg_ssc'] or 0,
            'avg_hsc': stats['avg_hsc'] or 0,
            'female_perc': round(female_perc, 1),
            'golden_count': stats['golden_count'],
            'revenue': float(stats['revenue'] or 0)
        })
        
    return analysis_data

def get_admission_trends():
    """
    Calculates admission velocity for the last 30 days and 6 months.
    Includes zero-fill logic for visual consistency.
    """
    now = timezone.now()
    
    # 1. Last 30 Days (Daily Momentum)
    thirty_days_ago = now.date() - timedelta(days=29)
    daily_stats = Student.objects.filter(admission_date__gte=thirty_days_ago) \
        .annotate(day=TruncDay('admission_date')) \
        .values('day') \
        .annotate(count=Count('student_id')) \
        .order_by('day')
    
    # Fill gaps for 30 days
    daily_map = {
        (item['day'].date() if hasattr(item['day'], 'date') else item['day']): item['count'] 
        for item in daily_stats if item['day']
    }
    daily_trend = []
    for i in range(30):
        d = thirty_days_ago + timedelta(days=i)
        daily_trend.append({
            'label': d.strftime('%b %d'),
            'count': daily_map.get(d, 0)
        })

    # 2. Last 6 Months (Monthly Seasonality)
    start_month = now.replace(day=1)
    for _ in range(5):
        start_month = (start_month - timedelta(days=1)).replace(day=1)

    monthly_stats = Student.objects.filter(admission_date__gte=start_month.date()) \
        .annotate(month=TruncMonth('admission_date')) \
        .values('month') \
        .annotate(count=Count('student_id')) \
        .order_by('month')

    # Fill gaps for 6 months
    monthly_map = {
        (item['month'].date() if hasattr(item['month'], 'date') else item['month']): item['count'] 
        for item in monthly_stats if item['month']
    }
    monthly_trend = []
    curr_m = start_month
    for _ in range(6):
        monthly_trend.append({
            'label': curr_m.strftime('%b %Y'),
            'count': monthly_map.get(curr_m.date(), 0)
        })
        # Advance to next month
        if curr_m.month == 12:
            curr_m = curr_m.replace(year=curr_m.year + 1, month=1)
        else:
            curr_m = curr_m.replace(month=curr_m.month + 1)

    # 3. Growth Metrics
    prev_thirty_start = thirty_days_ago - timedelta(days=30)
    curr_period_count = sum(item['count'] for item in daily_trend)
    prev_period_count = Student.objects.filter(admission_date__range=(prev_thirty_start, thirty_days_ago - timedelta(days=1))).count()
    
    growth = 0
    if prev_period_count > 0:
        growth = round(((curr_period_count - prev_period_count) / prev_period_count) * 100, 1)
    elif curr_period_count > 0:
        growth = 100

    return {
        'daily': daily_trend,
        'monthly': monthly_trend,
        'metrics': {
            'last_30_days': curr_period_count,
            'growth_perc': growth,
            'peak_day': max(daily_trend, key=lambda x: x['count']) if daily_trend else None,
            'peak_month': max(monthly_trend, key=lambda x: x['count']) if monthly_trend else None,
        }
    }
