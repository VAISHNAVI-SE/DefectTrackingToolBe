from rest_framework import  permissions
from .models import Mentor
class IsMentor(permissions.BasePermission):
    def has_permission(self, request, view):
        return Mentor.objects.filter(user=request.user).exists()