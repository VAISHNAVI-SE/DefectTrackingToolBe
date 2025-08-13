from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Project, UserProfile, Defect, Mentor, DefectHistory

# Unregister the default User admin
admin.site.unregister(User)

# --- UserProfile Admin ---
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'get_projects', 'mentor']
    list_filter = ['role']
    filter_horizontal = ['projects']

    def get_projects(self, obj):
        return ", ".join([p.name for p in obj.projects.all()])
    get_projects.short_description = 'Projects'


admin.site.register(UserProfile, UserProfileAdmin)  # <-- Register with custom admin

# --- Inline for UserProfile in User admin ---
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    readonly_fields = ['firebase_uid']

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')

# Register the new User admin
admin.site.register(User, CustomUserAdmin)

# --- Project Admin ---
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['name']

# --- Defect Admin ---
@admin.register(Defect)
class DefectAdmin(admin.ModelAdmin):
    list_display = ['defect_id', 'summary', 'priority', 'status', 'project', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'project', 'created_at']
    search_fields = ['summary', 'defect_id']
    readonly_fields = ['defect_id', 'created_at', 'updated_at', 'approved_at']
    ordering = ['-created_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('defect_id', 'project', 'summary', 'priority')
        }),
        ('Details', {
            'fields': ('actual_result', 'expected_result')
        }),
        ('Status & Approval', {
            'fields': ('status', 'approved_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'approved_at')
        }),
    )
# --- Mentor Admin ---
@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ['mentor_username', 'user', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['mentor_username', 'user__username']
    filter_horizontal = ['projects']
    ordering = ['mentor_username']

# --- DefectHistory Admin ---
@admin.register(DefectHistory)
class DefectHistoryAdmin(admin.ModelAdmin):
    list_display = ['defect', 'action', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['defect__defect_id', 'performed_by__username']
    readonly_fields = ['defect', 'action', 'performed_by', 'timestamp', 'changes']
    ordering = ['-timestamp']

# --- Admin Site Customization ---
admin.site.site_header = "Defect Tracking Tool Administration"
admin.site.site_title = "Defect Tracker Admin"
admin.site.index_title = "Welcome to Defect Tracking Tool Administration"