from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import uuid

class Project(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name    
    
    class Meta:
        ordering = ['name']

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('mentor', 'Mentor'),
        ('client', 'Client'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mentor = models.ForeignKey('Mentor', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    projects = models.ManyToManyField(Project, blank=True, related_name='user_profiles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    firebase_uid = models.CharField(max_length=128, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username
    
    @property
    def full_name(self):
        return self.user.username

class Mentor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mentor_username = models.CharField(max_length=100, unique=True)
    projects = models.ManyToManyField(Project, related_name='mentors')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.mentor_username
    
    @login_required
    def mentor_student_defects(request):
        user = request.user
        try:
            mentor = Mentor.objects.get(user=user)
        except Mentor.DoesNotExist:
            return JsonResponse({'error': 'Not a mentor'}, status=403)
        defects = mentor.get_student_defects()
        data = [
            {
                'defect_id': defect.defect_id,
                'summary': defect.summary,
                'project': defect.project.name,
                'created_by': defect.created_by.username,
                'status': defect.status,
                'priority': defect.priority,
                'created_at': defect.created_at,
            }
            for defect in defects
        ]
        return JsonResponse({'defects': data})
    
    def get_student_defects(self):
        # Get all users with role 'student' in mentor's projects
        student_profiles = UserProfile.objects.filter(
            projects__in=self.projects.all(),
            role='student'
        ).distinct()
        student_users = [profile.user for profile in student_profiles]
        # Get defects created by these students
        return Defect.objects.filter(
            project__in=self.projects.all(),
            created_by__in=student_users
        ).select_related('project', 'created_by')

# New model for defect screenshots
class DefectScreenshot(models.Model):
    image = models.ImageField(upload_to='defect_screenshots/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    defect = models.ForeignKey('Defect', on_delete=models.CASCADE, related_name='screenshots')
    
    def __str__(self):
        return f"Screenshot {self.id} for Defect #{self.defect.defect_id}"

class Defect(models.Model):
    PRIORITY_CHOICES = [
        ('P1', 'P1 - Critical'),
        ('P2', 'P2 - High'),
        ('P3', 'P3 - Medium'),
        ('P4', 'P4 - Low'),
    ]
    
    MENTOR_STATE_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Invalid', 'Invalid'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('REOPEN', 'Reopen'),
        ('APPROVED', 'Approved'),
        ('INVALID', 'Invalid'),
        ('PENDING', 'Pending'),
    ]
    
    SEVERITY_CHOICES = [
        ('S1', 'S1 - Blocker'),
        ('S2', 'S2 - Critical'),
        ('S3', 'S3 - Major'),
        ('S4', 'S4 - Minor'),
        ('S5', 'S5 - Medium'),
        ('S6', 'S6 - High'),
    ]
    
    mentor_state = models.CharField(
        max_length=20,
        choices=MENTOR_STATE_CHOICES, 
        default='Pending'
    )
    defect_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='defects')
    environment = models.CharField(max_length=100, blank=True, null=True)
    summary = models.CharField(max_length=500)
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='S4')
    steps_to_reproduce = models.TextField(blank=True)
    actual_result = models.TextField()
    expected_result = models.TextField()
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='OPEN')
    application_url = models.URLField(blank=True, null=True)
    
    # Changed from single ImageField to ManyToMany for multiple screenshots
    # defect_screenshots = models.ImageField(upload_to='defect_screenshots/', blank=True, null=True)
    
    defect_video = models.FileField(upload_to='defect_videos/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_defects')
    approved_by = models.ForeignKey(User, related_name='approved_defects', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Defect #{self.defect_id} - {self.summary[:50]}"

    def save(self, *args, **kwargs):
        if self.status == 'APPROVED' and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def defect_screenshots(self):
        """Property to get all screenshots for this defect"""
        return self.screenshots.all()
    
    def add_screenshot(self, image_file):
        """Helper method to add a screenshot"""
        screenshot = DefectScreenshot.objects.create(defect=self, image=image_file)
        return screenshot
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['project']),
            models.Index(fields=['created_by']),
        ]

class DefectHistory(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('APPROVED', 'Approved'),
        ('INVALIDATED', 'Marked Invalid'),
    ]
    
    defect = models.ForeignKey(Defect, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Defect histories"