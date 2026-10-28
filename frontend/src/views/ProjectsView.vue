<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { isAxiosError } from 'axios'

import {
  projectService,
  type CreateProjectPayload,
  type Project,
  type ProjectStatus,
} from '../services/projects'

// --------------------------------------------------
// ESTADO REACTIVO
// --------------------------------------------------

const projects = ref<Project[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const successMessage = ref('')

const search = ref('')
const statusFilter = ref('')
const showCreateForm = ref(false)

// --------------------------------------------------
// FORMULARIO
// --------------------------------------------------

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

const statusOptions: {
  value: ProjectStatus
  label: string
}[] = [
  { value: 'PLANNED', label: 'Planificado' },
  { value: 'IN_PROGRESS', label: 'En progreso' },
  { value: 'ON_HOLD', label: 'En pausa' },
  { value: 'COMPLETED', label: 'Completado' },
  { value: 'CANCELLED', label: 'Cancelado' },
]

// --------------------------------------------------
// ESTADÍSTICAS DEL LISTADO
// --------------------------------------------------

const statistics = computed(() => ({
  total: projects.value.length,
  active: projects.value.filter((p) => p.status === 'IN_PROGRESS').length,
  planned: projects.value.filter((p) => p.status === 'PLANNED').length,
  completed: projects.value.filter((p) => p.status === 'COMPLETED').length,
}))

// --------------------------------------------------
// FILTRADO LOCAL
// --------------------------------------------------

const filteredProjects = computed(() => {
  const term = search.value.trim().toLowerCase()

  return projects.value.filter((project) => {
    const matchesSearch =
      !term ||
      project.name.toLowerCase().includes(term) ||
      project.code.toLowerCase().includes(term) ||
      project.manager_name.toLowerCase().includes(term)

    const matchesStatus = !statusFilter.value || project.status === statusFilter.value

    return matchesSearch && matchesStatus
  })
})

// --------------------------------------------------
// UTILIDADES
// --------------------------------------------------

function formatDate(value: string): string {
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

function getStatusClass(status: ProjectStatus): string {
  return status.toLowerCase().replaceAll('_', '-')
}

function getErrorMessage(errorValue: unknown): string {
  if (isAxiosError(errorValue)) {
    if (!errorValue.response) {
      return 'No se pudo conectar con Django. Verifica el servidor.'
    }

    const data: unknown = errorValue.response.data

    if (typeof data === 'object' && data !== null) {
      const messages: string[] = []

      for (const [field, value] of Object.entries(data)) {
        const fieldMessage = Array.isArray(value) ? value.map(String).join(', ') : String(value)

        messages.push(`${field}: ${fieldMessage}`)
      }

      if (messages.length > 0) {
        return messages.join(' | ')
      }
    }

    return `Error HTTP ${errorValue.response.status}`
  }

  return 'Ocurrió un error inesperado.'
}

// --------------------------------------------------
// API: CONSULTAR PROYECTOS
// --------------------------------------------------

async function loadProjects() {
  loading.value = true
  error.value = ''

  try {
    projects.value = await projectService.list()
  } catch (err) {
    error.value = getErrorMessage(err)
    projects.value = []
  } finally {
    loading.value = false
  }
}

// --------------------------------------------------
// API: CREAR PROYECTO
// --------------------------------------------------

async function createProject() {
  error.value = ''
  successMessage.value = ''

  if (!form.value.code.trim() || !form.value.name.trim()) {
    error.value = 'Código y nombre son obligatorios.'
    return
  }

  if (form.value.start_date && form.value.end_date && form.value.end_date < form.value.start_date) {
    error.value = 'La fecha de término no puede ser anterior a la de inicio.'
    return
  }

  saving.value = true

  try {
    const payload: CreateProjectPayload = {
      ...form.value,
      code: form.value.code.trim(),
      name: form.value.name.trim(),
      manager_name: form.value.manager_name.trim(),
    }

    const created = await projectService.create(payload)

    showCreateForm.value = false
    form.value = emptyForm()

    await loadProjects()

    successMessage.value = `Proyecto ${created.code} creado correctamente.`
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

function openCreateForm() {
  form.value = emptyForm()
  error.value = ''
  successMessage.value = ''
  showCreateForm.value = true
}

function closeCreateForm() {
  if (saving.value) return
  showCreateForm.value = false
  error.value = ''
}

// --------------------------------------------------
// CARGA INICIAL
// --------------------------------------------------

onMounted(loadProjects)
</script>

<template>
  <div class="projects-view">
    <!-- ENCABEZADO -->
    <header class="page-header">
      <div>
        <h1 class="page-title">Proyectos</h1>
        <p class="page-description">Administra los proyectos registrados en order-project.</p>
      </div>

      <button class="primary-button" type="button" @click="openCreateForm">+ Nuevo proyecto</button>
    </header>

    <!-- MENSAJES -->
    <div v-if="error" class="error-banner message-banner" role="alert">
      {{ error }}
    </div>

    <div v-if="successMessage" class="success-banner message-banner" role="status">
      {{ successMessage }}
    </div>

    <!-- TARJETAS DE RESUMEN -->
    <section class="stat-grid">
      <article class="panel stat-card">
        <span class="stat-label">Total proyectos</span>
        <strong class="stat-value">
          {{ statistics.total }}
        </strong>
      </article>

      <article class="panel stat-card">
        <span class="stat-label">En progreso</span>
        <strong class="stat-value blue">
          {{ statistics.active }}
        </strong>
      </article>

      <article class="panel stat-card">
        <span class="stat-label">Planificados</span>
        <strong class="stat-value yellow">
          {{ statistics.planned }}
        </strong>
      </article>

      <article class="panel stat-card">
        <span class="stat-label">Completados</span>
        <strong class="stat-value green">
          {{ statistics.completed }}
        </strong>
      </article>
    </section>

    <!-- LISTADO -->
    <section class="panel project-panel">
      <div class="panel-header">
        <div>
          <h2>Listado de proyectos</h2>
          <p>
            {{ filteredProjects.length }}
            proyectos visibles
          </p>
        </div>

        <button class="secondary-button" type="button" :disabled="loading" @click="loadProjects">
          {{ loading ? 'Cargando...' : 'Actualizar' }}
        </button>
      </div>

      <!-- FILTROS -->
      <div class="filter-row">
        <input
          v-model="search"
          class="form-control search-field"
          type="search"
          placeholder="Buscar por código, nombre o responsable..."
          aria-label="Buscar proyectos"
        />

        <select
          v-model="statusFilter"
          class="form-control status-filter"
          aria-label="Filtrar por estado"
        >
          <option value="">Todos los estados</option>

          <option v-for="option in statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <!-- TABLA -->
      <div class="table-container">
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
            </tr>
          </thead>

          <tbody>
            <tr v-for="project in filteredProjects" :key="project.id">
              <td class="code-cell">
                {{ project.code }}
              </td>

              <td>
                <div class="project-name">
                  {{ project.name }}
                </div>

                <div v-if="project.description" class="project-description">
                  {{ project.description }}
                </div>
              </td>

              <td>{{ project.manager_name }}</td>

              <td>
                <span class="status-badge" :class="getStatusClass(project.status)">
                  {{ project.status_display }}
                </span>
              </td>

              <td>{{ formatDate(project.start_date) }}</td>
              <td>{{ formatDate(project.end_date) }}</td>

              <td class="money-cell">
                {{ formatMoney(project.baseline_budget) }}
              </td>
            </tr>

            <tr v-if="!loading && filteredProjects.length === 0">
              <td colspan="7" class="empty-state">No hay proyectos que mostrar.</td>
            </tr>

            <tr v-if="loading">
              <td colspan="7" class="empty-state">Cargando proyectos...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- FORMULARIO MODAL -->
    <div v-if="showCreateForm" class="modal-backdrop">
      <section
        class="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
      >
        <div class="modal-header">
          <div>
            <h2 id="create-project-title">Nuevo proyecto</h2>
            <p>Completa los datos del proyecto.</p>
          </div>

          <button
            type="button"
            class="close-button"
            aria-label="Cerrar formulario"
            :disabled="saving"
            @click="closeCreateForm"
          >
            ×
          </button>
        </div>

        <form @submit.prevent="createProject">
          <div class="form-grid">
            <div>
              <label class="form-label" for="project-code"> Código * </label>

              <input
                id="project-code"
                v-model="form.code"
                class="form-control"
                type="text"
                maxlength="30"
                required
                placeholder="PRJ-003"
              />
            </div>

            <div>
              <label class="form-label" for="project-name"> Nombre * </label>

              <input
                id="project-name"
                v-model="form.name"
                class="form-control"
                type="text"
                maxlength="200"
                required
                placeholder="Nombre del proyecto"
              />
            </div>

            <div class="full-width">
              <label class="form-label" for="project-description"> Descripción </label>

              <textarea
                id="project-description"
                v-model="form.description"
                class="form-control"
                rows="3"
                placeholder="Descripción general del proyecto"
              ></textarea>
            </div>

            <div>
              <label class="form-label" for="project-manager"> Responsable * </label>

              <input
                id="project-manager"
                v-model="form.manager_name"
                class="form-control"
                type="text"
                maxlength="150"
                required
              />
            </div>

            <div>
              <label class="form-label" for="project-status"> Estado </label>

              <select id="project-status" v-model="form.status" class="form-control">
                <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div>
              <label class="form-label" for="project-start"> Fecha de inicio * </label>

              <input
                id="project-start"
                v-model="form.start_date"
                class="form-control"
                type="date"
                required
              />
            </div>

            <div>
              <label class="form-label" for="project-end"> Fecha de término * </label>

              <input
                id="project-end"
                v-model="form.end_date"
                class="form-control"
                type="date"
                required
              />
            </div>

            <div class="full-width">
              <label class="form-label" for="project-budget"> Presupuesto inicial (CLP) * </label>

              <input
                id="project-budget"
                v-model="form.baseline_budget"
                class="form-control"
                type="number"
                min="0"
                step="0.01"
                required
              />
            </div>
          </div>

          <div v-if="error" class="error-banner form-error">
            {{ error }}
          </div>

          <div class="modal-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="saving"
              @click="closeCreateForm"
            >
              Cancelar
            </button>

            <button class="primary-button" type="submit" :disabled="saving">
              {{ saving ? 'Guardando...' : 'Crear proyecto' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.projects-view {
  width: 100%;
}

.message-banner {
  margin-bottom: 20px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 15px;
  padding: 22px;
  min-height: 118px;
}

.stat-label {
  font-size: 12px;
  color: var(--color-muted);
}

.stat-value {
  font-size: 29px;
  font-weight: 700;
  line-height: 1;
}

.stat-value.blue {
  color: var(--color-primary);
}

.stat-value.yellow {
  color: var(--color-warning);
}

.stat-value.green {
  color: var(--color-success);
}

.project-panel {
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
}

.panel-header h2 {
  margin: 0 0 7px;
  font-size: 16px;
}

.panel-header p {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
}

.filter-row {
  display: flex;
  gap: 12px;
  padding: 0 24px 22px;
}

.search-field {
  flex: 1;
}

.status-filter {
  max-width: 210px;
}

.table-container {
  width: 100%;
  overflow-x: auto;
}

.projects-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  white-space: nowrap;
}

.projects-table th {
  padding: 15px 18px;
  background: #20262f;
  color: #9ba9ba;
  font-size: 11px;
  font-weight: 600;
}

.projects-table td {
  padding: 18px;
  border-top: 1px solid var(--color-border);
  color: #c8d1dd;
  font-size: 12px;
}

.projects-table tbody tr:hover {
  background: #2b333f;
}

.code-cell {
  color: #85b1ff !important;
  font-weight: 600;
}

.project-name {
  max-width: 240px;
  color: #f1f5f9;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-description {
  max-width: 240px;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #8795a8;
  font-size: 11px;
}

.money-cell {
  font-variant-numeric: tabular-nums;
}

.status-badge {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 6px;
  background: #37404b;
  color: #cbd5e1;
  font-size: 10px;
  font-weight: 600;
}

.status-badge.planned {
  background: #493d2b;
  color: #f4b860;
}

.status-badge.in-progress {
  background: #273c5a;
  color: #85b1ff;
}

.status-badge.on-hold {
  background: #514132;
  color: #f4b860;
}

.status-badge.completed {
  background: #29443d;
  color: #5cc8a1;
}

.status-badge.cancelled {
  background: #4c3438;
  color: #eb8b80;
}

.empty-state {
  padding: 50px 20px !important;
  text-align: center;
  color: var(--color-muted) !important;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(9, 13, 19, 0.75);
}

.modal {
  width: min(620px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 28px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 24px;
}

.modal-header h2 {
  margin: 0 0 8px;
  font-size: 19px;
}

.modal-header p {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
}

.close-button {
  width: 32px;
  height: 32px;
  border: 0;
  background: transparent;
  color: #aab4c3;
  font-size: 26px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.full-width {
  grid-column: 1 / -1;
}

.form-error {
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

@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .stat-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .filter-row {
    flex-direction: column;
  }

  .status-filter {
    max-width: none;
  }

  .panel-header {
    padding: 18px;
  }

  .filter-row {
    padding: 0 18px 18px;
  }

  .modal {
    padding: 20px;
  }
}
</style>
