from django.contrib import admin
from .models import (
    DeveloperProfile, Education, Skill,
    Project, Experience, Achievement
)


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0
    ordering = ['sort_order', '-start_year']


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0
    ordering = ['sort_order', 'category']


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0
    ordering = ['-is_featured', 'sort_order']
    fields = ('title', 'status', 'is_featured', 'sort_order', 'github_url', 'live_url')


class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0
    ordering = ['sort_order', '-start_date']


class AchievementInline(admin.TabularInline):
    model = Achievement
    extra = 0
    ordering = ['sort_order']


@admin.register(DeveloperProfile)
class DeveloperProfileAdmin(admin.ModelAdmin):
    inlines = [EducationInline, SkillInline, ExperienceInline, AchievementInline, ProjectInline]
    readonly_fields = ['visit_count', 'updated_at']
    fieldsets = (
        ('Identity', {
            'fields': ('full_name', 'title', 'department', 'institution', 'tagline', 'bio', 'profile_photo')
        }),
        ('Contact & Links', {
            'fields': ('email', 'phone', 'github_url', 'linkedin_url', 'portfolio_url')
        }),
        ('Status', {
            'fields': ('years_of_experience', 'is_available_for_work', 'visit_count', 'updated_at')
        }),
    )


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('degree', 'institution', 'start_year', 'end_year', 'sort_order')
    ordering = ['sort_order', '-start_year']


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'proficiency', 'sort_order')
    list_filter = ('category',)
    ordering = ['sort_order', 'category']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'is_featured', 'sort_order')
    list_filter = ('status', 'is_featured')
    ordering = ['-is_featured', 'sort_order']


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('job_title', 'organization', 'employment_type', 'is_current', 'start_date')
    ordering = ['sort_order', '-start_date']


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('title', 'issuer', 'date_earned', 'sort_order')
    ordering = ['sort_order']
