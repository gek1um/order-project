
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Health Check
    path("api/", include("core.urls")),

    # Projects API
    path("api/", include("projects.urls")),

    # Tasks API
    path("api/", include("tasks.urls")),
]
