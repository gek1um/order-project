# Frontend — order-project

Interfaz web de **order-project**, desarrollada con **Vue 3, TypeScript y Vite**. Consume la API REST de Django para administrar proyectos, actividades, planificación, recursos, control de cambios y dashboards.

[Volver al README general](../README.md) · [Documentación del backend](../backend/README.md)

## Stack y arquitectura

- **Vue 3** con componentes `.vue` y Composition API.
- **TypeScript** para los contratos de datos y servicios.
- **Vite** para servidor de desarrollo y compilación.
- **Vue Router** para las páginas y sus protecciones.
- **Pinia** para el estado de autenticación.
- **Axios** para las peticiones a Django, cookies de sesión y CSRF.
- Estilo visual **oscuro**, con componentes de layout y estilos globales.

Las versiones exactas y scripts disponibles dependen de `package.json` del checkout local; no se incluyó ese archivo en el ZIP de `src` revisado para redactar esta guía.

## Estructura principal

```text
frontend/
├── src/
│   ├── assets/styles/global.css
│   ├── components/
│   │   ├── layout/                 # AppLayout, AppSidebar, AppTopbar
│   │   └── scheduling/             # Gantt, dependencias, calendarios, hitos y KPI
│   ├── router/index.ts             # Rutas y guardas de navegación
│   ├── services/                   # API Axios y servicios por dominio
│   ├── stores/                     # Estado de autenticación en Pinia
│   ├── utils/                      # Indicadores auxiliares de planificación
│   ├── views/                      # Páginas
│   ├── App.vue
│   └── main.ts
├── package.json
└── README.md
```

## Requisitos y preparación

- Node.js y npm compatibles con `package.json`.
- Backend Django levantado en `http://localhost:8000`.
- PostgreSQL funcionando y migraciones del backend aplicadas.

En PowerShell:

```powershell
cd frontend
npm install
```

Crear o revisar `frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api
```

> La base URL incluye `/api` y los servicios Axios agregan sus rutas relativas. **No** agregar `/api` por duplicado dentro de cada servicio.

Ejecutar:

```powershell
npm run dev
```

Abrir **http://localhost:5173/login**.

### Compilación

```powershell
npm run build
```

Este comando comprueba la construcción de la aplicación. Verificar el `package.json` local para scripts adicionales (`lint`, pruebas, etc.); aquí no se asume su existencia.

## Rutas de la aplicación

| Ruta | Módulo |
| --- | --- |
| `/login` | Inicio de sesión |
| `/projects` y `/projects/:id` | Proyectos y actividades |
| `/scheduling` | Programación y calendarios |
| `/gantt` | Carta Gantt independiente |
| `/milestones` | Hitos |
| `/milestone-kpis` | Indicadores de hitos |
| `/resources` | Recursos, asignaciones, costos y disponibilidad |
| `/changes` | Solicitudes de cambio, auditoría e implementación |
| `/dashboard/project` | Dashboard de Seguimiento del Proyecto |
| `/dashboard/changes` | Dashboard de Gestión del Cambio |
| `/admin/users` | Usuarios y permisos (solo ADMIN) |

Las páginas privadas exigen una sesión válida. La ruta de administración comprueba además el rol en Vue, **sin sustituir** las verificaciones de Django.

## Autenticación y roles

El frontend utiliza **cookies de sesión de Django**, no JWT:

1. La aplicación consulta `GET /api/auth/me/` al inicializarse.
2. Si no hay sesión activa, redirige a `/login`.
3. Antes de operaciones de escritura obtiene un token desde `GET /api/auth/csrf/`.
4. `POST /api/auth/login/` inicia sesión y devuelve datos de usuario; el token CSRF puede rotar después del login.
5. Axios envía las cookies (`withCredentials`) y `X-CSRFToken` para `POST`, `PUT`, `PATCH` y `DELETE`.
6. `POST /api/auth/logout/` cierra la sesión; una petición privada posterior requiere reautenticarse.

Los roles son `ADMIN` y `PROJECT_USER`. Un PROJECT_USER puede trabajar únicamente en proyectos a los que fue asignado y no puede realizar aprobaciones administrativas. Django filtra y autoriza los datos en el servidor.

### Gestión de usuarios

Ingresar como ADMIN y abrir `/admin/users`. Desde esa página se puede:

- Crear cuentas con rol inicial.
- Asignar uno o varios proyectos.
- Cambiar roles de usuarios autorizados.
- Añadir o revocar membresías.

Si se crea una cuenta y falla la asignación de uno de sus proyectos, la cuenta puede quedar creada con **membresías parciales**: revisar el mensaje de error y completar las asignaciones pendientes.

## Funcionalidades por pantalla

### Programación y Carta Gantt

El backend suministra el cronograma con `GET /api/scheduling/projects/{id}/schedule/`. El gráfico representa la programación vigente, fechas reales, dependencias FS/SS/FF/SF, hitos y progreso.

La reprogramación no se guarda al pulsar la barra: usa una **simulación** antes de confirmar:

- `POST /api/scheduling/tasks/{id}/preview/` (sin guardar).
- `POST /api/scheduling/tasks/{id}/reschedule/` (confirma tras validación del backend).

### Hitos y KPI por hitos

Cada hito puede asociarse a varias actividades del mismo proyecto. Sus KPI admiten valores directos o porcentajes con numerador/denominador; Django calcula `MET`, `NOT_MET` o `NOT_MEASURED`.

### Recursos y costos

Permite gestionar recursos, asignaciones a actividades, horas/unidades previstas y ejecutadas, costos y alertas de capacidad semanal. Los precios propios de cada asignación se conservan independientemente del catálogo.

### Gestión de cambios

Incluye registro, evaluación, aprobación/rechazo, implementación, trazabilidad y consulta de KPI. Las aprobaciones y rechazos son exclusivos de ADMIN.

### Dashboards

- **Seguimiento:** actividades, avance, hitos, KPI asociados, costos y disponibilidad.
- **Gestión del Cambio:** tasa de aprobación, tiempo promedio de decisión, cumplimiento de cierre, estados y prioridades.

## Problemas frecuentes

| Síntoma | Qué revisar |
| --- | --- |
| `403` al hacer login | Que frontend y backend usen `localhost`; cookie CSRF y encabezado `X-CSRFToken`; `CSRF_TRUSTED_ORIGINS` |
| `401` al cargar una pantalla | Sesión caducada o cookie ausente; volver a iniciar sesión |
| `403` en acciones de escritura | Rol/membresía, CSRF y permisos del backend |
| `404` en un proyecto | ID incorrecto **o** proyecto no autorizado (ocultación intencional de recursos ajenos) |
| `ERR_CONNECTION_REFUSED` | Django no está ejecutándose o URL/puerto incorrecto |
| El build falla por dependencias | Ejecutar `npm install` y revisar la versión local de Node / `package.json` |
| Los datos del dashboard no cambian | Recargar la consulta y comprobar el proyecto seleccionado |

Para investigar peticiones: Chrome DevTools → **Network**, consultar `Status`, `Request URL` y `Response` sin compartir contraseñas, cookies ni tokens reales.

## Verificación antes de entregar

```powershell
npm run build
```

Además, comprobar manualmente: inicio/cierre de sesión, un flujo ADMIN, un flujo PROJECT_USER, aislamiento de proyectos, CRUD permitido, reprogramación, hitos/KPI, costos, cambios y ambos dashboards. Conservar capturas y resultados en el registro de evidencias de la Fase 9.

## Límites conocidos

- La navegación restringe acciones visualmente; **la autorización definitiva ocurre en Django**.
- Los KPI de hitos no poseen un histórico de múltiples mediciones.
- La carga semanal de recursos es una estimación, no una agenda horaria real.
- No se presupone configuración de despliegue productivo, HTTPS o monitoreo en este README.
