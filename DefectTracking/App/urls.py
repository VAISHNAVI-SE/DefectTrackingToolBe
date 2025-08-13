# App/urls.py (or your main app's urls.py)
from django.urls import path, re_path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import similar_defects_view
from .import views 
try:
    from .swagger import schema_view
    SWAGGER_AVAILABLE = True
except ImportError as e:
    print(f"Swagger import error: {e}")
    SWAGGER_AVAILABLE = False
    schema_view = None
urlpatterns = [
    # Authentication
    path('auth/login/', views.user_login, name='user_login'),
    path('auth/mentor-login/', views.mentor_login, name='mentor_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.register_user, name='register'),
    # Projects
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    # Defects
    path('defects/', views.DefectListCreateView.as_view(), name='defect_list_create'),
    path('defects/<int:defect_id>/', views.DefectDetailView.as_view(), name='defect_detail'),
    path('defects/<int:defect_id>/approve/', views.approve_defect, name='approve_defect'),
    path('defects/<int:defect_id>/invalidate/', views.invalidate_defect, name='invalidate_defect'),
    path('defects/stats/', views.defect_stats, name='defect_stats'),
    path('api/defects/similar/', similar_defects_view, name='similar-defects'),
    # Mentors
    path('mentor/projects/', views.MentorProjectsView.as_view(), name='mentor_projects'),
    path('mentor/defects/', views.mentor_student_defects, name='mentor_student_defects'),
    path('mentor/students/', views.mentor_students_view, name='mentor_students'),
    path('mentor/projects/', views.mentor_projects, name='mentor-projects'),
    path('mentor/projects/<int:project_id>/defects/', views.mentor_project_defects, name='mentor_project_defects'),
    path('mentor/defects/<int:defect_id>/', views.mentor_defect_detail, name='mentor-defect-detail'),
    path('mentor/defects/<int:defect_id>/approve/', views.mentor_defect_approve, name='mentor-defect-approve'),
    path('mentor/defects/<int:defect_id>/invalidate/', views.mentor_defect_invalidate, name='mentor-defect-invalidate'),
    #Clients
    path('client/unique-defects/', views.client_unique_defects_view, name='client_unique_defects'),
    path('client/login/', views.ClientLoginView.as_view(), name='client_login'),
    path('client/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('client/projects/', views.client_projects, name='client_projects'),
    path('client/projects/<int:project_id>/defects/', views.client_project_defects, name='client_project_defects'),
    # User Profile
    path('user/profile/', views.user_profile, name='user_profile'),
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
]
# Add Swagger URLs only if available
if SWAGGER_AVAILABLE and schema_view:
    urlpatterns += [
        re_path(r'^swagger(?P<format>\.json|\.yaml)$', 
                schema_view.without_ui(cache_timeout=0), name='schema-json'),
        re_path(r'^swagger/$', 
                schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        re_path(r'^redoc/$', 
                schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]