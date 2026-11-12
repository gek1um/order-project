<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { projectService, type Project } from '../services/projects'
import { userAdministrationService, type ProjectMembership } from '../services/userAdministration'
import type { AuthUser, UserRole } from '../services/auth'

const auth = useAuthStore()
const users = ref<AuthUser[]>([])
const projects = ref<Project[]>([])
const memberships = ref<ProjectMembership[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const createOpen = ref(false)
const username = ref('')
const password = ref('')
const email = ref('')
const role = ref<UserRole>('PROJECT_USER')
const selectedForNew = ref<number[]>([])
const selection = ref<number | null>(null)
const selectedExistingProjects = ref<number[]>([])
const filter = ref('')

const selectedUser = computed(() => users.value.find(u => u.id === selection.value) ?? null)
const userMemberships = computed(() => memberships.value.filter(m => m.user === selection.value))
const assignedSet = computed(() => new Set(userMemberships.value.map(m => m.project)))
const filteredUsers = computed(() => users.value.filter(u => [u.username, u.email, u.role]
  .join(' ').toLowerCase().includes(filter.value.trim().toLowerCase())))

function errorText(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const response = err.response?.data as Record<string, unknown> | undefined
    if (response && typeof response === 'object') {
      const detail = response.detail
      if (typeof detail === 'string') return detail
      return Object.entries(response).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`).join(' · ')
    }
    if (!err.response) return 'No se pudo conectar con Django.'
    return `Error HTTP ${err.response.status}.`
  }
  return err instanceof Error ? err.message : 'Ocurrió un error inesperado.'
}

async function reload(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [newUsers, newProjects, newMemberships] = await Promise.all([
      userAdministrationService.listUsers(),
      projectService.list(),
      userAdministrationService.listMemberships(),
    ])
    users.value = newUsers
    projects.value = newProjects
    memberships.value = newMemberships
    if (selection.value !== null && !newUsers.some(u => u.id === selection.value)) selection.value = null
  } catch (err: unknown) { error.value = errorText(err) }
  finally { loading.value = false }
}

function selectUser(id: number): void {
  selection.value = id
  selectedExistingProjects.value = []
  error.value = ''
  success.value = ''
}

function resetNew(): void {
  username.value = ''
  password.value = ''
  email.value = ''
  role.value = 'PROJECT_USER'
  selectedForNew.value = []
  createOpen.value = false
}

async function createUser(): Promise<void> {
  if (saving.value) return
  error.value = ''
  success.value = ''
  if (!username.value.trim() || !password.value) { error.value = 'Ingresa usuario y contraseña.'; return }
  saving.value = true
  let created: AuthUser | null = null
  const failures: string[] = []
  try {
    created = await userAdministrationService.createUser({
      username: username.value.trim(),
      password: password.value,
      email: email.value.trim(),
      role: role.value,
    })
    // Se asignan secuencialmente para identificar con precisión los errores parciales.
    for (const projectId of selectedForNew.value) {
      try { await userAdministrationService.addMembership(created.id, projectId) }
      catch (err: unknown) {
        const project = projects.value.find(p => p.id === projectId)
        failures.push(`${project?.code ?? projectId}: ${errorText(err)}`)
      }
    }
    const selectedCount = selectedForNew.value.length
    resetNew()
    selection.value = created.id
    await reload()
    if (failures.length) {
      error.value = `Se creó ${created.username}, pero no se asignaron algunos proyectos: ${failures.join(' · ')}. Puedes reintentarlo desde sus membresías.`
    } else {
      success.value = `Usuario ${created.username} creado correctamente${selectedCount ? ' y proyectos asignados' : ''}.`
    }
  } catch (err: unknown) {
    error.value = errorText(err)
    if (created) error.value = `Se creó ${created.username}, pero ocurrió un error después: ${error.value}`
  } finally { saving.value = false }
}

async function updateRole(newRole: UserRole): Promise<void> {
  if (!selectedUser.value || saving.value || selectedUser.value.role === newRole) return
  error.value = ''; success.value = ''; saving.value = true
  try {
    await userAdministrationService.changeRole(selectedUser.value.id, newRole)
    await reload()
    success.value = 'Rol actualizado.'
  } catch (err: unknown) { error.value = errorText(err) }
  finally { saving.value = false }
}

async function addSelectedMemberships(): Promise<void> {
  if (selection.value === null || saving.value || !selectedExistingProjects.value.length) return
  saving.value = true; error.value = ''; success.value = ''
  const failures: string[] = []
  let count = 0
  for (const projectId of selectedExistingProjects.value) {
    if (assignedSet.value.has(projectId)) continue
    try { await userAdministrationService.addMembership(selection.value, projectId); count++ }
    catch (err: unknown) { failures.push(`${projects.value.find(p => p.id === projectId)?.code ?? projectId}: ${errorText(err)}`) }
  }
  selectedExistingProjects.value = []
  await reload()
  if (failures.length) error.value = `Algunas asignaciones fallaron: ${failures.join(' · ')}`
  else success.value = `${count} proyecto(s) asignado(s).`
  saving.value = false
}

async function removeMembership(membership: ProjectMembership): Promise<void> {
  if (saving.value) return
  if (!window.confirm(`¿Quitar a ${membership.username} del proyecto ${membership.project_code}?`)) return
  saving.value = true; error.value = ''; success.value = ''
  try {
    await userAdministrationService.removeMembership(membership.id)
    await reload()
    success.value = 'Membresía revocada correctamente.'
  } catch (err: unknown) { error.value = errorText(err) }
  finally { saving.value = false }
}

onMounted(() => { if (auth.isAdmin) void reload() })
</script>

<template>
  <section class="users-page">
    <template v-if="!auth.isAdmin">
      <h1>Acceso restringido</h1>
      <p class="muted">Esta sección está disponible únicamente para administradores.</p>
    </template>
    <template v-else>
      <header class="page-heading">
        <div>
          <h1>Usuarios y permisos</h1>
          <p class="muted">Crea usuarios y controla el acceso a los proyectos de order-project.</p>
        </div>
        <div class="toolbar">
          <button class="secondary-button" :disabled="loading || saving" @click="reload">Actualizar</button>
          <button class="primary-button" :disabled="saving" @click="createOpen = !createOpen">{{ createOpen ? 'Cerrar formulario' : '+ Nuevo usuario' }}</button>
        </div>
      </header>

      <p v-if="error" class="message error" role="alert">{{ error }}</p>
      <p v-if="success" class="message success" role="status">{{ success }}</p>

      <form v-if="createOpen" class="panel form-panel" @submit.prevent="createUser">
        <h2>Crear usuario</h2>
        <div class="fields-grid">
          <label>Nombre de usuario <input v-model.trim="username" required maxlength="150" autocomplete="off" placeholder="usuario_proyecto" /></label>
          <label>Contraseña inicial <input v-model="password" required type="password" autocomplete="new-password" placeholder="Contraseña segura" /></label>
          <label>Correo (opcional) <input v-model.trim="email" type="email" placeholder="usuario@ejemplo.cl" /></label>
          <label>Rol
            <select v-model="role"><option value="PROJECT_USER">PROJECT_USER</option><option value="ADMIN">ADMIN</option></select>
          </label>
        </div>
        <div class="selection-heading">Proyectos iniciales <span class="muted">(opcional)</span></div>
        <div class="project-options">
          <label v-for="project in projects" :key="project.id" class="check-option">
            <input v-model="selectedForNew" type="checkbox" :value="project.id" />
            <span><strong>{{ project.code }}</strong> — {{ project.name }}</span>
          </label>
          <p v-if="!projects.length" class="muted">No hay proyectos disponibles.</p>
        </div>
        <div class="toolbar end">
          <button class="secondary-button" type="button" :disabled="saving" @click="resetNew">Cancelar</button>
          <button class="primary-button" type="submit" :disabled="saving">{{ saving ? 'Guardando…' : 'Crear y asignar proyectos' }}</button>
        </div>
      </form>

      <div v-if="loading" class="panel muted">Cargando usuarios y proyectos…</div>
      <div v-else class="columns">
        <section class="panel user-list">
          <div class="panel-title"><h2>Usuarios registrados</h2><span class="muted">{{ users.length }}</span></div>
          <input v-model="filter" class="filter-input" placeholder="Buscar usuario, correo o rol…" aria-label="Buscar usuarios" />
          <div v-if="!filteredUsers.length" class="muted empty">No se encontraron usuarios.</div>
          <button v-for="user in filteredUsers" :key="user.id" class="user-row" :class="{ selected: selection === user.id }" @click="selectUser(user.id)">
            <span class="user-main"><strong>{{ user.username }}</strong><small>{{ user.email || 'Sin correo' }}</small></span>
            <span class="role-pill">{{ user.role }}</span>
            <span class="membership-count">{{ user.role === 'ADMIN' ? 'Todos' : `${memberships.filter(m => m.user === user.id).length} proyectos` }}</span>
          </button>
        </section>

        <section class="panel details-panel">
          <template v-if="selectedUser">
            <div class="panel-title"><h2>{{ selectedUser.username }}</h2><span class="role-pill">{{ selectedUser.role }}</span></div>
            <p class="muted">Administración de rol y proyectos autorizados.</p>
            <label class="role-field">Rol del usuario
              <select :value="selectedUser.role" :disabled="saving || selectedUser.is_superuser || selectedUser.id === auth.user?.id" @change="updateRole(($event.target as HTMLSelectElement).value as UserRole)">
                <option value="PROJECT_USER">PROJECT_USER</option><option value="ADMIN">ADMIN</option>
              </select>
            </label>
            <p v-if="selectedUser.is_superuser" class="muted helper">El rol de un superusuario no puede modificarse.</p>
            <h3>Proyectos asignados</h3>
            <div v-if="!userMemberships.length" class="muted empty">Este usuario no tiene membresías explícitas.</div>
            <div v-for="membership in userMemberships" :key="membership.id" class="membership-row">
              <span><strong>{{ membership.project_code }}</strong> · {{ membership.project_name }}</span>
              <button class="danger-button" :disabled="saving" @click="removeMembership(membership)">Quitar</button>
            </div>
            <div class="assign-panel">
              <h3>Asignar proyectos</h3>
              <p v-if="selectedUser.role === 'ADMIN'" class="muted helper">Los ADMIN ya pueden consultar todos los proyectos; estas membresías no limitan su acceso.</p>
              <div class="project-options">
                <label v-for="project in projects.filter(p => !assignedSet.has(p.id))" :key="project.id" class="check-option">
                  <input v-model="selectedExistingProjects" type="checkbox" :value="project.id" />
                  <span><strong>{{ project.code }}</strong> — {{ project.name }}</span>
                </label>
                <span v-if="projects.every(p => assignedSet.has(p.id))" class="muted">No hay más proyectos por asignar.</span>
              </div>
              <div class="toolbar end"><button class="primary-button" :disabled="saving || !selectedExistingProjects.length" @click="addSelectedMemberships">{{ saving ? 'Guardando…' : 'Asignar seleccionados' }}</button></div>
            </div>
          </template>
          <div v-else class="muted empty">Selecciona un usuario para consultar o modificar su rol y sus proyectos asignados.</div>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.users-page { max-width: 1350px; margin: 0 auto; padding: 36px; color: var(--color-text); }
h1 { margin:0 0 8px; font-size:26px; letter-spacing:-0.6px; }
h2 { margin:0; font-size:16px; }
h3 { margin:24px 0 10px; font-size:13px; }
.muted { color: var(--color-muted); font-size:12px; line-height:1.5; }
.page-heading { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:22px; }
.toolbar { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.end { justify-content:flex-end; margin-top:20px; }
.primary-button,.secondary-button,.danger-button { cursor:pointer; border-radius:7px; padding:10px 14px; font-size:12px; font-weight:600; }
.primary-button { background:#4f8cff; border:1px solid #4f8cff; color:#fff; }
.secondary-button { color:#dce5f3; border:1px solid var(--color-border); background:var(--color-surface); }
.danger-button { color:#f4a69d; border:1px solid #78404a; background:transparent; padding:6px 10px; }
button:disabled { opacity:.55; cursor:not-allowed; }
.panel { background:var(--color-surface); border:1px solid var(--color-border); border-radius:12px; padding:22px; }
.form-panel { margin-bottom:20px; }
.fields-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:20px; }
label { display:flex; flex-direction:column; gap:7px; font-size:12px; color:#cbd6e4; }
input:not([type=checkbox]), select { width:100%; background:#19212d; border:1px solid #374354; border-radius:7px; color:#edf3fb; font:inherit; padding:11px 12px; outline:none; }
input:focus, select:focus { border-color:#4f8cff; }
.selection-heading { margin-top:20px; font-size:12px; font-weight:600; }
.project-options { display:grid; gap:8px; max-height:190px; overflow:auto; margin-top:12px; }
.check-option { display:flex; flex-direction:row; align-items:center; gap:10px; padding:9px 12px; background:#19212d; border:1px solid #303c4b; border-radius:7px; font-size:12px; cursor:pointer; }
.check-option input { accent-color:#4f8cff; }
.columns { display:grid; grid-template-columns:minmax(300px,0.9fr) minmax(400px,1.2fr); gap:18px; }
.panel-title { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:16px; }
.filter-input { margin-bottom:16px; }
.user-list { max-height:700px; overflow:auto; }
.user-row { width:100%; text-align:left; display:flex; align-items:center; gap:10px; border:1px solid transparent; border-bottom-color:#303a49; background:transparent; padding:12px 6px; color:inherit; cursor:pointer; }
.user-row:hover, .user-row.selected { background:#273447; border-radius:7px; }
.user-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:5px; }
.user-main small { color:var(--color-muted); }
.role-pill { background:#273c57; color:#a3c5fc; padding:5px 8px; border-radius:6px; font-size:10px; white-space:nowrap; }
.membership-count { color:var(--color-muted); font-size:10px; }
.membership-row { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px; margin-bottom:8px; background:#19212d; border-radius:7px; font-size:12px; }
.assign-panel { margin-top:25px; padding-top:15px; border-top:1px solid var(--color-border); }
.role-field { margin:16px 0; max-width:300px; }
.message { border:1px solid; border-radius:8px; padding:12px 16px; margin-bottom:18px; font-size:12px; }
.error { color:#ffb7a9; border-color:#773b44; background:#40232b; }
.success { color:#9ce3bb; border-color:#35694b; background:#1a3427; }
.empty { padding:24px 0; }
.helper { margin-top:4px; }
@media(max-width:950px) { .columns { grid-template-columns:1fr; } }
@media(max-width:650px) { .users-page { padding:20px; } .fields-grid { grid-template-columns:1fr; } .page-heading { align-items:flex-start; flex-direction:column; } }
</style>
