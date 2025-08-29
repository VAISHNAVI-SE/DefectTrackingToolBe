import profile
from rest_framework import serializers
from django.contrib.auth.models import User
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from streamlit import user
from .models import Project, UserProfile, Defect, Mentor, DefectHistory, DefectScreenshot
from django.conf import settings
from urllib.parse import urljoin

def get_full_media_url(path):
    if not path:
        return None
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return urljoin(settings.MEDIA_URL, path)

class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for Project model"""
    class Meta:
        model = Project
        fields = ['id', 'name']

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration using username, email, password, confirm_password, and project."""
    username = serializers.CharField(max_length=150,help_text="User's username")
    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    projects = serializers.PrimaryKeyRelatedField(many=True, queryset=Project.objects.filter(is_active=True))

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password', 'projects']

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def validate_username(self, value):
        if User.objects.filter(username=value, is_active=True).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        projects = validated_data.pop('projects') 
        user = User.objects.create_user(**validated_data)
        user.is_active = True
        user.save()
        profile = UserProfile.objects.create(user=user)
        profile.projects.set(projects) 
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login with username/email and password"""
    username = serializers.CharField(
        max_length=150,
        help_text="Username or email address"
    )
    password = serializers.CharField(
        write_only=True,
        help_text="User password"
    )

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['projects','project_name','email','username','firebase_uid']

class DefectScreenshotSerializer(serializers.ModelSerializer):
    """Serializer for defect screenshots"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = DefectScreenshot
        fields = ['id', 'image', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'image_url', 'uploaded_at']
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return settings.MEDIA_URL + str(obj.image)
        return None

class DefectSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='created_by.username', read_only=True)
    severity = serializers.CharField()
    priority = serializers.CharField()
    screenshots = DefectScreenshotSerializer(many=True, read_only=True)
    defect_video = serializers.FileField(use_url=True, required=False, allow_null=True)
    application_url = serializers.CharField(read_only=True)

    def get_created_by_name(self, obj):
        try:
            return obj.created_by.userprofile.username
        except AttributeError:
            return obj.created_by.username if obj.created_by else "Unknown"

    def get_approved_by_name(self, obj):
        try:
            return obj.approved_by.userprofile.full_name if obj.approved_by else None
        except AttributeError:
            return obj.approved_by.username if obj.approved_by else None

    def get_defect_video(self, obj):
        if obj.defect_video:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.defect_video.url)
            return settings.MEDIA_URL + str(obj.defect_video)
        return None
    
    class Meta:
        model = Defect
        fields = '__all__'

class DefectCreateSerializer(serializers.ModelSerializer):
    defect_screenshots = serializers.ListField(
        child=serializers.ImageField(required=False, allow_null=True),
        required=False,
        allow_null=True,
        write_only=True
    )
    defect_video = serializers.FileField(required=False, allow_null=True)
    
    """Serializer for creating new defects"""
    class Meta:
        model = Defect
        fields = ['project','summary','priority','severity','steps_to_reproduce','actual_result','expected_result','defect_screenshots','defect_video','application_url','environment','status']

    def validate_summary(self, value):
        """Validate summary length and content"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Summary must be at least 10 characters long")
        return value.strip()
    
    def create(self, validated_data):
        user = self.context['request'].user if 'request' in self.context else None
        if user is None or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required to create a defect.")
        
        # Extract files from validated_data
        defect_screenshots = validated_data.pop('defect_screenshots', [])
        defect_video = validated_data.pop('defect_video', None)
        
        validated_data['created_by'] = user
        defect = Defect.objects.create(**validated_data)
        
        # Handle multiple screenshots - FIXED: Use the add_screenshot method
        for screenshot_file in defect_screenshots:
            if screenshot_file:  # Only process if file exists
                defect.add_screenshot(screenshot_file)
        
        # Handle video
        if defect_video:
            defect.defect_video = defect_video
            defect.save()
            
        DefectHistory.objects.create(
            defect=defect, 
            action='CREATED', 
            performed_by=user, 
            comments='Defect created'
        )
        return defect

class DefectListSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='created_by.username', read_only=True)
    mentor_state = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    severity = serializers.CharField(read_only=True)
    priority = serializers.CharField(read_only=True)
    application_url = serializers.CharField(read_only=True)
    screenshots = DefectScreenshotSerializer(many=True, read_only=True)
    defect_video = serializers.SerializerMethodField()
    
    def get_defect_video(self, obj):
        if obj.defect_video:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.defect_video.url)
            return settings.MEDIA_URL + str(obj.defect_video)
        return None

    class Meta:
        model = Defect
        fields = [
            'defect_id',
            'summary',
            'project',
            'reported_by',
            'status',
            'severity',
            'priority',
            'created_at',
            'environment',
            'application_url',
            'screenshots',
            'defect_video',
            'mentor_state'
        ]

class DefectDetailSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='created_by.username', read_only=True)
    approved_by = serializers.CharField(source='approved_by.username', read_only=True, default=None)
    screenshots = DefectScreenshotSerializer(many=True, read_only=True)
    defect_video = serializers.SerializerMethodField()
    application_url = serializers.CharField()
    
    def get_defect_video(self, obj):
        if obj.defect_video:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.defect_video.url)
            return settings.MEDIA_URL + str(obj.defect_video)
        return None

    class Meta:
        model = Defect
        fields = ['defect_id', 'project', 'summary', 'priority', 'steps_to_reproduce',
                  'actual_result', 'expected_result', 'reported_by', 'approved_by',
                  'created_at', 'updated_at', 'approved_at', 'environment', 'screenshots','defect_video','status','application_url','severity','mentor_state']
        read_only_fields = ['defect_id', 'project', 'reported_by', 'approved_by',
                            'created_at', 'updated_at', 'approved_at', 'environment','screenshots','defect_video','application_url']

class DefectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating defect details"""
    status = serializers.ChoiceField(choices=['OPEN', 'CLOSED', 'REOPEN'])
    mentor_state = serializers.ChoiceField(choices=['Pending', 'Approved', 'Invalid'])
    defect_screenshots = serializers.ListField(
        child=serializers.ImageField(required=False, allow_null=True),
        required=False,
        allow_null=True,
        write_only=True
    )
    defect_video = serializers.FileField(required=False, allow_null=True)
    severity = serializers.CharField()  
    priority = serializers.CharField() 
    
    class Meta:
        model = Defect
        fields = ['summary', 'priority', 'actual_result', 'expected_result', 'environment', 
                 'application_url', 'mentor_state', 'defect_screenshots','defect_video', 'status', 
                 'steps_to_reproduce', 'severity']
    
    def update(self, instance, validated_data):
        # Handle defect_screenshots field separately
        defect_screenshots = validated_data.pop('defect_screenshots', [])
        defect_video = validated_data.pop('defect_video', None) 
        
        # Track changes to fields
        changes = {}
        for field, new_value in validated_data.items():
            old_value = getattr(instance, field)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
            setattr(instance, field, new_value)
        
        # Handle new screenshots
        if defect_screenshots:
            # Clear existing screenshots and add new ones
            instance.screenshots.all().delete()
            for screenshot_file in defect_screenshots:
                if screenshot_file:
                    instance.add_screenshot(screenshot_file)
            changes['defect_screenshots'] = {'old': 'existing', 'new': 'updated'}

        # Handle video update
        if defect_video is not None:
            if defect_video == '':
                if instance.defect_video:
                    instance.defect_video.delete(save=False)
                instance.defect_video = None
                changes['defect_video'] = {'old': 'exists', 'new': 'removed'}
            else:
                if instance.defect_video:
                    instance.defect_video.delete(save=False)
                instance.defect_video = defect_video
                changes['defect_video'] = {'old': 'exists', 'new': 'updated'}
        
        instance.save()
        
        if changes:
            DefectHistory.objects.create(
                defect=instance,
                action='UPDATED',
                performed_by=self.context['request'].user,
                changes=changes,
                comments='Updated defect details'
            )
        return instance

# ... rest of your serializers remain the same ...
class MentorSerializer(serializers.ModelSerializer):
    """Serializer for mentor information"""
    projects = ProjectSerializer(many=True, read_only=True)

    class Meta:
        model = Mentor
        fields = ['id', 'mentor_username', 'projects', 'is_active']

class DefectStatsSerializer(serializers.Serializer):
    """Serializer for defect statistics"""
    total_defects = serializers.IntegerField(help_text="Total number of defects")
    approved_defects = serializers.IntegerField(help_text="Number of approved defects")
    pending_defects = serializers.IntegerField(help_text="Number of pending defects")
    invalid_defects = serializers.IntegerField(help_text="Number of invalid defects")
    defects_by_priority = serializers.DictField(
        help_text="Breakdown of defects by priority level",
        child=serializers.IntegerField()
    )
class MentorLoginSerializer(serializers.Serializer):
    """Serializer for mentor login"""
    username = serializers.CharField(
        max_length=100,
        help_text="Mentor username (not the Django user username)"
    )
    password = serializers.CharField(
        write_only=True,
        help_text="Mentor password"
    )
class DefectActionSerializer(serializers.Serializer):
    """Serializer for defect approval/invalidation actions"""
    comments = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional comments for the action"
    )