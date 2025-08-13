from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
try:
    schema_view = get_schema_view(
        openapi.Info(
            title="Defect Tracking Tool API",
            default_version='v1',
            description="API for managing defects in software projects",
            contact=openapi.Contact(email="support@nammaqa.com"),
            license=openapi.License(name="MIT License"),
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
    )
except Exception as e:
    print(f"Error creating schema view: {e}")
    schema_view = None
