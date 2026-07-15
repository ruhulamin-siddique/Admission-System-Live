import datetime
from django.db import migrations

def seed_developer_portfolio(apps, schema_editor):
    DeveloperProfile = apps.get_model('core', 'DeveloperProfile')
    Education = apps.get_model('core', 'Education')
    Experience = apps.get_model('core', 'Experience')
    Skill = apps.get_model('core', 'Skill')
    Project = apps.get_model('core', 'Project')
    Achievement = apps.get_model('core', 'Achievement')

    # 1. Developer Profile (Singleton pk=1)
    profile, created = DeveloperProfile.objects.update_or_create(
        id=1,
        defaults={
            'full_name': 'MD RUHULAMIN SIDDIQUE',
            'title': 'Assistant Software Engineer',
            'department': 'ICT Wing & Archive',
            'institution': 'Bangladesh Army University of Science and Technology (BAUST)',
            'tagline': 'Django Developer | Software Engineer | System Architect',
            'bio': (
                "An experienced Software Engineer and System Architect with a demonstrated history "
                "of developing high-performance, secure web applications. Currently serving as "
                "Assistant Software Engineer in the ICT Wing & Archive at BAUST, managing critical "
                "university management suites and examination billing systems. Skilled in Python, "
                "Django, PHP, Java, databases, and network technologies (CCNA, MTCNA)."
            ),
            'email': 'ruhulamin.ruet.ete12@gmail.com',
            'phone': '01780780785',
            'github_url': 'https://github.com/ruhulamin-siddique',
            'years_of_experience': 8,
            'is_available_for_work': True,
        }
    )

    # 2. Education (Delete existing to avoid duplicates on migration re-runs and seed fresh)
    profile.education_set.all().delete()
    
    Education.objects.create(
        developer=profile,
        degree='Master of Science (M.Sc.) in ICT',
        institution='Institute of Information and Communication Technology (IICT), Khulna University of Engineering & Technology (KUET)',
        field_of_study='Information and Communication Technology',
        start_year=2024,
        end_year=2026,
        gpa='3.50/4.00',
        description='Specialized in Information and Communication Technology.',
        sort_order=1
    )

    Education.objects.create(
        developer=profile,
        degree='B.Sc. in Electronics and Communication Engineering (ECE)',
        institution='Rajshahi University of Engineering & Technology (RUET)',
        field_of_study='Electronics and Communication Engineering',
        start_year=2014,
        end_year=2019,
        gpa='2.91/4.00',
        description='Completed undergraduate degree majoring in Electronics and Communication Engineering.',
        sort_order=2
    )

    Education.objects.create(
        developer=profile,
        degree='Higher Secondary Certificate (HSC)',
        institution='Tamirul Millat Kamil Madrasah, Dhaka',
        field_of_study='Science',
        start_year=2010,
        end_year=2012,
        gpa='5.00/5.00',
        description='Major in Science under the Madrasah Education Board, Dhaka.',
        sort_order=3
    )

    Education.objects.create(
        developer=profile,
        degree='Secondary School Certificate (SSC)',
        institution='Chitmirgonj Shalongram Fadil Madrasah, Nilphamari',
        field_of_study='Science',
        start_year=2008,
        end_year=2010,
        gpa='5.00/5.00',
        description='Major in Science under the Madrasah Education Board, Dhaka.',
        sort_order=4
    )

    # 3. Experience (Delete existing and seed fresh)
    profile.experiences.all().delete()

    Experience.objects.create(
        developer=profile,
        job_title='Assistant Software Engineer',
        organization='Bangladesh Army University of Science & Technology (BAUST)',
        employment_type='fulltime',
        location='Saidpur Cantonment, Nilphamari',
        start_date=datetime.date(2025, 7, 15),
        end_date=None,
        is_current=True,
        description=(
            "Working in the ICT Wing and Archive, designing, developing, and maintaining high-performance "
            "enterprise applications (including the Admission Management System) and archiving solutions. "
            "Automating academic board verification processes and exam billing calculations."
        ),
        sort_order=1
    )

    Experience.objects.create(
        developer=profile,
        job_title='IT Officer',
        organization='Bangladesh Army University of Science & Technology (BAUST)',
        employment_type='fulltime',
        location='Saidpur Cantonment, Nilphamari',
        start_date=datetime.date(2022, 2, 1),
        end_date=datetime.date(2025, 7, 15),
        is_current=False,
        description=(
            "Served in the Office of the Controller of Examinations. Managed exam registration portals, "
            "result calculation/tabulation systems, exam billing systems, and student records database."
        ),
        sort_order=2
    )

    Experience.objects.create(
        developer=profile,
        job_title='IT Expert',
        organization='Alhera Educare Home High School and College',
        employment_type='fulltime',
        location='Nilphamari',
        start_date=datetime.date(2019, 10, 1),
        end_date=datetime.date(2022, 1, 30),
        is_current=False,
        description=(
            "Administered school management information systems, developed customized reporting tools, "
            "and handled network setup and administrative databases."
        ),
        sort_order=3
    )

    Experience.objects.create(
        developer=profile,
        job_title='Software Developer',
        organization='Rove Dash Cam (USA Based Company)',
        employment_type='fulltime',
        location='Remote',
        start_date=datetime.date(2018, 3, 18),
        end_date=datetime.date(2019, 9, 30),
        is_current=False,
        description=(
            "Developed backend systems and APIs for dashcam settings configuration, GPS telemetry visualization, "
            "and cloud-based dashboard integration for connected vehicular cameras."
        ),
        sort_order=4
    )

    # 4. Skill (Delete existing and seed fresh)
    profile.skills.all().delete()

    skills_data = [
        # Backend
        ('Python', 'Backend', 90, 'fab fa-python', 1),
        ('Django', 'Backend', 90, 'fab fa-python', 2),
        ('PHP & MySQL', 'Backend', 85, 'fab fa-php', 3),
        ('Java', 'Backend', 80, 'fab fa-java', 4),
        # Frontend
        ('HTML5 & CSS3', 'Frontend', 85, 'fab fa-html5', 5),
        ('JavaScript & HTMX', 'Frontend', 80, 'fab fa-js', 6),
        # Database
        ('MySQL', 'Database', 85, 'fas fa-database', 7),
        ('SQLite', 'Database', 85, 'fas fa-database', 8),
        # DevOps
        ('Network Routing (CCNA)', 'DevOps', 75, 'fas fa-network-wired', 9),
        ('MikroTik Administration (MTCNA)', 'DevOps', 75, 'fas fa-server', 10),
        # Tools
        ('Google IT Automation', 'Tools', 80, 'fas fa-cogs', 11),
        ('Google Data Analytics', 'Tools', 80, 'fas fa-chart-bar', 12),
    ]

    for name, category, proficiency, icon_class, sort_order in skills_data:
        Skill.objects.create(
            developer=profile,
            name=name,
            category=category,
            proficiency=proficiency,
            icon_class=icon_class,
            sort_order=sort_order
        )

    # 5. Achievements / Certifications (Delete existing and seed fresh)
    profile.achievements.all().delete()

    achievements_data = [
        ('Google IT Automation with Python Specialization', 'Coursera and Google', datetime.date(2021, 6, 30), 'fab fa-google', 1),
        ('Google Data Analytics Specialization', 'Coursera and Google', datetime.date(2021, 9, 30), 'fab fa-google', 2),
        ('Google IT Support Specialization', 'Coursera and Google', datetime.date(2021, 5, 31), 'fab fa-google', 3),
        ('Cisco Certified Network Associate (CCNA)', 'Cisco Networking Academy, RUET', datetime.date(2017, 9, 30), 'fab fa-cisco', 4),
        ('MikroTik Certified Network Associate (MTCNA)', 'AT Computer Solutions, Dhaka', datetime.date(2021, 6, 30), 'fas fa-network-wired', 5),
        ('Web Application Development using PHP & MySQL', 'Bangladesh Computer Council, Rajshahi (LICT Top-Up IT Training)', datetime.date(2017, 9, 30), 'fab fa-php', 6),
        ('Web Application Development using Java', 'Bangladesh Computer Council, Rajshahi (LICT Top-Up IT Training)', datetime.date(2017, 9, 30), 'fab fa-java', 7),
    ]

    for title, issuer, date_earned, icon_class, sort_order in achievements_data:
        Achievement.objects.create(
            developer=profile,
            title=title,
            issuer=issuer,
            date_earned=date_earned,
            icon_class=icon_class,
            sort_order=sort_order
        )

    # 6. Projects (Delete existing and seed fresh)
    profile.projects.all().delete()
    
    Project.objects.create(
        developer=profile,
        title='Admission Suite - Professional Admission Management System',
        description=(
            "A high-performance, secure, and modern Django-based web application designed for managing "
            "student admissions, academic records, and institutional examination billing at BAUST. Features "
            "granular RBAC, dynamic HTMX UI, automated SSC/HSC verification, and exam bill processing."
        ),
        tech_stack='Python, Django, MySQL, HTMX, Vanilla CSS, JavaScript',
        github_url='https://github.com/ruhulamin-siddique/Admission-System-Live',
        live_url='',
        status='live',
        is_featured=True,
        sort_order=1
    )

def reverse_seed_developer_portfolio(apps, schema_editor):
    DeveloperProfile = apps.get_model('core', 'DeveloperProfile')
    DeveloperProfile.objects.filter(id=1).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_developer_portfolio'),
    ]

    operations = [
        migrations.RunPython(seed_developer_portfolio, reverse_seed_developer_portfolio),
    ]
