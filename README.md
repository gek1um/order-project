# order-project

**Sistema web de gestión, planificación y seguimiento de proyectos** desarrollado como proyecto académico integrador. Permite administrar proyectos y actividades, planificar cronogramas, visualizar una Carta Gantt, gestionar hitos y KPI, asignar recursos, controlar costos y tramitar solicitudes de cambio.

> **Estado:** aplicación funcional validada progresivamente durante el desarrollo. La regresión integral de la Fase 9.2 y la preparación de entrega todavía deben registrarse con evidencias finales. No se considera un despliegue productivo endurecido.

## Tecnologías

| Capa | Tecnologías |
| --- | --- |
| Frontend | Vue 3, TypeScript, Vite, Vue Router, Pinia, Axios |
| Backend | Python, Django 5.2, Django REST Framework |
| Base de datos | PostgreSQL |
| Autenticación | Sesiones de Django, cookies HTTP y protección CSRF |
| Desarrollo local | Windows/PowerShell, Python `.venv`, npm y PostgreSQL (local o en Docker) |

## Funcionalidades principales

- **Proyectos y actividades:** datos generales, estados, fechas planificadas/reales y progreso.
- **Programación:** dependencias FS, SS, FF y SF, desfases, calendarios laborales y excepciones; simulación y confirmación de reprogramaciones con propagación.
- **Carta Gantt:** barras planificadas/reales, conexiones, progreso, retrasos, hitos y acceso a la reprogramación.
- **Hitos y KPI asociados:** responsables, criterios de aceptación, evidencias, vinculación con actividades, metas y mediciones de indicadores.
- **Recursos y costos:** catálogo, asignaciones por actividad, unidades y costos planificados/reales, resúmenes y estimaciones de disponibilidad semanal.
- **Gestión de cambios:** solicitudes, evaluación, decisiones, aplicación controlada, eventos de auditoría y KPI de control del cambio.
- **Dashboards:** Seguimiento del Proyecto y Gestión del Cambio.
- **Usuarios y permisos:** roles `ADMIN` y `PROJECT_USER`, membresías por proyecto, acceso limitado por proyecto y administración de usuarios desde Vue.

### Roles

| Funcionalidad | ADMIN | PROJECT_USER |
| --- | --- | --- |
| Ver proyectos | Todos | Solo los asignados |
| Crear, editar o eliminar proyectos | Sí | No |
| Trabajar en actividades y recursos | Sí | Solo en proyectos asignados |
| Crear solicitudes de cambio | Sí | En proyectos asignados |
| Aprobar o rechazar solicitudes | Sí | No |
| Administrar usuarios, roles y membresías | Sí | No |

Los controles del frontend ayudan a la experiencia de uso; **Django es quien aplica los permisos de seguridad**.

## Estructura del repositorio

```text
order-project/
├── backend/                 # API REST Django, modelos, migraciones y tests
│   ├── config/
│   ├── core/
│   ├── projects/
│   ├── tasks/
│   ├── scheduling/
│   ├── manage.py
│   ├── requirements.txt
│   └── README.md
├── frontend/                # Interfaz Vue 3 + TypeScript
│   ├── src/
│   ├── package.json
│   └── README.md
└── README.md
```

La raíz puede incluir archivos de configuración local (por ejemplo, `.env` y archivos Docker Compose) según el entorno donde se haya clonado el repositorio. No se incluyen credenciales en estos README.

## Requisitos para ejecutar localmente

- Python compatible con las dependencias de `backend/requirements.txt`.
- Node.js y npm compatibles con `frontend/package.json`.
- PostgreSQL accesible desde el backend.
- Puerto **8000** disponible para Django y **5173** para Vite (configuración de desarrollo habitual).

> **Configuración de referencia comprobada en el backend:** Django 5.2.18, DRF 3.18.3, `psycopg` 3.3.6, `django-cors-headers` 4.9.0. Consultar los archivos de dependencias para las versiones exactas del checkout actual.

## Instalación rápida

### 1. Configurar PostgreSQL

El backend lee desde el archivo `.env` situado en la **raíz de `order-project`** las variables:

```dotenv
POSTGRES_DB=order_project
POSTGRES_USER=order_user
POSTGRES_PASSWORD=reemplazar_por_clave_local
POSTGRES_PORT=5433
DJANGO_SECRET_KEY=reemplazar_por_clave_secreta_local
DJANGO_DEBUG=True
```

Estos son **valores de ejemplo**, no credenciales ni nombres de base de datos confirmados. Deben coincidir con la instancia de PostgreSQL del equipo. La configuración de Django consultada usa `127.0.0.1` como host y `5433` como puerto predeterminado.

Si se utiliza Docker, iniciar PostgreSQL con el archivo Compose **existente en el repositorio**, si lo hay. No se presupone un nombre concreto de servicio ni de archivo Docker.

### 2. Iniciar el backend

En una terminal PowerShell desde la raíz:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

La API queda disponible en `http://localhost:8000/api/`. Para preparar la cuenta administradora inicial, en otra terminal del backend:

```powershell
python manage.py createsuperuser
```

### 3. Iniciar el frontend

En otra terminal, desde la raíz:

```powershell
cd frontend
npm install
npm run dev
```

Configurar el archivo `frontend/.env` si no existe:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api
```

Abrir `http://localhost:5173/login` e iniciar sesión con una cuenta de Django.

**Importante para CSRF:** abrir Vue y apuntar Axios al backend usando el mismo nombre de host (`localhost` en ambos). Evitar mezclar `localhost` y `127.0.0.1`, ya que puede causar un `403` en el login por cookies/tokens CSRF.

Para configuración detallada consultar [Backend](backend/README.md) y [Frontend](frontend/README.md).

## Páginas principales

| Ruta | Descripción |
| --- | --- |
| `/login` | Inicio de sesión |
| `/projects` | Proyectos |
| `/projects/:id` | Detalle y actividades del proyecto |
| `/scheduling` | Programación y calendario |
| `/gantt` | Carta Gantt independiente |
| `/milestones` | Administración de hitos |
| `/milestone-kpis` | KPI asociados a hitos |
| `/resources` | Recursos y costos |
| `/changes` | Gestión de cambios |
| `/dashboard/project` | Seguimiento del Proyecto |
| `/dashboard/changes` | Gestión del Cambio |
| `/admin/users` | Administración de usuarios (solo ADMIN) |

## Pruebas y verificación

**Backend** (desde `backend/`, con `.venv` activo):

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core projects tasks scheduling -v 2
```

**Frontend** (desde `frontend/`):

```powershell
npm run build
```

Las fases anteriores fueron probadas incrementalmente. Para la entrega final, registrar la **cantidad real** de tests, la fecha, el log y las evidencias de los recorridos E2E; no se fija un número de tests porque ha cambiado con las fases.

## Recorrido recomendado para la demostración

1. Ingresar como ADMIN y crear un proyecto de prueba.
2. Crear un PROJECT_USER y asignarlo al proyecto.
3. Ingresar como PROJECT_USER y crear actividades, dependencias e hitos.
4. Mostrar el calendario, la Carta Gantt y una simulación de reprogramación.
5. Asignar recursos y registrar costos planificados/reales.
6. Registrar una solicitud de cambio; aprobarla e implementarla con ADMIN.
7. Revisar la trazabilidad y ambos dashboards.
8. Demostrar que un PROJECT_USER no puede acceder a un proyecto no asignado.

## Consideraciones y límites

- La planificación maneja actividades **planas**, sin EDT/WBS jerárquica, conforme a la excepción académica acordada.
- La disponibilidad semanal se **estima** distribuyendo horas entre días laborables; no constituye una agenda de turnos.
- Los KPI de hitos representan la **medición actual**; no existe todavía un histórico de mediciones para series temporales.
- La planificación muestra fechas planificadas vigentes y reales; no equivale por sí sola a un historial completo de líneas base.
- Para una puesta en producción se requieren configuración de HTTPS, secretos, cookies seguras, `DEBUG=False`, hosts permitidos, respaldos y revisión adicional de infraestructura/seguridad.

## Documentación complementaria

- [README del frontend](frontend/README.md)
- [README del backend](backend/README.md)

---

**Proyecto académico — order-project.** Las capturas, casos de prueba y resultados de la regresión final deben acompañar la entrega.
