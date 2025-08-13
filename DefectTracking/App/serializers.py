from rest_framework import serializers
from django.contrib.auth.models import User
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .models import Project, UserProfile, Defect, Mentor, DefectHistory
class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for Project model"""
    class Meta:
        model = Project
        fields = ['id', 'name']
class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration using username, email, password, confirm_password, and project."""
    username = serializers.CharField(
        max_length=150,
        help_text="User's username"
    )
    email = serializers.EmailField(
        help_text="User's email address"
    )
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.filter(is_active=True))
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password', 'project']
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
        project = validated_data.pop('project')
        user = User.objects.create_user(**validated_data)
        user.is_active = True
        user.save()
        UserProfile.objects.create(user=user, project=project)
        return user
class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login with username/email and password
    """
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
        fields = ['project', 'project_name', 'email', 'username', 'firebase_uid']
class DefectSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField() 
    project_name = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='reported_by.username', read_only=True)
    severity = serializers.CharField()
    priority = serializers.CharField()
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
    class Meta:
        model = Defect
        fields = '__all__'
        read_only_fields = ['defect_id', 'summary', 'status', 'reported_by',
            'severity', 'priority', 'created_at']
class DefectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new defects"""
    class Meta:
        model = Defect
        fields = ['project', 'summary', 'priority', 'steps_to_reproduce', 'actual_result', 'expected_result']
    def validate_summary(self, value):
        """Validate summary length and content"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Summary must be at least 10 characters long")
        return value.strip()
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        defect = Defect.objects.create(**validated_data)
        DefectHistory.objects.create(
            defect=defect,
            action='CREATED',
            performed_by=self.context['request'].user,
            comments='Defect created'
        )
        return defect
class DefectListSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='created_by.username', read_only=True)
    severity = serializers.CharField(read_only=True)
    priority = serializers.CharField(read_only=True)
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
            'created_at'
        ]
class DefectDetailSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source='project.name', read_only=True)
    reported_by = serializers.CharField(source='created_by.username', read_only=True)
    approved_by = serializers.CharField(source='approved_by.username', read_only=True, default=None)
    class Meta:
        model = Defect
        fields = [  'defect_id', 'project', 'summary', 'priority', 'steps_to_reproduce',
                    'actual_result', 'expected_result', 'status', 'reported_by', 'approved_by',
                    'created_at', 'updated_at', 'approved_at']
        read_only_fields = ['defect_id', 'project', 'reported_by', 'approved_by', 'created_at', 'updated_at', 'approved_at']
class DefectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating defect details"""
    class Meta:
        model = Defect
        fields = ['summary', 'priority', 'actual_result', 'expected_result']
    def update(self, instance, validated_data):
        changes = {}
        for field, new_value in validated_data.items():
            old_value = getattr(instance, field)
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if changes:
            DefectHistory.objects.create(
                defect=instance,
                action='UPDATED',
                performed_by=self.context['request'].user,
                changes=changes,
                comments='Defect updated'
            )
        return instance
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