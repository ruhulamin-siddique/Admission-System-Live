from django.db import models

class Cluster(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="UGC Cluster Code (e.g., 05)")
    is_engineering = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Clusters"

class Program(models.Model):
    LEVEL_CHOICES = [
        ('1', 'Bachelor'),
        ('3', 'Masters'),
    ]
    name = models.CharField(max_length=150, unique=True, help_text="Full Name (e.g., Computer Science and Engineering)")
    short_name = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="Short Name (e.g., CSE)")
    ugc_code = models.CharField(max_length=10, help_text="UGC Subject Code (e.g., 01 for CSE)")
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name='programs')
    level_code = models.CharField(max_length=1, choices=LEVEL_CHOICES, default='1', verbose_name="Program Type")
    sort_order = models.IntegerField(default=0, help_text="Higher numbers appear first")

    def __str__(self):
        return f"{self.name} ({self.short_name})" if self.short_name else self.name

    @property
    def full_ugc_code(self):
        """Returns the 5-digit UGC code (Cluster + Subject + Level)."""
        clean_ugc = ''.join(filter(str.isdigit, self.ugc_code))
        return f"{self.cluster.code}{clean_ugc}{self.level_code}"

    class Meta:
        ordering = ['-sort_order', 'name']
        unique_together = ('cluster', 'ugc_code', 'level_code')

class Hall(models.Model):
    full_name = models.CharField(max_length=150, unique=True, null=True, blank=True)
    short_name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Internal/UGC Hall Code (e.g., 01)")

    def __str__(self):
        return self.full_name if self.full_name else self.short_name

class AdmissionYear(models.Model):
    year = models.IntegerField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.year)

    class Meta:
        ordering = ['-year']

class Semester(models.Model):
    name = models.CharField(max_length=50, unique=True) # e.g., Spring
    code = models.CharField(max_length=1, help_text="Semester code (1 or 2)")

    def __str__(self):
        return self.name

class Batch(models.Model):
    name = models.CharField(max_length=50) # e.g., 25th
    admission_year = models.ForeignKey(AdmissionYear, on_delete=models.CASCADE)
    sort_order = models.IntegerField(default=0, help_text="Higher numbers appear first")

    def __str__(self):
        return f"{self.name} ({self.admission_year.year})"

    class Meta:
        verbose_name_plural = "Batches"
        unique_together = ('name', 'admission_year')
        ordering = ['-sort_order', 'name']
