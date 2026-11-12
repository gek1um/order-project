"""Endpoints de sesión para el frontend Vue.

El inicio y cierre de sesión usan vistas Django (no @api_view de DRF),
para garantizar la protección CSRF también en las peticiones anónimas.
"""

import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


def _identity(user):
    from .role_views import identity
    return identity(user)


def _read_json(request):
    if request.content_type != "application/json":
        return None, JsonResponse(
            {"detail": "El cuerpo debe enviarse como application/json."}, status=415
        )
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse({"detail": "JSON inválido."}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({"detail": "Se espera un objeto JSON."}, status=400)
    return data, None


@never_cache
@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    """Solicita cookie CSRF y expone el token para el encabezado X-CSRFToken."""
    return JsonResponse({"csrfToken": get_token(request)})


@never_cache
@csrf_protect
@require_POST
def session_login(request):
    data, error = _read_json(request)
    if error is not None:
        return error
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return JsonResponse({"detail": "Usuario y contraseña son obligatorios."}, status=400)

    user = authenticate(request, username=username.strip(), password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": "Credenciales inválidas."}, status=401)

    login(request, user)
    # Django rota el token CSRF al iniciar sesión. Entregamos el token actualizado.
    return JsonResponse({"user": _identity(user), "csrfToken": get_token(request)})


@never_cache
@require_GET
def session_me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "No autenticado."}, status=401)
    return JsonResponse({"user": _identity(request.user)})


@never_cache
@csrf_protect
@require_POST
def session_logout(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "No autenticado."}, status=401)
    logout(request)
    return JsonResponse({"detail": "Sesión cerrada correctamente."})
