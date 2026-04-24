from django.db.models import Count, Sum, Avg, Case, When, IntegerField, Q
from .models import Student

def get_academic_analytics(year=None, program=None):
    """
    Returns aggregated academic performance and demographic data.
    """
    queryset = Student.objects.all()
    if year:
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

    return {
        'gpa_stats': gpa_stats,
        'gender_split': list(gender_split),
        'religion_split': list(religion_split),
        'blood_split': list(blood_split),
        'program_split': list(program_split),
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
