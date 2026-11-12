"""Administración de usuarios y proyectos autorizada por sesión y rol.

La autorización global de los otros módulos se aplicará en Fase 8.1.3.
"""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_GET

from projects.models import Project
from .models import ProjectMembership, UserProfile, UserRole


def effective_role(user):
    if user.is_superuser:
        return UserRole.ADMIN
    profile = UserProfile.objects.filter(user_id=user.pk).first()
    return profile.role if profile else UserRole.PROJECT_USER


def identity(user):
    return {"id": user.pk, "username": user.get_username(),
            "first_name": user.first_name, "last_name": user.last_name,
            "email": user.email, "role": effective_role(user),
            "is_staff": user.is_staff, "is_superuser": user.is_superuser}


def access_error(request, admin=False):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"detail": "Autenticación requerida."}, status=401)
    if admin and effective_role(request.user) != UserRole.ADMIN:
        return JsonResponse({"detail": "Solo los administradores pueden realizar esta operación."}, status=403)
    return None


def parse_json(request):
    if request.content_type != "application/json":
        return None, JsonResponse({"detail": "Se requiere application/json."}, status=415)
    try:
        obj = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse({"detail": "JSON inválido."}, status=400)
    if not isinstance(obj, dict):
        return None, JsonResponse({"detail": "Se espera un objeto JSON."}, status=400)
    return obj, None


def membership_dict(m):
    return {"id": m.pk, "user": m.user_id, "username": m.user.username,
            "project": m.project_id, "project_code": m.project.code,
            "project_name": m.project.name, "created_at": m.created_at.isoformat()}


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def users(request):
    if error := access_error(request, admin=True):
        return error
    User = get_user_model()
    if request.method == "GET":
        return JsonResponse({"results": [identity(u) for u in User.objects.all().order_by("id")]})
    data, error = parse_json(request)
    if error is not None:
        return error
    username, password = data.get("username"), data.get("password")
    role = data.get("role", UserRole.PROJECT_USER)
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str):
        return JsonResponse({"detail": "username y password son obligatorios."}, status=400)
    username = username.strip()
    if role not in UserRole.values:
        return JsonResponse({"role": ["Rol inválido."]}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({"username": ["El usuario ya existe."]}, status=400)
    new_user = User(username=username, email=str(data.get("email", "")).strip())
    try:
        validate_password(password, user=new_user)
    except ValidationError as exc:
        return JsonResponse({"password": exc.messages}, status=400)
    with transaction.atomic():
        try:
            new_user.set_password(password)
            new_user.save()
            UserProfile.objects.create(user=new_user, role=role)
        except IntegrityError:
            return JsonResponse({"username": ["El usuario ya existe."]}, status=400)
    return JsonResponse({"user": identity(new_user)}, status=201)


@never_cache
@csrf_protect
@require_http_methods(["PATCH"])
def user_role(request, user_id):
    if error := access_error(request, admin=True):
        return error
    data, error = parse_json(request)
    if error is not None:
        return error
    role = data.get("role")
    if role not in UserRole.values:
        return JsonResponse({"role": ["Rol inválido."]}, status=400)
    target = get_object_or_404(get_user_model(), pk=user_id)
    if target.is_superuser:
        return JsonResponse({"detail": "El rol de un superusuario no se modifica desde esta API."}, status=403)
    if request.user.pk == target.pk and role != UserRole.ADMIN:
        return JsonResponse({"detail": "No puedes retirar tu propio rol de administrador."}, status=403)
    with transaction.atomic():
        UserProfile.objects.update_or_create(user=target, defaults={"role": role})
    return JsonResponse({"user": identity(target)})


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def memberships(request):
    if error := access_error(request, admin=True):
        return error
    if request.method == "GET":
        rows = ProjectMembership.objects.select_related("user", "project")
        project = request.GET.get("project")
        user = request.GET.get("user")
        if project:
            if not project.isdecimal():
                return JsonResponse({"project": ["Se requiere un ID numérico."]}, status=400)
            rows = rows.filter(project_id=int(project))
        if user:
            if not user.isdecimal():
                return JsonResponse({"user": ["Se requiere un ID numérico."]}, status=400)
            rows = rows.filter(user_id=int(user))
        return JsonResponse({"results": [membership_dict(m) for m in rows]})
    data, error = parse_json(request)
    if error is not None:
        return error
    user_id, project_id = data.get("user"), data.get("project")
    if type(user_id) is not int or type(project_id) is not int or user_id < 1 or project_id < 1:
        return JsonResponse({"detail": "user y project deben ser IDs enteros positivos."}, status=400)
    user = get_object_or_404(get_user_model(), pk=user_id)
    project = get_object_or_404(Project, pk=project_id)
    try:
        with transaction.atomic():
            member, created = ProjectMembership.objects.get_or_create(user=user, project=project)
    except IntegrityError:
        return JsonResponse({"detail": "No fue posible crear la membresía."}, status=409)
    member = ProjectMembership.objects.select_related("user", "project").get(pk=member.pk)
    return JsonResponse({"membership": membership_dict(member)}, status=201 if created else 200)


@never_cache
@csrf_protect
@require_http_methods(["DELETE"])
def membership_detail(request, membership_id):
    if error := access_error(request, admin=True):
        return error
    member = get_object_or_404(ProjectMembership, pk=membership_id)
    member.delete()
    return JsonResponse({}, status=204)


@never_cache
@require_GET
def my_projects(request):
    if error := access_error(request):
        return error
    projects = Project.objects.all() if effective_role(request.user) == UserRole.ADMIN else Project.objects.filter(user_memberships__user=request.user)
    return JsonResponse({"role": effective_role(request.user), "results": [
        {"id": p.pk, "code": p.code, "name": p.name} for p in projects.order_by("id")
    ]})
