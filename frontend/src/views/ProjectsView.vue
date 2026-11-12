<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { useAuthStore } from '../stores/auth'

import {
  projectService,
  type Project,
  type ProjectStatus,
  type CreateProjectPayload,
} from '../services/projects'

const router = useRouter()
const auth = useAuthStore()

const projects = ref<Project[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)

const pageError = ref('')
const formError = ref('')
const deleteError = ref('')
const successMessage = ref('')

const search = ref('')
const statusFilter = ref('')

const showForm = ref(false)
const showDelete = ref(false)

const editingProject = ref<Project | null>(null)
const projectToDelete = ref<Project | null>(null)

const isEditing = computed(() => editingProject.value !== null)

const statusOptions: { value: ProjectStatus; label: string }[] = [
  { value: 'PLANNED', label: 'Planificado' },
  { value: 'IN_PROGRESS', label: 'En progreso' },
  { value: 'ON_HOLD', label: 'En pausa' },
  { value: 'COMPLETED', label: 'Completado' },
  { value: 'CANCELLED', label: 'Cancelado' },
]

function emptyForm(): CreateProjectPayload {
  return {
    code: '',
    name: '',
    description: '',
    manager_name: '',
    status: 'PLANNED',
    start_date: '',
    end_date: '',
    baseline_budget: '0',
  }
}

const form = ref<CreateProjectPayload>(emptyForm())

// ==================================================
// FILTROS Y ESTADÍSTICAS
// ==================================================

const statistics = computed(() => ({
  total: projects.value.length,
  active: projects.value.filter((p) => p.status === 'IN_PROGRESS').length,
  planned: projects.value.filter((p) => p.status === 'PLANNED').length,
  completed: projects.value.filter((p) => p.status === 'COMPLETED').length,
}))

const filteredProjects = computed(() => {
  const term = search.value.trim().toLowerCase()

  return projects.value.filter((project) => {
    const matchesText =
      !term ||
      project.code.toLowerCase().includes(term) ||
      project.name.toLowerCase().includes(term) ||
      project.manager_name.toLowerCase().includes(term)

    const matchesStatus = !statusFilter.value || project.status === statusFilter.value

    return matchesText && matchesStatus
  })
})

// ==================================================
// UTILIDADES
// ==================================================

function formatDate(value: string): string {
  if (!value) return '-'
  const parts = value.split('-')
  if (parts.length !== 3) return value
  return `${parts[2]}/${parts[1]}/${parts[0]}`
}

function formatMoney(value: string): string {
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

function statusClass(status: string): string {
  return status.toLowerCase().replaceAll('_', '-')
}

function getErrorMessage(err: unknown): string {
  if (!isAxiosError(err)) return 'Ocurrió un error inesperado.'
  if (!err.response) return 'No se pudo conectar con Django.'

  const data: unknown = err.response.data

  if (typeof data === 'object' && data !== null) {
    const messages = Object.entries(data).map(([field, value]) => {
      const message = Array.isArray(value) ? value.map(String).join(', ') : String(value)

      return field === 'detail' ? message : `${field}: ${message}`
    })

    if (messages.length) return messages.join(' | ')
  }

  return `Error HTTP ${err.response.status}.`
}

// ==================================================
// CONSULTAS Y NAVEGACIÓN
// ==================================================

async function loadProjects() {
  loading.value = true
  pageError.value = ''

  try {
    projects.value = await projectService.list()
  } catch (err) {
    pageError.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function openDetail(project: Project) {
  router.push({
    name: 'project-detail',
    params: { id: project.id },
  })
}

// ==================================================
// FORMULARIO CREAR / EDITAR
// ==================================================

function openCreateForm() {
  if (!auth.isAdmin) return
  editingProject.value = null
  form.value = emptyForm()
  formError.value = ''
  successMessage.value = ''
  showForm.value = true
}

function openEditForm(project: Project) {
  if (!auth.isAdmin) return
  editingProject.value = project

  form.value = {
    code: project.code,
    name: project.name,
    description: project.description,
    manager_name: project.manager_name,
    status: project.status,
    start_date: project.start_date,
    end_date: project.end_date,
    baseline_budget: project.baseline_budget,
  }

  formError.value = ''
  successMessage.value = ''
  showForm.value = true
}

function closeForm() {
  if (saving.value) return

  showForm.value = false
  editingProject.value = null
  formError.value = ''
}

function validateForm(): boolean {
  if (!form.value.code.trim() || !form.value.name.trim() || !form.value.manager_name.trim()) {
    formError.value = 'Código, nombre y responsable son obligatorios.'
    return false
  }

  if (!form.value.start_date || !form.value.end_date) {
    formError.value = 'Debes completar las fechas.'
    return false
  }

  if (form.value.end_date < form.value.start_date) {
    formError.value = 'La fecha de término no puede ser anterior al inicio.'
    return false
  }

  if (
    !Number.isFinite(Number(form.value.baseline_budget)) ||
    Number(form.value.baseline_budget) < 0
  ) {
    formError.value = 'Presupuesto no válido.'
    return false
  }

  return true
}

async function saveProject() {
  if (!auth.isAdmin) return
  if (saving.value || !validateForm()) return

  saving.value = true
  formError.value = ''
  pageError.value = ''

  const existing = editingProject.value

  try {
    const payload: CreateProjectPayload = {
      ...form.value,
      code: form.value.code.trim(),
      name: form.value.name.trim(),
      manager_name: form.value.manager_name.trim(),
    }

    let saved: Project

    if (existing) {
      // El presupuesto inicial es inmutable.
      const { baseline_budget: _budget, ...changes } = payload
      void _budget

      saved = await projectService.update(existing.id, changes)
    } else {
      saved = await projectService.create(payload)
    }

    showForm.value = false
    editingProject.value = null

    successMessage.value = existing
      ? `Proyecto ${saved.code} actualizado correctamente.`
      : `Proyecto ${saved.code} creado correctamente.`

    await loadProjects()
  } catch (err) {
    formError.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

// ==================================================
// ELIMINACIÓN
// ==================================================

function openDeleteModal(project: Project) {
  if (!auth.isAdmin) return
  projectToDelete.value = project
  deleteError.value = ''
  successMessage.value = ''
  showDelete.value = true
}

function closeDeleteModal() {
  if (deleting.value) return

  showDelete.value = false
  projectToDelete.value = null
  deleteError.value = ''
}

async function confirmDelete() {
  if (!auth.isAdmin) return
  if (!projectToDelete.value || deleting.value) return

  deleting.value = true
  deleteError.value = ''

  const selected = projectToDelete.value

  try {
    await projectService.remove(selected.id)

    showDelete.value = false
    projectToDelete.value = null

    successMessage.value = `Proyecto ${selected.code} eliminado correctamente.`

    await loadProjects()
  } catch (err) {
    deleteError.value = getErrorMessage(err)
  } finally {
    deleting.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <h1 class="page-title">Proyectos</h1>
        <p class="page-description">Administra los proyectos registrados en order-project.</p>
      </div>

      <button v-if="auth.isAdmin" class="primary-button" @click="openCreateForm">+ Nuevo proyecto</button>
    </header>

    <div v-if="pageError" class="error-banner notice" role="alert">
      {{ pageError }}
    </div>

    <div v-if="successMessage" class="success-banner notice" role="status">
      {{ successMessage }}
    </div>

    <!-- RESUMEN ADMINISTRATIVO -->
    <section class="stats">
      <article class="panel stat-card">
        <span>Total proyectos</span>
        <strong>{{ statistics.total }}</strong>
      </article>

      <article class="panel stat-card">
        <span>En progreso</span>
        <strong class="blue">{{ statistics.active }}</strong>
      </article>

      <article class="panel stat-card">
        <span>Planificados</span>
        <strong class="yellow">{{ statistics.planned }}</strong>
      </article>

      <article class="panel stat-card">
        <span>Completados</span>
        <strong class="green">{{ statistics.completed }}</strong>
      </article>
    </section>

    <!-- TABLA -->
    <section class="panel table-panel">
      <div class="panel-heading">
        <div>
          <h2>Listado de proyectos</h2>
          <p>{{ filteredProjects.length }} proyectos visibles</p>
        </div>

        <button class="secondary-button" :disabled="loading" @click="loadProjects">
          {{ loading ? 'Cargando...' : 'Actualizar' }}
        </button>
      </div>

      <div class="filters">
        <input
          v-model="search"
          type="search"
          class="form-control"
          placeholder="Buscar por nombre, código o responsable..."
          aria-label="Buscar proyectos"
        />

        <select
          v-model="statusFilter"
          class="form-control filter-select"
          aria-label="Filtrar proyectos por estado"
        >
          <option value="">Todos los estados</option>
          <option v-for="option in statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <div class="table-scroll">
        <table class="projects-table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Proyecto</th>
              <th>Responsable</th>
              <th>Estado</th>
              <th>Inicio</th>
              <th>Término</th>
              <th>Presupuesto inicial</th>
              <th>Acciones</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="project in filteredProjects" :key="project.id">
              <td class="code">{{ project.code }}</td>

              <td>
                <strong>{{ project.name }}</strong>
                <div class="muted description">
                  {{ project.description }}
                </div>
              </td>

              <td>{{ project.manager_name }}</td>

              <td>
                <span class="status-badge" :class="statusClass(project.status)">
                  {{ project.status_display }}
                </span>
              </td>

              <td>{{ formatDate(project.start_date) }}</td>
              <td>{{ formatDate(project.end_date) }}</td>
              <td>{{ formatMoney(project.baseline_budget) }}</td>

              <td>
                <div class="actions">
                  <button class="action-button detail-action" @click="openDetail(project)">
                    Ver detalle
                  </button>

                  <button v-if="auth.isAdmin" class="action-button edit-action" @click="openEditForm(project)">
                    Editar
                  </button>

                  <button v-if="auth.isAdmin" class="action-button delete-action" @click="openDeleteModal(project)">
                    Eliminar
                  </button>
                </div>
              </td>
            </tr>

            <tr v-if="loading">
              <td colspan="8" class="empty-cell">Cargando proyectos...</td>
            </tr>

            <tr v-else-if="!filteredProjects.length">
              <td colspan="8" class="empty-cell">No hay proyectos que mostrar.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- FORMULARIO CREAR / EDITAR -->
    <div v-if="auth.isAdmin && showForm" class="modal-backdrop">
      <section
        class="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-form-title"
      >
        <div class="modal-header">
          <h2 id="project-form-title">
            {{ isEditing ? 'Editar proyecto' : 'Nuevo proyecto' }}
          </h2>

          <button
            type="button"
            class="close-button"
            :disabled="saving"
            aria-label="Cerrar"
            @click="closeForm"
          >
            ×
          </button>
        </div>

        <form @submit.prevent="saveProject">
          <div class="form-grid">
            <div>
              <label class="form-label" for="p-code">Código *</label>
              <input id="p-code" v-model="form.code" class="form-control" maxlength="30" required />
            </div>

            <div>
              <label class="form-label" for="p-name">Nombre *</label>
              <input
                id="p-name"
                v-model="form.name"
                class="form-control"
                maxlength="200"
                required
              />
            </div>

            <div class="full">
              <label class="form-label" for="p-description">Descripción</label>
              <textarea
                id="p-description"
                v-model="form.description"
                class="form-control"
                rows="3"
              ></textarea>
            </div>

            <div>
              <label class="form-label" for="p-manager">Responsable *</label>
              <input
                id="p-manager"
                v-model="form.manager_name"
                class="form-control"
                maxlength="150"
                required
              />
            </div>

            <div>
              <label class="form-label" for="p-status">Estado</label>
              <select id="p-status" v-model="form.status" class="form-control">
                <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div>
              <label class="form-label" for="p-start">Fecha inicio *</label>
              <input
                id="p-start"
                v-model="form.start_date"
                class="form-control"
                type="date"
                required
              />
            </div>

            <div>
              <label class="form-label" for="p-end">Fecha término *</label>
              <input id="p-end" v-model="form.end_date" class="form-control" type="date" required />
            </div>

            <div class="full">
              <label class="form-label" for="p-budget"> Presupuesto inicial (CLP) * </label>
              <input
                id="p-budget"
                v-model="form.baseline_budget"
                class="form-control"
                type="number"
                min="0"
                step="0.01"
                required
                :disabled="isEditing"
              />
              <p v-if="isEditing" class="muted">
                La línea base presupuestaria no se puede modificar.
              </p>
            </div>
          </div>

          <div v-if="formError" class="error-banner modal-error">
            {{ formError }}
          </div>

          <div class="modal-actions">
            <button class="secondary-button" type="button" :disabled="saving" @click="closeForm">
              Cancelar
            </button>

            <button class="primary-button" type="submit" :disabled="saving">
              {{ saving ? 'Guardando...' : isEditing ? 'Guardar cambios' : 'Crear proyecto' }}
            </button>
          </div>
        </form>
      </section>
    </div>

    <!-- CONFIRMACIÓN DE ELIMINACIÓN -->
    <div v-if="auth.isAdmin && showDelete && projectToDelete" class="modal-backdrop">
      <section
        class="modal delete-modal panel"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="project-delete-title"
      >
        <h2 id="project-delete-title">¿Eliminar proyecto?</h2>

        <p class="muted">
          Se eliminará
          <strong>{{ projectToDelete.code }} — {{ projectToDelete.name }}</strong
          >.
        </p>

        <p class="warning">
          La acción no se puede deshacer. Si el proyecto tiene tareas, Django impedirá eliminarlo.
        </p>

        <div v-if="deleteError" class="error-banner modal-error">
          {{ deleteError }}
        </div>

        <div class="modal-actions">
          <button
            class="secondary-button"
            type="button"
            :disabled="deleting"
            @click="closeDeleteModal"
          >
            Cancelar
          </button>

          <button class="delete-confirm" type="button" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? 'Eliminando...' : 'Sí, eliminar' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.notice {
  margin-bottom: 20px;
}

.muted {
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.6;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stat-card span {
  color: var(--color-muted);
  font-size: 12px;
}

.stat-card strong {
  font-size: 28px;
}

.blue {
  color: var(--color-primary);
}
.yellow {
  color: var(--color-warning);
}
.green {
  color: var(--color-success);
}

.table-panel {
  overflow: hidden;
}

.panel-heading {
  padding: 24px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.panel-heading h2 {
  font-size: 16px;
  margin: 0 0 8px;
}

.panel-heading p {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
}

.filters {
  padding: 0 24px 22px;
  display: flex;
  gap: 12px;
}

.filters input {
  flex: 1;
}

.filter-select {
  max-width: 210px;
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

.projects-table {
  border-collapse: collapse;
  width: 100%;
  white-space: nowrap;
  text-align: left;
}

.projects-table th {
  background: #20262f;
  color: #9ba9ba;
  padding: 15px 18px;
  font-size: 11px;
}

.projects-table td {
  border-top: 1px solid var(--color-border);
  padding: 18px;
  font-size: 12px;
  color: #cbd5e1;
}

.projects-table tbody tr:hover {
  background: #2b333f;
}

.projects-table td strong {
  color: #f1f5f9;
}

.code {
  color: #85b1ff !important;
  font-weight: 600;
}

.description {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 5px;
}

.status-badge {
  display: inline-flex;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 10px;
  font-weight: 600;
  background: #37404b;
}

.status-badge.planned,
.status-badge.on-hold {
  color: #f4b860;
  background: #493d2b;
}

.status-badge.in-progress {
  color: #85b1ff;
  background: #273c5a;
}

.status-badge.completed {
  color: #5cc8a1;
  background: #29443d;
}

.status-badge.cancelled {
  color: #eb8b80;
  background: #4c3438;
}

.actions {
  display: flex;
  gap: 7px;
}

.action-button {
  border: 1px solid #405470;
  border-radius: 7px;
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 600;
  background: #303d51;
  color: #a7c8ff;
}

.action-button:hover {
  background: #3d506b;
}

.detail-action {
  background: #263d55;
  color: #8db9ff;
}

.delete-action {
  background: #473238;
  border-color: #67464e;
  color: #f0a099;
}

.empty-cell {
  padding: 45px !important;
  text-align: center;
  color: var(--color-muted) !important;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(9, 13, 19, 0.78);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.modal {
  padding: 28px;
  width: min(620px, 100%);
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.modal-header h2,
.delete-modal h2 {
  margin: 0;
  font-size: 19px;
}

.close-button {
  background: transparent;
  border: 0;
  color: #aab4c3;
  font-size: 26px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.full {
  grid-column: 1 / -1;
}

.modal-error {
  margin-top: 18px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}

.delete-modal {
  width: min(470px, 100%);
}

.delete-modal p {
  margin-top: 18px;
}

.delete-modal strong {
  color: #f1f5f9;
}

.warning {
  padding: 14px;
  border: 1px solid #55463a;
  border-radius: 8px;
  background: #39312d;
  color: #e6b985;
  font-size: 12px;
  line-height: 1.7;
}

.delete-confirm {
  min-height: 40px;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  background: #c95649;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 1100px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 650px) {
  .stats,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .filters,
  .panel-heading {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-select {
    max-width: none;
  }

  .panel-heading {
    padding: 18px;
  }

  .filters {
    padding: 0 18px 18px;
  }

  .modal {
    padding: 20px;
  }
}
</style>
