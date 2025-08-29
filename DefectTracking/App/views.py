from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Count, Q, OuterRef, Subquery, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Project, UserProfile, Defect, Mentor, DefectHistory
from .serializers import (ProjectSerializer, UserRegistrationSerializer, DefectSerializer,DefectCreateSerializer, DefectUpdateSerializer, MentorSerializer,
    DefectStatsSerializer, UserProfileSerializer, MentorLoginSerializer,DefectActionSerializer, UserLoginSerializer, DefectListSerializer,DefectDetailSerializer)
from .permissions import IsMentor
from django.conf import settings
from .ai_utils import ai_filter_unique_defects

AI_FILTER_UNIQUE_DEFECTS_THRESHOLD = 0.3  # Centralized threshold for AI clustering
class ProjectListView(generics.ListAPIView):
    """Get list of all active projects"""
    queryset = Project.objects.filter(is_active=True)
    serializer_class = ProjectSerializer
    permission_classes = [AllowAny]
    @swagger_auto_schema(
        operation_description="Get list of all active projects",
        responses={200: ProjectSerializer(many=True), 500: "Internal server error"},
        tags=['Projects'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
@swagger_auto_schema(
    method='post',
    operation_description="Register a new user",
    request_body=UserRegistrationSerializer,
    responses={
        201: openapi.Response(
            description="Registration successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                })),
        400: "Validation errors"},
    tags=['Authentication'])
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            return Response({
                'message': 'Registration successful! User account created.',
                'user_id': user.id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Registration failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
@swagger_auto_schema(
    method='post',
    operation_description="User login with username/email and password",
    request_body=UserLoginSerializer,
    responses={
        200: openapi.Response(
            description="Login successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING, description="JWT access token"),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description="JWT refresh token"),
                    'user': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'username': openapi.Schema(type=openapi.TYPE_STRING),
                            'email': openapi.Schema(type=openapi.TYPE_STRING),
                            'role': openapi.Schema(type=openapi.TYPE_STRING, description="User role"),
                            'is_mentor': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            })})),
        400: "Invalid credentials"},
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def user_login(request):
    """User login endpoint"""
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    username_or_email = serializer.validated_data['username']
    password = serializer.validated_data['password']
    user = None
    try:
        if '@' in username_or_email:
            user_obj = User.objects.get(email__iexact=username_or_email, is_active=True)
        else:
            user_obj = User.objects.get(username__iexact=username_or_email, is_active=True)
        if user_obj.check_password(password):
            user = user_obj
    except User.DoesNotExist:
        pass
    if user and user.is_active:
        try:
            user_profile = UserProfile.objects.get(user=user)
            role = user_profile.role
        except UserProfile.DoesNotExist:
            role = None
        is_mentor = Mentor.objects.filter(user=user, is_active=True).exists()
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': role,
                'is_mentor': is_mentor,}})
    else:
        return Response({'error': 'Invalid credentials'}, status=400)
@swagger_auto_schema(
    method='post',
    operation_description="Mentor login with mentor username and password",
    request_body=MentorLoginSerializer,
    responses={
        200: openapi.Response(
            description="Login successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING, description="JWT access token"),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description="JWT refresh token"),
                    'user': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'username': openapi.Schema(type=openapi.TYPE_STRING),
                            'is_mentor': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            'mentor_username': openapi.Schema(type=openapi.TYPE_STRING),})})),
        400: "Invalid credentials"},
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def mentor_login(request):
    """Mentor login endpoint"""
    serializer = MentorLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    mentor_username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    try:
        mentor = Mentor.objects.get(mentor_username=mentor_username, is_active=True)
        user = authenticate(username=mentor.user.username, password=password)
        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'is_mentor': True,
                    'mentor_username': mentor.mentor_username}})
        else:
            return Response({'error': 'Invalid credentials'}, status=400)
    except Mentor.DoesNotExist:
        return Response({'error': 'Invalid mentor credentials'}, status=400)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
def mentor_projects(request):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': 'Unauthorized: Not a mentor'}, status=403)
    projects = mentor.projects.filter(is_active=True)
    serializer = ProjectSerializer(projects, many=True)
    return Response(serializer.data)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
def get_defect_detail(request, defect_id):
    mentor = Mentor.objects.get(user=request.user)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__mentors=mentor)
    serializer = DefectDetailSerializer(defect, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
def mentor_project_defects(request, project_id):
    try:
        mentor = Mentor.objects.get(user=request.user)
        if not mentor.projects.filter(id=project_id).exists():
            return Response({'error': 'Project not assigned to this mentor'}, status=403)
        defects = Defect.objects.filter(project_id=project_id)
        serializer = DefectListSerializer(defects, many=True, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
def mentor_defect_detail(request, defect_id):
    mentor = Mentor.objects.get(user=request.user)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__mentors=mentor)
    
    if request.method == 'GET':
        serializer = DefectDetailSerializer(defect)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        # For file uploads, we need to use request.data directly
        if request.content_type.startswith('multipart/form-data'):
            serializer = DefectUpdateSerializer(defect, data=request.data, partial=True)
        else:
            serializer = DefectUpdateSerializer(defect, data=request.data, partial=True)
            
        if serializer.is_valid():
            serializer.save()
            # Log update in DefectHistory
            DefectHistory.objects.create(
                defect=defect,
                action='UPDATED',
                performed_by=request.user,
                changes=serializer.validated_data,
                comments=request.data.get('comments', '')
            )
            return Response({'success': True, 'defect': DefectDetailSerializer(defect).data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
@transaction.atomic
def mentor_defect_approve(request, defect_id):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': 'Only mentors can approve defects'}, status=403)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__mentors=mentor)
    if defect.status == 'APPROVED':
        return Response({'error': 'Already approved'}, status=400)
    defect.status = 'APPROVED'
    defect.mentor_state = 'Approved'
    defect.approved_by = request.user
    defect.approved_at = timezone.now()
    defect.save()
    DefectHistory.objects.create(
        defect=defect,
        action='APPROVED',
        performed_by=request.user,
        comments=request.data.get('comments', 'Defect approved by mentor'))
    return Response({'success': True, 'defect': DefectDetailSerializer(defect).data})
@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated, IsMentor])
@transaction.atomic
def mentor_defect_invalidate(request, defect_id):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': 'Only mentors can invalidate defects'}, status=403)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__mentors=mentor)
    if defect.status == 'INVALID':
        return Response({'error': 'Already invalidated'}, status=400)
    defect.status = 'INVALID'
    defect.mentor_state = 'Invalid'
    defect.save()
    DefectHistory.objects.create(
        defect=defect,
        action='INVALIDATED',
        performed_by=request.user,
        comments=request.data.get('comments', 'Defect marked as invalid by mentor'))
    return Response({'success': True, 'defect': DefectDetailSerializer(defect).data})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mentor_student_defects(request):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': "Not a mentor"}, status=403)
    student_profiles = UserProfile.objects.filter(project__in=mentor.projects.all(), role='student').select_related('user')
    student_users = [profile.user for profile in student_profiles]
    defects = Defect.objects.filter(created_by__in=student_users)
    serializer = DefectListSerializer(defects, many=True)
    data = [{
        "defect_id": d.defect_id,
        "summary": d.summary,
        "status": d.status,
        "project": d.project.name,
        "reported_by": d.created_by.username,  # <--- Here
        "created_at": d.created_at,
    } for d in defects]
    return Response(serializer.data)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMentor])
def mentor_students_view(request):
    try:
        user_profile = request.user.userprofile
        if user_profile.role != "mentor":
            return Response({"detail": "Permission denied, not a mentor"}, status=403)
    except UserProfile.DoesNotExist:
        return Response({"detail": "Mentor profile not found"}, status=404)
    mentor = Mentor.objects.get(user=request.user)
    students = mentor.students.select_related('user','project')
    mentor_projects = request.user.mentor.projects.all()
    student_profiles = UserProfile.objects.filter(project__in=mentor_projects.all(), role='student').select_related('user','project')
    students = UserProfile.objects.filter(project__in=mentor_projects, role="student").select_related('user','project')
    data = []
    for student in students:
        defects = Defect.objects.filter(created_by=student.user)
        data.append({
            "student_id": student.user.id,
            "student_username": student.user.username,
            "project": student.project.name if student.project else None,
            "defects": [{   "defect_id": d.defect_id,
                    "summary": d.summary,
                    "status": d.status,
                    "reported_by": d.created_by.username,
                    "created_at": d.created_at,}
                for d in defects]})
        return Response(data)
class DefectListAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Optional: enforce login

    def get(self, request, *args, **kwargs):
        defects = Defect.objects.all()
        serializer = DefectListSerializer(defects, many=True, context={'request': request})
        return Response(serializer.data)
class DefectListCreateView(generics.ListCreateAPIView):
    """List defects and create new defects"""
    queryset = Defect.objects.all()
    serializer_class = DefectSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Get list of defects based on user role",
        manual_parameters=[openapi.Parameter(
                'project',
                openapi.IN_QUERY,
                description="Filter by project ID (mentors only)",
                type=openapi.TYPE_INTEGER,
                required=False)],
        responses={200: DefectSerializer(many=True), 401: "Authentication required"},
        tags=['Defects'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    @swagger_auto_schema(
        operation_description="Create a new defect",
        request_body=DefectCreateSerializer,
        responses={201: DefectSerializer,
            400: "Validation errors",
            401: "Authentication required"},
        tags=['Defects']
    )
    def post(self, request, *args, **kwargs):
        serializer = DefectCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    def get_queryset(self):
        queryset = Defect.objects.all()
        try:
            mentor = Mentor.objects.get(user=self.request.user)
            project_id = self.request.query_params.get('project')
            if project_id:
                queryset = queryset.filter(project_id=project_id, project__in=mentor.projects.all())
            else:
                queryset = queryset.filter(project__in=mentor.projects.all())
        except Mentor.DoesNotExist:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset.select_related('project', 'created_by__userprofile', 'approved_by__userprofile')
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DefectCreateSerializer
        return DefectSerializer
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def similar_defects_view(request):
    """Given a text query, return a list of similar defects.Query param: q - the text to match against defect summaries and actual/expected results"""
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'error': 'Query parameter "q" is required.'}, status=400)
    defects = (
        Defect.objects.filter(summary__icontains=query) |
        Defect.objects.filter(actual_result__icontains=query) |
        Defect.objects.filter(expected_result__icontains=query)
    ).distinct()[:10]
    serializer = DefectSerializer(defects, many=True)
    return Response(serializer.data)
class DefectDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update defect details"""
    serializer_class = DefectSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'defect_id'
    @swagger_auto_schema(
        operation_description="Get detailed information about a specific defect",
        responses={200: DefectSerializer, 404: "Defect not found", 403: "Permission denied"},
        tags=['Defects']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update defect details (mentors only)",
        request_body=DefectUpdateSerializer,
        responses={200: DefectSerializer, 400: "Validation errors", 403: "Permission denied", 404: "Defect not found"},
        tags=['Defects']
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Partially update defect details (mentors only)",
        request_body=DefectUpdateSerializer,
        responses={200: DefectSerializer, 400: "Validation errors", 403: "Permission denied", 404: "Defect not found"},
        tags=['Defects']
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    def get_queryset(self):
        try:
            mentor = Mentor.objects.get(user=self.request.user)
            return Defect.objects.filter(project__in=mentor.projects.all())
        except Mentor.DoesNotExist:
            return Defect.objects.filter(created_by=self.request.user)
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DefectUpdateSerializer
        return DefectSerializer
@swagger_auto_schema(
    method='patch',
    operation_description="Approve a defect (mentor only)",
    request_body=DefectActionSerializer,
    responses={
        200: openapi.Response(
            description="Defect approved successfully",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'message': openapi.Schema(type=openapi.TYPE_STRING)})
        ),
        403: "Permission denied - Only mentors can approve defects",
        404: "Defect not found"
    },
    tags=['Defects']
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def approve_defect(request, defect_id):
    """Approve a defect"""
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': 'Only mentors can approve defects'}, status=403)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__in=mentor.projects.all())
    if defect.status == 'APPROVED':
        return Response({'message': 'Defect already approved'})
    defect.status = 'APPROVED'
    defect.approved_by = request.user
    defect.approved_at = timezone.now()
    defect.save()
    comments = request.data.get('comments', 'Defect approved by mentor')
    DefectHistory.objects.create(
        defect=defect,
        action='APPROVED',
        performed_by=request.user,
        comments=comments
    )
    return Response({'message': 'Defect approved successfully'})
@swagger_auto_schema(
    method='patch',
    operation_description="Mark a defect as invalid (mentor only)",
    request_body=DefectActionSerializer,
    responses={
        200: openapi.Response(
            description="Defect marked as invalid",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'message': openapi.Schema(type=openapi.TYPE_STRING)})
        ),
        403: "Permission denied - Only mentors can invalidate defects",
        404: "Defect not found"
    },
    tags=['Defects']
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def invalidate_defect(request, defect_id):
    """Mark a defect as invalid"""
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        return Response({'error': 'Only mentors can invalidate defects'}, status=403)
    defect = get_object_or_404(Defect, defect_id=defect_id, project__in=mentor.projects.all())
    if defect.status == 'INVALID':
        return Response({'message': 'Defect already marked as invalid'})
    defect.status = 'INVALID'
    defect.save()
    comments = request.data.get('comments', 'Defect marked as invalid by mentor')
    DefectHistory.objects.create(
        defect=defect,
        action='INVALIDATED',
        performed_by=request.user,
        comments=comments)
    return Response({'message': 'Defect marked as invalid'})
@swagger_auto_schema(
    method='get',
    operation_description="Get defect statistics",
    responses={200: DefectStatsSerializer, 401: "Authentication required"},
    tags=['Defects']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def defect_stats(request):
    """Get defect statistics"""
    try:
        mentor = Mentor.objects.get(user=request.user)
        queryset = Defect.objects.filter(project__in=mentor.projects.all())
    except Mentor.DoesNotExist:
        queryset = Defect.objects.filter(created_by=request.user)

    total_defects = queryset.count()
    approved_defects = queryset.filter(status='APPROVED').count()
    pending_defects = queryset.filter(status='PENDING').count()
    invalid_defects = queryset.filter(status='INVALID').count()

    priority_stats = queryset.values('priority').annotate(count=Count('priority'))
    defects_by_priority = {item['priority']: item['count'] for item in priority_stats}
    stats = {
        'total_defects': total_defects,
        'approved_defects': approved_defects,
        'pending_defects': pending_defects,
        'invalid_defects': invalid_defects,
        'defects_by_priority': defects_by_priority
    }
    return Response(stats)
class MentorProjectsView(generics.RetrieveAPIView):
    """Get mentor's assigned projects"""
    serializer_class = MentorSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Get mentor's assigned projects",
        responses={200: MentorSerializer, 403: "User is not a mentor", 401: "Authentication required"},
        tags=['Mentors']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    def get_object(self):
        try:
            return Mentor.objects.get(user=self.request.user)
        except Mentor.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('User is not a mentor')
@swagger_auto_schema(
    method='get',
    operation_description="Get current user profile information",
    responses={200: UserProfileSerializer, 404: "Profile not found", 401: "Authentication required"},
    tags=['User Profile']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)
    except UserProfile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    """User Dashboard API"""
    defects = (
        Defect.objects.filter(created_by=request.user)
        .values('project__name')
        .annotate(
            num_defects=Count('defect_id'),
            num_approved=Count('defect_id', filter=Q(status='APPROVED')),
            num_invalid=Count('defect_id', filter=Q(status='INVALID'))
        )
        .order_by('project__name')
    )
    dashboard = []
    for idx, row in enumerate(defects, 1):
        dashboard.append({
            'sl_no': idx,
            'project_name': row['project__name'],
            'num_defects': row['num_defects'],
            'num_approved': row['num_approved'],
            'num_invalid': row['num_invalid'],
        })
    return Response(dashboard)
class ClientLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            return Response({'error': 'User profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if profile.role != 'client':
            return Response({'error': 'User is not a client.'}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        projects = list(profile.projects.values('id', 'name'))

        return Response({
            'message': 'Login successful.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user_id': user.id,
            'username': user.username,
            'role': profile.role,
            'project': projects
        }, status=status.HTTP_200_OK)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_projects(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=404)

    if profile.role != 'client':
        return Response({'error': 'User is not a client.'}, status=403)

    projects = profile.projects.filter(is_active=True).distinct()
    project_list = [{'id': p.id, 'name': p.name} for p in projects]
    return Response(project_list)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_project_defects(request, project_id):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=404)
    if profile.role != 'client':
        return Response({'error': 'User is not a client.'}, status=403)
    project = get_object_or_404(profile.projects, id=project_id)
    defects_qs = Defect.objects.filter(project=project, status='APPROVED')
    serializer = DefectListSerializer(defects_qs, many=True, context={'request': request})
    defect_dicts = serializer.data
    # --------- USE AI CLUSTERING HERE ---------
    unique_defects = ai_filter_unique_defects(defect_dicts, AI_FILTER_UNIQUE_DEFECTS_THRESHOLD)
    return Response({
        'project': project.name,
        'defects': unique_defects
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_unique_defects_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=404)

    if profile.role != 'client':
        return Response({'error': 'User is not a client.'}, status=403)

    # Fetch all defects for client projects
    defects = list(Defect.objects.filter(project__in=profile.projects.all()).values(
        'defect_id', 'summary', 'status', 'created_at', 'steps_to_reproduce', 'actual_result', 'expected_result','environment'
    ))
    defects_list = list(defects)

    # Apply AI-based filtering to get unique defects
    unique_defects = ai_filter_unique_defects(defects,AI_FILTER_UNIQUE_DEFECTS_THRESHOLD)

    return Response({'unique_defects': unique_defects})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_dashboard(request):
    try:
        profile = request.user.userprofile
    except Exception:
        return Response({'error': 'User profile not found.'}, status=404)
    if profile.role != 'client':
        return Response({'error': 'User is not a client.'}, status=403)
    projects = profile.projects.all()
    if not projects:
        return Response({'error': 'No project assigned to this client.'}, status=404)
    result = []
    for project in projects:
        defects = list(Defect.objects.filter(
            project=project,
            status='APPROVED',
            created_by=request.user
        ).values(
            'defect_id',
            'summary',
            'status',
            'created_by__username',
            'priority',
            'created_at',
            'environment',
            'application_url',
            'defect_screenshots',
            'defect_video'
        ))
        for d in defects:
            if d['defect_video']:
                d['defect_video'] = request.build_absolute_uri(settings.MEDIA_URL + d['defect_video'])
            if d['defect_screenshots']:
                d['defect_screenshots'] = request.build_absolute_uri(settings.MEDIA_URL + d['defect_screenshots'])
        # --------- USE AI CLUSTERING HERE ---------
        unique_defects = ai_filter_unique_defects(list(defects),AI_FILTER_UNIQUE_DEFECTS_THRESHOLD)
        result.append({
            'project': project.name,
            'defects': unique_defects
        })
    return Response(result)
#

