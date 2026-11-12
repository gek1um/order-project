<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import GanttChart from '../components/scheduling/GanttChart.vue'
import MilestonesManager from '../components/scheduling/MilestonesManager.vue'
import MilestoneKpisManager from '../components/scheduling/MilestoneKpisManager.vue'
import RescheduleTaskModal from '../components/scheduling/RescheduleTaskModal.vue'
import { taskService, type Task } from '../services/tasks'
import { milestoneService, type Milestone } from '../services/milestones'
import { isOverdue, isFinishedLate, localTodayISO, overdueDays, progressSummary } from '../utils/scheduleHealth'
import { isAxiosError } from 'axios'
import { projectService, type Project } from '../services/projects'
import {
  schedulingService,
  type ProjectSchedule,
  type ScheduleTask,
} from '../services/scheduling'

const props = withDefaults(defineProps<{ section?: 'all' | 'gantt' | 'milestones' | 'kpis' }>(), { section: 'all' })
const selectedKpiId = ref<number | null>(null)
const selectedKpi = computed(() => milestones.value.find(m => m.id === selectedKpiId.value) ?? null)
const isAll = computed(() => props.section === 'all')
const showGantt = computed(() => props.section === 'all' || props.section === 'gantt')
const showMilestones = computed(() => props.section === 'all' || props.section === 'milestones')
const showKpis = computed(() => props.section === 'kpis')
const pageTitle = computed(() => ({ all: 'Programación', gantt: 'Carta Gantt', milestones: 'Hitos del proyecto', kpis: 'KPI por hitos' })[props.section])
const pageDescription = computed(() => ({ all: 'Consulta el cronograma vigente, sus dependencias y el calendario de cada proyecto.', gantt: 'Visualiza la planificación, la ejecución real y las dependencias. Reprograma actividades desde el gráfico.', milestones: 'Administra los hitos del proyecto, sus criterios de aceptación y las actividades asociadas.', kpis: 'Selecciona un hito para gestionar sus indicadores, metas y mediciones.' })[props.section])
const projects = ref<Project[]>([])
const selectedProjectId = ref<number | null>(null)
const schedule = ref<ProjectSchedule | null>(null)
const milestones = ref<Milestone[]>([])
const loadingProjects = ref(false)
const loadingSchedule = ref(false)
const error = ref('')
const selectedTask = ref<Task | null>(null)
const selectingTask = ref(false)
const actionError = ref('')
const successMessage = ref('')
let selectionVersion = 0

async function openReschedule(taskId: number) {
  const version = ++selectionVersion
  const projectId = selectedProjectId.value
  if (projectId === null || selectingTask.value) return
  selectingTask.value = true
  actionError.value = ''
  successMessage.value = ''
  try {
    const task = await taskService.getById(taskId)
    if (version !== selectionVersion || selectedProjectId.value !== projectId) return
    if (task.project !== projectId) {
      actionError.value = 'La actividad no pertenece al proyecto seleccionado.'
      return
    }
    selectedTask.value = task
  } catch (err) {
    if (version === selectionVersion) actionError.value = getErrorMessage(err)
  } finally {
    if (version === selectionVersion) selectingTask.value = false
  }
}

function closeReschedule() {
  selectedTask.value = null
}

async function onRescheduleConfirmed() {
  selectedTask.value = null
  actionError.value = ''
  successMessage.value = 'Reprogramación confirmada. El cronograma fue actualizado.'
  await loadSchedule()
}

let requestVersion = 0
const todayISO = localTodayISO()

function getErrorMessage(err: unknown): string {
  if (!isAxiosError(err)) return 'Ocurrió un error inesperado.'
  if (!err.response) return 'No se pudo conectar con el backend de Django.'
  const data: unknown = err.response.data
  if (typeof data === 'object' && data !== null) {
    const messages = Object.entries(data).map(([key, value]) => {
      const content = Array.isArray(value) ? value.map(String).join(', ') : String(value)
      return key === 'detail' ? content : `${key}: ${content}`
    })
    if (messages.length) return messages.join(' | ')
  }
  return `Error HTTP ${err.response.status}.`
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return year && month && day ? `${day}/${month}/${year}` : value
}

function calendarDayDifference(planned: string, actual: string | null): string {
  if (!actual) return '—'
  const dayValue = (value: string): number => {
    const [year, month, day] = value.split('-').map(Number)
    return Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)
  }
  const difference = Math.round((dayValue(actual) - dayValue(planned)) / 86_400_000)
  if (difference === 0) return '0 (a tiempo)'
  return difference > 0 ? `+${difference} (después)` : `${difference} (antes)`
}

function statusLabel(status: ScheduleTask['status']): string {
  const labels: Record<ScheduleTask['status'], string> = {
    PENDING: 'Pendiente',
    IN_PROGRESS: 'En progreso',
    COMPLETED: 'Completada',
    CANCELLED: 'Cancelada',
  }
  return labels[status]
}

async function loadProjects() {
  loadingProjects.value = true
  error.value = ''
  try {
    projects.value = await projectService.list()
    if (selectedProjectId.value === null && projects.value.length > 0) {
      selectedProjectId.value = projects.value[0]?.id ?? null
    }
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loadingProjects.value = false
  }
}

async function loadSchedule() {
  const version = ++requestVersion
  const id = selectedProjectId.value
  schedule.value = null
  milestones.value = []
  selectedKpiId.value = null
  error.value = ''
  if (id === null) {
    loadingSchedule.value = false
    return
  }
  loadingSchedule.value = true
  try {
    const [result, milestoneResult] = await Promise.all([
      schedulingService.getProjectSchedule(id), milestoneService.list(id),
    ])
    if (version === requestVersion) { schedule.value = result; milestones.value = milestoneResult }
  } catch (err) {
    if (version === requestVersion) error.value = getErrorMessage(err)
  } finally {
    if (version === requestVersion) loadingSchedule.value = false
  }
}

watch(selectedProjectId, () => {
  ++selectionVersion
  selectingTask.value = false
  selectedTask.value = null
  actionError.value = ''
  successMessage.value = ''
  void loadSchedule()
})
onMounted(() => { void loadProjects() })

const health = computed(() => progressSummary(schedule.value?.tasks ?? [], todayISO))

const counts = computed(() => {
  const tasks = schedule.value?.tasks ?? []
  return {
    total: tasks.length,
    pending: tasks.filter(task => task.status === 'PENDING').length,
    inProgress: tasks.filter(task => task.status === 'IN_PROGRESS').length,
    completed: tasks.filter(task => task.status === 'COMPLETED').length,
  }
})

// Diagnóstico informativo de consistencia. NO sustituye las
// validaciones transaccionales del backend.
const warnings = computed(() => {
  const result = schedule.value
  if (!result) return []
  const issues: string[] = []
  const calendar = result.calendar
  const exceptionMap = new Map(calendar.exceptions.map(entry => [entry.date, entry.is_working]))
  const isWorking = (dateString: string): boolean => {
    if (exceptionMap.has(dateString)) return exceptionMap.get(dateString) === true
    const weekday = new Date(`${dateString}T12:00:00`).getDay()
    const pythonWeekday = (weekday + 6) % 7
    return calendar.working_weekdays.includes(pythonWeekday)
  }

  for (const task of result.tasks) {
    if (task.start_date < result.project.start_date || task.end_date > result.project.end_date) {
      issues.push(`${task.name}: sus fechas están fuera del período del proyecto.`)
    }
    if (task.end_date < task.start_date) {
      issues.push(`${task.name}: la fecha de término es anterior al inicio.`)
    }
    if (!isWorking(task.start_date) || !isWorking(task.end_date)) {
      issues.push(`${task.name}: el inicio o término coincide con un día no laborable.`)
    }
  }
  return issues
})
</script>

<template>
  <div class="scheduling-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">{{ pageTitle }}</h1>
        <p class="page-description">{{ pageDescription }}</p>
      </div>
      <button class="secondary-button" type="button" :disabled="loadingProjects || loadingSchedule" @click="loadSchedule">Actualizar cronograma</button>
    </header>

    <section class="panel selector-panel">
      <label class="form-label" for="project-select">Proyecto</label>
      <select id="project-select" v-model.number="selectedProjectId" class="form-control" :disabled="loadingProjects || projects.length === 0">
        <option :value="null" disabled>Seleccionar proyecto...</option>
        <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.code }} — {{ project.name }}</option>
      </select>
      <p v-if="!loadingProjects && projects.length === 0" class="muted">Todavía no existen proyectos. Crea uno desde la sección Proyectos.</p>
    </section>

    <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
    <div v-if="actionError" class="error-banner" role="alert">{{ actionError }}</div>
    <p v-if="successMessage" class="notice-ok success-banner" role="status">{{ successMessage }}</p>
    <p v-if="selectingTask" class="muted">Preparando actividad para reprogramar...</p>
    <p v-if="loadingProjects || loadingSchedule" class="muted">Cargando datos de programación...</p>

    <template v-if="schedule && !loadingSchedule">
      <section v-if="isAll || props.section === 'gantt'" class="summary-grid">
        <article class="panel stat-card"><span class="muted">Actividades</span><strong>{{ counts.total }}</strong></article>
        <article class="panel stat-card"><span class="muted">Pendientes</span><strong>{{ counts.pending }}</strong></article>
        <article class="panel stat-card"><span class="muted">En progreso</span><strong>{{ counts.inProgress }}</strong></article>
        <article class="panel stat-card"><span class="muted">Dependencias</span><strong>{{ schedule.dependencies_count }}</strong></article>
        <article class="panel stat-card"><span class="muted">Avance promedio*</span><strong>{{ health.averageProgress }}%</strong></article>
        <article class="panel stat-card" :class="{ 'stat-alert': health.overdue > 0 }"><span class="muted">Actividades atrasadas</span><strong>{{ health.overdue }}</strong></article>
        <article class="panel stat-card"><span class="muted">Finalizadas fuera de plazo</span><strong>{{ health.finishedLate }}</strong></article>
        <article class="panel stat-card"><span class="muted">Finalizadas en plazo</span><strong>{{ health.finishedOnTime }}</strong></article>
      </section>

      <p v-if="isAll || props.section === 'gantt'" class="muted">* Avance promedio simple de las actividades no canceladas. No está ponderado por duración ni por costo. Retrasos calculados en días calendario respecto del día actual.</p>

      <section class="panel section-panel">
        <div class="section-heading-row">
          <div>
            <h2>{{ schedule.project.name }}</h2>
            <p class="muted">{{ formatDate(schedule.project.start_date) }} — {{ formatDate(schedule.project.end_date) }}</p>
          </div>
          <RouterLink :to="{ name: 'project-detail', params: { id: schedule.project.id } }" class="primary-button">Administrar actividades</RouterLink>
        </div>
        <p class="muted">Calendario: {{ schedule.calendar.source === 'configured' ? 'personalizado' : 'predeterminado (lunes a viernes)' }} · {{ schedule.calendar.exceptions.length }} excepciones.</p>
      </section>

      <section v-if="isAll" class="panel section-panel">
        <h2>Revisión rápida de consistencia</h2>
        <p class="muted">Comprobación visual de días laborables y límites del proyecto. Las restricciones FS/SS/FF/SF y la integridad de escritura deben validarse en Django.</p>
        <p v-if="warnings.length === 0" class="notice-ok">No se detectaron problemas de fechas en esta revisión básica.</p>
        <ul v-else class="warning-list"><li v-for="(warning, index) in warnings" :key="index">{{ warning }}</li></ul>
      </section>

      <section v-if="showGantt" id="carta-gantt" class="panel section-panel navigation-target">
        <GanttChart :schedule="schedule" :milestones="milestones" @select-task="openReschedule" />
        <p class="muted gantt-help">Selecciona una barra planificada o el botón «Reprogramar» para simular cambios. Las barras no se arrastran y la simulación no modifica datos.</p>
      </section>

      <RescheduleTaskModal
        v-if="selectedTask"
        :key="selectedTask.id"
        :task="selectedTask"
        :project-id="schedule.project.id"
        :project-start-date="schedule.project.start_date"
        :project-end-date="schedule.project.end_date"
        @close="closeReschedule"
        @confirmed="onRescheduleConfirmed"
      />

      <section v-if="isAll" class="panel section-panel">
        <div class="section-heading-row"><h2>Actividades del cronograma</h2><span class="muted">{{ counts.completed }} completadas</span></div>
        <div class="table-scroll">
          <table class="data-table">
            <thead><tr><th>Actividad</th><th>Estado</th><th>Inicio plan.</th><th>Término plan.</th><th>Inicio real</th><th>Término real</th><th>Duración plan. (laboral)</th><th>Duración real (laboral)</th><th>Desfase de término (días calendario)</th><th>Avance</th><th>Alerta de plazo</th></tr></thead>
            <tbody>
              <tr v-for="task in schedule.tasks" :key="task.id" :class="{ 'row-overdue': isOverdue(task, todayISO) }">
                <td>{{ task.name }}</td><td>{{ statusLabel(task.status) }}</td><td>{{ formatDate(task.start_date) }}</td><td>{{ formatDate(task.end_date) }}</td><td>{{ formatDate(task.actual_start_date) }}</td><td>{{ formatDate(task.actual_end_date) }}</td><td>{{ task.estimated_duration_days ?? '—' }}</td><td>{{ task.actual_duration_days ?? '—' }}</td><td>{{ calendarDayDifference(task.end_date, task.actual_end_date) }}</td><td>{{ task.progress_percent }} %</td><td><span v-if="isOverdue(task, todayISO)" class="deadline-alert">Atrasada {{ overdueDays(task, todayISO) }} día(s)</span><span v-else-if="isFinishedLate(task)" class="deadline-late">Finalizó tarde</span><span v-else class="muted">Sin retraso detectado</span></td>
              </tr>
              <tr v-if="schedule.tasks.length === 0"><td colspan="11" class="muted">No hay actividades registradas.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="showMilestones" id="hitos" class="panel section-panel navigation-target">
        <MilestonesManager
          :project-id="schedule.project.id"
          :start-date="schedule.project.start_date"
          :end-date="schedule.project.end_date"
          :milestones="milestones"
          :tasks="schedule.tasks"
          @changed="loadSchedule"
        />
      </section>

      <section v-if="showKpis" id="kpi-hitos" class="panel section-panel">
        <div class="section-heading-row">
          <div>
            <h2>Indicadores asociados a hitos</h2>
            <p class="muted">Cada indicador pertenece a un hito. Su estado de cumplimiento lo calcula Django.</p>
          </div>
          <RouterLink :to="{ name: 'milestones' }" class="secondary-button">Administrar hitos</RouterLink>
        </div>
        <label class="form-label" for="milestone-kpi-select">Selecciona un hito</label>
        <select id="milestone-kpi-select" v-model="selectedKpiId" class="form-control kpi-selector">
          <option :value="null">Seleccionar hito...</option>
          <option v-for="milestone in milestones" :key="milestone.id" :value="milestone.id">
            {{ milestone.name }} — {{ formatDate(milestone.due_date) }}
          </option>
        </select>
        <p v-if="milestones.length === 0" class="muted">Este proyecto no tiene hitos. Crea uno desde Hitos.</p>
        <MilestoneKpisManager
          v-if="selectedKpi"
          :key="selectedKpi.id"
          :milestone-id="selectedKpi.id"
          :milestone-name="selectedKpi.name"
        />
      </section>

      <section v-if="isAll" class="panel section-panel">
        <h2>Dependencias registradas</h2>
        <div class="table-scroll">
          <table class="data-table">
            <thead><tr><th>Predecesora</th><th>Tipo</th><th>Desfase laboral</th><th>Sucesora</th></tr></thead>
            <tbody>
              <tr v-for="dependency in schedule.dependencies" :key="dependency.id">
                <td>#{{ dependency.predecessor_id }}</td><td>{{ dependency.dependency_type }}</td><td>{{ dependency.lag_days > 0 ? '+' : '' }}{{ dependency.lag_days }}</td><td>#{{ dependency.successor_id }}</td>
              </tr>
              <tr v-if="schedule.dependencies.length === 0"><td colspan="4" class="muted">No existen dependencias para este proyecto.</td></tr>
            </tbody>
          </table>
        </div>
        <p class="notice-note">Modificar una dependencia o un calendario no provoca una reprogramación automática. Las APIs protegidas rechazan cambios incompatibles; para desplazar tareas utiliza la opción de reprogramación.</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.scheduling-view { width: 100%; }
.navigation-target { scroll-margin-top: 20px; }
.kpi-selector { max-width: 560px; margin: 10px 0 20px; }
.kpi-navigation-note { margin-bottom: 16px; color: #9cbef3; font-size: 13px; }
.selector-panel { padding: 20px; margin-bottom: 20px; }
.selector-panel select { max-width: 530px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 20px 0; }
.stat-card { padding: 19px; display: flex; flex-direction: column; gap: 10px; }
.stat-card strong { font-size: 27px; }
.stat-alert { border: 1px solid #ae6255; }
.deadline-alert { color: #f6a38a; font-weight: 650; }
.deadline-late { color: #d1a2ea; }
.row-overdue { background: rgba(231,140,118,.06); }
.section-panel { padding: 22px; margin-bottom: 18px; }
.gantt-help { margin-top: 14px; }
.success-banner { margin: 0 0 20px; padding: 12px 14px; border: 1px solid #417e6b; border-radius: 9px; background: rgba(65,126,107,.12); }
.section-panel h2 { margin: 0 0 12px; font-size: 17px; }
.section-heading-row { display: flex; justify-content: space-between; align-items: center; gap: 15px; margin-bottom: 13px; }
.section-heading-row h2 { margin: 0 0 6px; }
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 13px 12px; border-bottom: 1px solid var(--color-border); text-align: left; white-space: nowrap; }
.data-table th { color: var(--color-muted); font-weight: 600; }
.muted { color: var(--color-muted); font-size: 12px; }
.warning-list { margin: 12px 0 0; padding-left: 20px; color: var(--color-warning); font-size: 12px; line-height: 1.8; }
.notice-ok { font-size: 12px; color: var(--color-success); }
.notice-note { margin-top: 18px; border-left: 3px solid var(--color-warning); padding: 10px 12px; background: #2b2c2c; color: #e6d3a8; font-size: 12px; line-height: 1.6; }
.error-banner { padding: 14px; border: 1px solid var(--color-danger); border-radius: 9px; margin-bottom: 20px; color: #ffb2a1; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 580px) { .summary-grid { grid-template-columns: 1fr; } .section-heading-row { align-items: flex-start; flex-direction: column; } }
</style>
