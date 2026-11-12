from django.urls import path

from .auth_views import csrf_token, session_login, session_logout, session_me
from .role_views import users, user_role, memberships, membership_detail, my_projects
from .views import health_check

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("auth/csrf/", csrf_token, name="auth-csrf"),
    path("auth/login/", session_login, name="auth-login"),
    path("auth/me/", session_me, name="auth-me"),
    path("auth/logout/", session_logout, name="auth-logout"),
    path("auth/users/", users, name="auth-users"),
    path("auth/users/<int:user_id>/role/", user_role, name="auth-user-role"),
    path("auth/project-memberships/", memberships, name="auth-project-memberships"),
    path("auth/project-memberships/<int:membership_id>/", membership_detail, name="auth-project-membership-detail"),
    path("auth/my-projects/", my_projects, name="auth-my-projects"),
]
