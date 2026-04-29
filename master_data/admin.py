from django.contrib import admin
from .models import Cluster, Program, Hall, AdmissionYear, Semester, Batch

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'ugc_code', 'cluster', 'level_code')
    list_filter = ('cluster', 'level_code')
    search_fields = ('name', 'ugc_code')

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(AdmissionYear)
class AdmissionYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'is_active')
    list_editable = ('is_active',)

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'admission_year', 'sort_order')
    list_filter = ('admission_year',)
    search_fields = ('name',)
