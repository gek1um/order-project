"""Roles y membresías sin sustituir AUTH_USER_MODEL."""
from django.conf import settings
from django.db import models
from django.db.models import Q, F


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    PROJECT_USER = "PROJECT_USER", "Usuario de proyecto"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_profile")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PROJECT_USER)

    class Meta:
        db_table = "user_project_profiles"


class ProjectMembership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="user_memberships")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_memberships"
        constraints = [models.UniqueConstraint(fields=["user", "project"], name="unique_project_user_membership")]
        ordering = ["project_id", "user_id"]
