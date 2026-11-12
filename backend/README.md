# Backend — order-project

API REST de **order-project**, construida con **Django 5.2**, **Django REST Framework** y **PostgreSQL**. Implementa planificación y validaciones de negocio, administración de recursos, solicitudes de cambio, KPI y autorización por proyecto.

[Volver al README general](../README.md) · [Documentación del frontend](../frontend/README.md)

## Tecnologías

Las dependencias observadas en `requirements.txt` incluyen:

| Paquete | Versión observada |
| --- | --- |
| Django | `5.2.18` |
| djangorestframework | `3.18.3` |
| psycopg / psycopg-binary | `3.3.6` |
| django-cors-headers | `4.9.0` |
| python-dotenv | `1.2.4` |

Consultar `backend/requirements.txt` para la lista completa y las versiones del repositorio instalado.

## Organización de código

```text
backend/
├── config/             # settings.py, urls.py, ASGI y WSGI
├── core/               # Salud, autenticación, roles, membresías y autorización
├── projects/           # Proyectos, hitos/KPI, recursos/costos, cambios/dashboards API
├── tasks/              # Actividades, datos reales y avance
├── scheduling/         # Dependencias, calendarios y propagación de cronogramas
├── manage.py
├── requirements.txt
└── README.md
```

## Configuración local

### 1. PostgreSQL

La configuración de Django revisada utiliza `127.0.0.1` como host de PostgreSQL y el puerto indicado por `POSTGRES_PORT` (predeterminado: **5433**). Requiere que la base esté disponible antes de ejecutar migraciones o pruebas.

El archivo de variables de entorno se carga en la **raíz de `order-project`** (`PROJECT_ROOT / '.env'`). Ejemplo de contenido, **con credenciales ficticias**:

```dotenv
POSTGRES_DB=order_project
POSTGRES_USER=order_user
POSTGRES_PASSWORD=contraseña_local_de_ejemplo
POSTGRES_PORT=5433
DJANGO_SECRET_KEY=generar_una_clave_secreta_distinta
DJANGO_DEBUG=True
```

Los nombres, usuario, contraseña y puerto deben coincidir con PostgreSQL local o el contenedor que uses. No incluir el `.env` real en Git.

### 2. Entorno Python

PowerShell, desde la raíz:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3. Base de datos y arranque

```powershell
python manage.py check
python manage.py migrate
python manage.py runserver 8000
```

**API:** `http://localhost:8000/api/`.

**Comprobación de salud:** `GET http://localhost:8000/api/health/`.

### 4. Crear administrador inicial

```powershell
python manage.py createsuperuser
```

El superusuario tiene rol efectivo `ADMIN`. Puede administrar usuarios y asignar miembros a proyectos desde el frontend (`/admin/users`) una vez iniciada la sesión.

## Autenticación y autorización

La API emplea `SessionAuthentication` de DRF y una política global `IsAuthenticated`. Django ofrece autenticación por **cookie de sesión** y requiere **CSRF en escrituras autenticadas**.

- `ADMIN`: acceso general, gestión de usuarios y decisiones administrativas.
- `PROJECT_USER`: acceso limitado a los proyectos asignados mediante membresías.

Se protege el acceso tanto en listados/detalles como en IDs enviados para crear relaciones. Un recurso de proyecto ajeno puede responder `404` por diseño; acciones prohibidas pueden responder `403`.

| Método | Endpoint | Descripción |
| --- | --- | --- |
| `GET` | `/api/auth/csrf/` | Solicita token/cookie CSRF |
| `POST` | `/api/auth/login/` | Login por usuario/contraseña |
| `GET` | `/api/auth/me/` | Datos del usuario autenticado |
| `POST` | `/api/auth/logout/` | Cierre de sesión |
| `GET/POST` | `/api/auth/users/` | Administración de usuarios (ADMIN) |
| `PATCH` | `/api/auth/users/{id}/role/` | Cambio de rol (ADMIN) |
| `GET/POST` | `/api/auth/project-memberships/` | Listado/creación de membresías (ADMIN) |
| `DELETE` | `/api/auth/project-memberships/{id}/` | Revocar membresía (ADMIN) |
| `GET` | `/api/auth/my-projects/` | Proyectos accesibles |

**Ejemplo de login** (JSON):

```json
{
  "username": "admin",
  "password": "CONTRASEÑA_REAL_NO_COMPARTIR"
}
```

Obtener previamente CSRF, enviar `X-CSRFToken` en el POST y conservar las cookies en el cliente. No registrar cookies, tokens ni contraseñas en las evidencias públicas.

## APIs principales

Las rutas son relativas a `http://localhost:8000` y, salvo excepciones explícitas, requieren usuario autenticado.

| Endpoint base | Funcionalidad |
| --- | --- |
| `/api/projects/` | CRUD de proyectos y presupuesto inicial |
| `/api/tasks/` | CRUD de tareas y ejecución real |
| `/api/scheduling/dependencies/` | FS/SS/FF/SF y desfases |
| `/api/scheduling/calendars/` | Calendarios laborables |
| `/api/scheduling/exceptions/` | Excepciones/feriados |
| `/api/scheduling/projects/{id}/calendar/` | Calendario efectivo |
| `/api/scheduling/projects/{id}/calculate/` | Cálculo de calendario |
| `/api/scheduling/projects/{id}/schedule/` | Cronograma consolidado |
| `/api/scheduling/tasks/{id}/preview/` | Simulación sin escritura |
| `/api/scheduling/tasks/{id}/reschedule/` | Reprogramación confirmada |
| `/api/milestones/` | Hitos y tareas asociadas |
| `/api/milestone-kpis/` | KPI de hitos |
| `/api/resources/` | Catálogo de recursos |
| `/api/resource-assignments/` | Asignaciones a actividades |
| `/api/resource-costs/projects/{id}/` | Resumen de costos del proyecto |
| `/api/resource-costs/tasks/{id}/` | Resumen por actividad |
| `/api/resource-availability/projects/{id}/` | Disponibilidad semanal estimada |
| `/api/change-requests/` | Solicitudes y acciones de control de cambios |
| `/api/change-kpis/projects/{id}/` | KPI de gestión del cambio |

Las acciones especializadas de solicitudes de cambio incluyen `submit`, `approve`, `reject`, `start-implementation`, `preview-schedule`, `apply-schedule`, `record-actual-cost` y `close` bajo `/api/change-requests/{id}/`.

> Los contratos detallados de campos, estados y validaciones están implementados en los serializers, vistas y pruebas correspondientes. No asumir que todas las acciones de un ViewSet están habilitadas para ambos roles.

## Reglas clave

### Planificación

- Las actividades tienen fechas planificadas, fechas reales y avance.
- Una tarea existente **no se reprograma mediante el CRUD general**: se utiliza el servicio de preview/confirmación para garantizar coherencia y propagación.
- Se admiten dependencias FS, SS, FF y SF con desfases ±.
- Los calendarios y excepciones afectan el cálculo de días laborables.
- Las operaciones sensibles emplean validaciones de consistencia y transacciones para evitar escrituras parciales.

### Hitos y KPI

- Un hito pertenece a un proyecto y puede relacionarse con distintas tareas del **mismo** proyecto.
- Un KPI pertenece a un hito; soporta valores directos o porcentuales y sentido de cumplimiento (al menos / como máximo).
- Django calcula los estados `MET`, `NOT_MET` y `NOT_MEASURED`.

### Recursos y costos

- Las asignaciones vinculan tareas y recursos del mismo proyecto.
- Costos planificados y reales se almacenan por separado, conservando las tarifas de las asignaciones.
- La disponibilidad semanal distribuye horas previstas entre días laborables: **es una estimación**.

### Cambios y auditoría

- Se registran solicitudes, decisiones, ejecución, costo real declarado y eventos de trazabilidad.
- Aprobar una solicitud no aplica automáticamente una reprogramación.
- La identidad de quien realiza acciones sensibles se obtiene de la sesión autenticada.
- Los cambios del cronograma confirmados quedan registrados en las aplicaciones asociadas.

## Pruebas

Ejecutar desde `backend/`, con `.venv` activo y PostgreSQL accesible:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core projects tasks scheduling -v 2
```

Las pruebas Django usan una **base de datos de pruebas** según la configuración de Django/PostgreSQL. El usuario de PostgreSQL necesita permisos para crearla. No ejecutar cargas destructivas manuales sobre datos relevantes.

La cantidad total de tests no se fija aquí: ha variado durante el desarrollo. Registrar el resultado de la suite actual para la entrega académica.

## Solución de problemas

| Problema | Posible causa o comprobación |
| --- | --- |
| `connection refused` a PostgreSQL | Servicio apagado, host o puerto distinto de `5433` |
| Error en `migrate` | Credenciales, conexión o migraciones no aplicadas |
| `401 Unauthorized` | Usuario sin sesión válida |
| `403 Forbidden` | Rol insuficiente, CSRF o autorización |
| `404 Not Found` en detalle | Registro inexistente o no accesible por membresía |
| `405 Method Not Allowed` | Método HTTP no soportado en la ruta |
| `400 Bad Request` | Validaciones de serializers y reglas de programación |
| `403` en login desde Vue | Cookie/header CSRF o mezcla de `localhost` y `127.0.0.1` |

Para errores HTTP, revisar el JSON de respuesta sin exponer secretos.

## Consideraciones para despliegue

La configuración revisada está orientada al **desarrollo local**. Antes de producción, como mínimo:

- Configurar `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` segura y hosts permitidos reales.
- Usar HTTPS y revisar `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE`, CORS y `CSRF_TRUSTED_ORIGINS`.
- Gestionar credenciales mediante secretos/variables de entorno; nunca subir `.env`.
- Preparar copias de seguridad y restauración de PostgreSQL.
- Configurar archivos estáticos, servidor de aplicación e infraestructura de despliegue.
- Ejecutar nuevamente migraciones, pruebas y revisión de seguridad en el entorno destino.

**No se afirma que este repositorio esté configurado para producción.**
