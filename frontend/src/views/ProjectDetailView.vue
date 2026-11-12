<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { isAxiosError } from 'axios'

import RescheduleTaskModal from '../components/scheduling/RescheduleTaskModal.vue'
import DependenciesManager from '../components/scheduling/DependenciesManager.vue'
import CalendarManager from '../components/scheduling/CalendarManager.vue'
import type { ScheduleResult } from '../services/scheduling'

import { projectService, type Project } from '../services/projects'
import {
  taskService,
  type Task,
  type TaskPayload,
  type TaskGeneralUpdatePayload,
  type TaskStatus,
} from '../services/tasks'

// ==================================================
// ROUTER Y PROPIEDADES
// ==================================================

const props = defineProps<{
  id: string
}>()

const router = useRouter()

const projectId = computed(() => Number(props.id))

// ==================================================
// ESTADO REACTIVO
// ==================================================

const project = ref<Project | null>(null)
const tasks = ref<Task[]>([])

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)

const error = ref('')
const formError = ref('')
const deleteError = ref('')
const successMessage = ref('')

const search = ref('')
const statusFilter = ref('')

const showForm = ref(false)
const showDelete = ref(false)
const taskToReschedule = ref<Task | null>(null)
const schedulingTab = ref<'dependencies' | 'calendar'>('dependencies')

const editingTask = ref<Task | null>(null)
const taskToDelete = ref<Task | null>(null)

const isEditing = computed(() => editingTask.value !== null)

const statusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'PENDING', label: 'Pendiente' },
  { value: 'IN_PROGRESS', label: 'En progreso' },
  { value: 'COMPLETED', label: 'Completada' },
  { value: 'CANCELLED', label: 'Cancelada' },
]

// ==================================================
// FORMULARIO
// ==================================================

function emptyForm(): TaskPayload {
  return {
    project: projectId.value,
    name: '',
    description: '',
    status: 'PENDING',
    start_date: '',
    end_date: '',
    position: 0,
  }
}

const form = ref<TaskPayload>(emptyForm())

// ==================================================
// CÁLCULOS PARA LA INTERFAZ
// ==================================================

const filteredTasks = computed(() => {
  const term = search.value.trim().toLowerCase()

  return tasks.value.filter((task) => {
    const matchesText =
      !term ||
      task.name.toLowerCase().includes(term) ||
      task.description.toLowerCase().includes(term)

    const matchesStatus = !statusFilter.value || task.status === statusFilter.value

    return matchesText && matchesStatus
  })
})

const taskCounts = computed(() => ({
  total: tasks.value.length,
  pending: tasks.value.filter((t) => t.status === 'PENDING').length,
  inProgress: tasks.value.filter((t) => t.status === 'IN_PROGRESS').length,
  completed: tasks.value.filter((t) => t.status === 'COMPLETED').length,
}))

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
  if (!isAxiosError(err)) {
    return 'Ocurrió un error inesperado.'
  }

  if (!err.response) {
    return 'No se pudo conectar con Django.'
  }

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
// CONSULTAR PROYECTO Y TAREAS
// ==================================================

async function loadData() {
  loading.value = true
  error.value = ''
  project.value = null
  tasks.value = []

  if (!Number.isInteger(projectId.value) || projectId.value <= 0) {
    error.value = 'El identificador del proyecto no es válido.'
    loading.value = false
    return
  }

  try {
    const [projectResponse, taskResponse] = await Promise.all([
      projectService.getById(projectId.value),
      taskService.list({
        project: projectId.value,
        ordering: 'position',
      }),
    ])

    project.value = projectResponse
    tasks.value = taskResponse
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function refreshTasks(): Promise<boolean> {
  try {
    tasks.value = await taskService.list({
      project: projectId.value,
      ordering: 'position',
    })
    return true
  } catch (err) {
    error.value = getErrorMessage(err)
    return false
  }
}

// ==================================================
// MODAL CREACIÓN / EDICIÓN
// ==================================================

function openCreateForm() {
  if (!project.value) return

  editingTask.value = null
  form.value = {
    ...emptyForm(),
    position: tasks.value.length + 1,
    start_date: project.value.start_date,
    end_date: project.value.start_date,
  }

  formError.value = ''
  successMessage.value = ''
  showForm.value = true
}

function openEditForm(task: Task) {
  editingTask.value = task

  form.value = {
    project: task.project,
    name: task.name,
    description: task.description,
    status: task.status,
    start_date: task.start_date,
    end_date: task.end_date,
    position: task.position,
  }

  formError.value = ''
  successMessage.value = ''
  showForm.value = true
}

function closeForm() {
  if (saving.value) return

  showForm.value = false
  editingTask.value = null
  formError.value = ''
}

function validateForm(): boolean {
  if (!project.value) return false

  if (!form.value.name.trim()) {
    formError.value = 'El nombre de la tarea es obligatorio.'
    return false
  }

  // Las fechas solo se validan durante la creación inicial.
  // Las reprogramaciones de actividades existentes pasan por Scheduling.
  if (!isEditing.value) {
    if (!form.value.start_date || !form.value.end_date) {
      formError.value = 'Debes ingresar ambas fechas.'
      return false
    }

    if (form.value.end_date < form.value.start_date) {
      formError.value = 'La fecha de término no puede ser anterior al inicio.'
      return false
    }

    if (
      form.value.start_date < project.value.start_date ||
      form.value.end_date > project.value.end_date
    ) {
      formError.value = 'Las fechas de la tarea deben estar dentro del proyecto.'
      return false
    }
  }

  if (!Number.isInteger(form.value.position) || form.value.position < 0) {
    formError.value = 'La posición debe ser un entero igual o mayor que cero.'
    return false
  }

  return true
}

async function saveTask() {
  if (saving.value || !validateForm()) return

  saving.value = true
  formError.value = ''
  error.value = ''

  const existing = editingTask.value

  try {
    const payload: TaskPayload = {
      ...form.value,
      name: form.value.name.trim(),
      description: form.value.description.trim(),
      project: projectId.value,
    }

    let saved: Task

    if (existing) {
      // El CRUD solo recibe campos generales: jamás enviamos
      // start_date, end_date ni estimated_duration_days.
      const changes: TaskGeneralUpdatePayload = {
        name: payload.name,
        description: payload.description,
        status: payload.status,
        position: payload.position,
      }

      saved = await taskService.update(existing.id, changes)
    } else {
      saved = await taskService.create(payload)
    }

    showForm.value = false
    editingTask.value = null

    successMessage.value = existing
      ? `Tarea "${saved.name}" actualizada correctamente.`
      : `Tarea "${saved.name}" creada correctamente.`

    await refreshTasks()
  } catch (err) {
    formError.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

// ==================================================
// ELIMINAR TAREA
// ==================================================

function openDeleteModal(task: Task) {
  taskToDelete.value = task
  deleteError.value = ''
  successMessage.value = ''
  showDelete.value = true
}

function closeDeleteModal() {
  if (deleting.value) return

  showDelete.value = false
  taskToDelete.value = null
  deleteError.value = ''
}

async function confirmDelete() {
  if (!taskToDelete.value || deleting.value) return

  deleting.value = true
  deleteError.value = ''

  const selected = taskToDelete.value

  try {
    await taskService.remove(selected.id)

    showDelete.value = false
    taskToDelete.value = null

    successMessage.value = `Tarea "${selected.name}" eliminada correctamente.`

    await refreshTasks()
  } catch (err) {
    deleteError.value = getErrorMessage(err)
  } finally {
    deleting.value = false
  }
}

// ==================================================
// REPROGRAMACIÓN DE ACTIVIDADES
// ==================================================

function openRescheduleModal(task: Task) {
  taskToReschedule.value = task
  successMessage.value = ''
  error.value = ''
}

function closeRescheduleModal() {
  taskToReschedule.value = null
}

async function onRescheduleConfirmed(result: ScheduleResult) {
  taskToReschedule.value = null
  successMessage.value = `Reprogramación aplicada: ${result.updated_tasks} actividad(es) actualizada(s).`
  await refreshTasks()
}

// ==================================================
// NAVEGACIÓN Y CARGA INICIAL
// ==================================================

function goBack() {
  router.push({ name: 'projects' })
}

// Se ejecuta inicialmente y también si cambia el ID de la ruta.
watch(
  () => props.id,
  () => {
    showForm.value = false
    showDelete.value = false
    taskToReschedule.value = null
    successMessage.value = ''
    loadData()
  },
  { immediate: true },
)
</script>

<template>
  <div class="detail-view">
    <button class="back-link" type="button" @click="goBack">← Volver a proyectos</button>

    <div v-if="error" class="error-banner notice" role="alert">
      {{ error }}
    </div>

    <div v-if="successMessage" class="success-banner notice" role="status">
      {{ successMessage }}
    </div>

    <p v-if="loading" class="muted">Cargando información del proyecto...</p>

    <template v-if="project && !loading">
      <!-- ENCABEZADO -->
      <header class="page-header">
        <div>
          <div class="heading-meta">
            <span class="project-code">{{ project.code }}</span>
            <span class="status-badge" :class="statusClass(project.status)">
              {{ project.status_display }}
            </span>
          </div>

          <h1 class="page-title">{{ project.name }}</h1>

          <p class="page-description">
            {{ project.description || 'Sin descripción.' }}
          </p>
        </div>
      </header>

      <!-- INFORMACIÓN DEL PROYECTO -->
      <section class="info-grid">
        <article class="panel info-card">
          <span class="muted">Responsable</span>
          <strong>{{ project.manager_name }}</strong>
        </article>

        <article class="panel info-card">
          <span class="muted">Presupuesto inicial</span>
          <strong>{{ formatMoney(project.baseline_budget) }}</strong>
        </article>

        <article class="panel info-card">
          <span class="muted">Fecha de inicio</span>
          <strong>{{ formatDate(project.start_date) }}</strong>
        </article>

        <article class="panel info-card">
          <span class="muted">Fecha de término</span>
          <strong>{{ formatDate(project.end_date) }}</strong>
        </article>
      </section>

      <!-- SECCIÓN DE TAREAS -->
      <section class="panel tasks-panel">
        <div class="section-header">
          <div>
            <h2>Actividades del proyecto</h2>
            <p class="muted">
              {{ taskCounts.total }} registradas · {{ taskCounts.pending }} pendientes ·
              {{ taskCounts.inProgress }} en progreso · {{ taskCounts.completed }} completadas
            </p>
          </div>

          <button type="button" class="primary-button" @click="openCreateForm">
            + Nueva tarea
          </button>
        </div>

        <div class="filters">
          <input
            v-model="search"
            class="form-control"
            type="search"
            placeholder="Buscar actividad..."
            aria-label="Buscar actividades"
          />

          <select
            v-model="statusFilter"
            class="form-control status-select"
            aria-label="Filtrar actividades por estado"
          >
            <option value="">Todos los estados</option>
            <option v-for="option in statusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>

          <button type="button" class="secondary-button" @click="refreshTasks">Actualizar</button>
        </div>

        <div class="table-scroll">
          <table class="tasks-table">
            <thead>
              <tr>
                <th>Orden</th>
                <th>Actividad</th>
                <th>Estado</th>
                <th>Inicio</th>
                <th>Término</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="task in filteredTasks" :key="task.id">
                <td>{{ task.position }}</td>

                <td>
                  <strong class="task-name">{{ task.name }}</strong>
                  <div class="muted task-description">
                    {{ task.description || 'Sin descripción' }}
                  </div>
                </td>

                <td>
                  <span class="status-badge" :class="statusClass(task.status)">
                    {{ task.status_display }}
                  </span>
                </td>

                <td>{{ formatDate(task.start_date) }}</td>
                <td>{{ formatDate(task.end_date) }}</td>

                <td>
                  <div class="actions">
                    <button type="button" class="action-button" @click="openEditForm(task)">
                      Editar
                    </button>

                    <button
                      type="button"
                      class="action-button"
                      @click="openRescheduleModal(task)"
                    >
                      Reprogramar
                    </button>

                    <button
                      type="button"
                      class="action-button danger-text"
                      @click="openDeleteModal(task)"
                    >
                      Eliminar
                    </button>
                  </div>
                </td>
              </tr>

              <tr v-if="filteredTasks.length === 0">
                <td colspan="6" class="empty-cell">No hay tareas que coincidan con los filtros.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- CONFIGURACIÓN DE PROGRAMACIÓN -->
      <section class="panel scheduling-panel">
        <div class="section-header scheduling-heading">
          <div>
            <h2>Configuración de programación</h2>
            <p class="muted">Administra las relaciones entre actividades y el calendario del proyecto.</p>
          </div>
        </div>
        <div class="scheduling-tabs" role="tablist" aria-label="Configuración de programación">
          <button type="button" role="tab" :aria-selected="schedulingTab === 'dependencies'" :class="{ active: schedulingTab === 'dependencies' }" @click="schedulingTab = 'dependencies'">Dependencias</button>
          <button type="button" role="tab" :aria-selected="schedulingTab === 'calendar'" :class="{ active: schedulingTab === 'calendar' }" @click="schedulingTab = 'calendar'">Calendario laboral</button>
        </div>
        <DependenciesManager v-if="schedulingTab === 'dependencies'" :project-id="project.id" :tasks="tasks" />
        <CalendarManager v-else :project-id="project.id" :tasks-count="tasks.length" />
      </section>
    </template>

    <!-- MODAL DE REPROGRAMACIÓN -->
    <RescheduleTaskModal
      v-if="taskToReschedule && project"
      :key="taskToReschedule.id"
      :task="taskToReschedule"
      :project-id="project.id"
      :project-start-date="project.start_date"
      :project-end-date="project.end_date"
      @close="closeRescheduleModal"
      @confirmed="onRescheduleConfirmed"
    />

    <!-- MODAL CREAR / EDITAR -->
    <div v-if="showForm" class="modal-backdrop">
      <section
        class="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-form-title"
      >
        <div class="modal-header">
          <h2 id="task-form-title">
            {{ isEditing ? 'Editar tarea' : 'Nueva tarea' }}
          </h2>

          <button
            class="close-button"
            type="button"
            :disabled="saving"
            aria-label="Cerrar formulario"
            @click="closeForm"
          >
            ×
          </button>
        </div>

        <form @submit.prevent="saveTask">
          <div class="form-grid">
            <div class="full">
              <label class="form-label" for="task-name"> Nombre * </label>
              <input
                id="task-name"
                v-model="form.name"
                class="form-control"
                maxlength="200"
                required
              />
            </div>

            <div class="full">
              <label class="form-label" for="task-description"> Descripción </label>
              <textarea
                id="task-description"
                v-model="form.description"
                class="form-control"
                rows="3"
              ></textarea>
            </div>

            <div>
              <label class="form-label" for="task-status"> Estado </label>
              <select id="task-status" v-model="form.status" class="form-control">
                <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div>
              <label class="form-label" for="task-position"> Posición </label>
              <input
                id="task-position"
                v-model.number="form.position"
                class="form-control"
                type="number"
                min="0"
                step="1"
                required
              />
            </div>

            <!-- Fechas editables únicamente al crear una actividad. -->
            <template v-if="!isEditing">
              <div>
                <label class="form-label" for="task-start">Fecha de inicio *</label>
                <input
                  id="task-start"
                  v-model="form.start_date"
                  class="form-control"
                  type="date"
                  :min="project?.start_date"
                  :max="project?.end_date"
                  required
                />
              </div>

              <div>
                <label class="form-label" for="task-end">Fecha de término *</label>
                <input
                  id="task-end"
                  v-model="form.end_date"
                  class="form-control"
                  type="date"
                  :min="project?.start_date"
                  :max="project?.end_date"
                  required
                />
              </div>
            </template>

            <!-- En edición solo se informan las fechas existentes. -->
            <div v-else class="full schedule-summary">
              <span class="form-label">Planificación actual</span>
              <p>
                Inicio: <strong>{{ formatDate(form.start_date) }}</strong>
                · Término: <strong>{{ formatDate(form.end_date) }}</strong>
              </p>
              <p class="muted">
                La planificación está protegida. La reprogramación de fechas y
                duraciones se habilitará en el módulo de Scheduling.
              </p>
            </div>
          </div>

          <div v-if="formError" class="error-banner modal-error" role="alert">
            {{ formError }}
          </div>

          <div class="modal-actions">
            <button type="button" class="secondary-button" :disabled="saving" @click="closeForm">
              Cancelar
            </button>

            <button type="submit" class="primary-button" :disabled="saving">
              {{ saving ? 'Guardando...' : isEditing ? 'Guardar cambios' : 'Crear tarea' }}
            </button>
          </div>
        </form>
      </section>
    </div>

    <!-- MODAL ELIMINAR -->
    <div v-if="showDelete && taskToDelete" class="modal-backdrop">
      <section
        class="modal delete-modal panel"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-task-title"
      >
        <h2 id="delete-task-title">¿Eliminar tarea?</h2>

        <p class="muted">
          Se eliminará permanentemente
          <strong>{{ taskToDelete.name }}</strong
          >. Esta operación no se puede deshacer.
        </p>

        <div v-if="deleteError" class="error-banner modal-error" role="alert">
          {{ deleteError }}
        </div>

        <div class="modal-actions">
          <button
            type="button"
            class="secondary-button"
            :disabled="deleting"
            @click="closeDeleteModal"
          >
            Cancelar
          </button>

          <button type="button" class="delete-button" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? 'Eliminando...' : 'Sí, eliminar' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.detail-view {
  width: 100%;
}

.back-link {
  border: 0;
  background: transparent;
  color: #8fb6ff;
  padding: 0;
  margin-bottom: 28px;
  font-size: 12px;
}

.back-link:hover {
  color: #c6dcff;
}

.notice {
  margin-bottom: 20px;
}

.muted {
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.6;
}

.heading-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.project-code {
  color: #8fb6ff;
  font-size: 12px;
  font-weight: 700;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.info-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.info-card strong {
  font-size: 15px;
  overflow-wrap: anywhere;
}

.tasks-panel {
  overflow: hidden;
}

.scheduling-panel { margin-top: 24px; overflow: hidden; }
.scheduling-heading { padding-bottom: 16px; }
.scheduling-tabs { display: flex; gap: 8px; padding: 0 24px 10px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap; }
.scheduling-tabs button { background: #303d51; border: 1px solid #405470; color: #aab4c3; border-radius: 8px; padding: 10px 14px; font-size: 12px; }
.scheduling-tabs button.active { background: #273c5a; border-color: #4f8cff; color: #b9d2ff; }
@media(max-width:650px) { .scheduling-tabs { padding: 0 16px 10px; } }

.section-header {
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.section-header h2 {
  font-size: 16px;
  margin: 0 0 7px;
}

.section-header p {
  margin: 0;
}

.filters {
  padding: 0 24px 22px;
  display: flex;
  gap: 12px;
}

.filters > input {
  flex: 1;
}

.status-select {
  max-width: 210px;
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

.tasks-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  white-space: nowrap;
}

.tasks-table th {
  background: #20262f;
  color: #9ba9ba;
  padding: 15px 18px;
  font-size: 11px;
}

.tasks-table td {
  padding: 18px;
  border-top: 1px solid var(--color-border);
  font-size: 12px;
  color: #cbd5e1;
}

.tasks-table tbody tr:hover {
  background: #2b333f;
}

.task-name {
  color: #f1f5f9;
}

.task-description {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 5px;
}

.actions {
  display: flex;
  gap: 8px;
}

.action-button {
  background: #303d51;
  color: #9ec0ff;
  border: 1px solid #405470;
  border-radius: 7px;
  padding: 8px 11px;
  font-size: 11px;
}

.action-button:hover {
  background: #3a4e6a;
}

.danger-text {
  background: #473238;
  border-color: #67464e;
  color: #f0a099;
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

.status-badge.planned,
.status-badge.pending,
.status-badge.on-hold {
  background: #493d2b;
  color: #f4b860;
}

.status-badge.in-progress {
  background: #273c5a;
  color: #85b1ff;
}

.status-badge.completed {
  background: #29443d;
  color: #5cc8a1;
}

.status-badge.cancelled {
  background: #4c3438;
  color: #eb8b80;
}

.empty-cell {
  text-align: center;
  padding: 45px !important;
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
  background: rgba(9, 13, 19, 0.78);
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

.schedule-summary {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #20262f;
  padding: 14px 16px;
}

.schedule-summary p {
  margin: 8px 0 0;
  font-size: 12px;
  color: #cbd5e1;
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

.delete-button {
  min-height: 40px;
  padding: 0 16px;
  background: #c95649;
  color: #fff;
  border: 0;
  border-radius: 8px;
  font-weight: 600;
  font-size: 12px;
}

.delete-button:hover:not(:disabled) {
  background: #ad4338;
}

@media (max-width: 1100px) {
  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 650px) {
  .info-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .filters,
  .section-header {
    flex-direction: column;
    align-items: stretch;
  }

  .status-select {
    max-width: none;
  }

  .section-header {
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
