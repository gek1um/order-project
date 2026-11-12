<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { isAxiosError } from 'axios'
import { projectService, type Project } from '../services/projects'
import { schedulingService, type ProjectSchedule, type ScheduleTask } from '../services/scheduling'
import { milestoneService, type Milestone } from '../services/milestones'
import { milestoneKpiService, type MilestoneKpi } from '../services/milestoneKpis'
import { assignmentService, type ProjectCostSummary, type WeeklyAvailability } from '../services/resources'
import { isOverdue, isFinishedLate, localTodayISO, progressSummary } from '../utils/scheduleHealth'

const projects = ref<Project[]>([])
const projectId = ref<number | null>(null)
const schedule = ref<ProjectSchedule | null>(null)
const milestones = ref<Milestone[]>([])
const milestoneKpis = ref<MilestoneKpi[] | null>(null)
const kpiResponsible = ref('')
const kpiMilestone = ref('')
const kpiFrom = ref('')
const kpiTo = ref('')
const kpiFilterError = ref('')
const costs = ref<ProjectCostSummary | null>(null)
const availability = ref<WeeklyAvailability | null>(null)
const warnings = ref<string[]>([])
const error = ref('')
const loadingProjects = ref(false)
const loading = ref(false)
let sequence = 0
const today = localTodayISO()

const selectedProject = computed(() => projects.value.find(p => p.id === projectId.value) ?? null)
const tasks = computed(() => schedule.value?.tasks ?? [])
const activeTasks = computed(() => tasks.value.filter(t => t.status !== 'CANCELLED'))
const summary = computed(() => progressSummary(tasks.value, today))
const totalTasks = computed(() => tasks.value.length)
const completedTasks = computed(() => tasks.value.filter(t => t.status === 'COMPLETED').length)
const pendingTasks = computed(() => tasks.value.filter(t => t.status === 'PENDING').length)
const inProgressTasks = computed(() => tasks.value.filter(t => t.status === 'IN_PROGRESS').length)
const milestoneNameById = computed(() => new Map(milestones.value.map(m => [m.id, m.name])))
const kpiResponsibles = computed(() => Array.from(new Set(
  (milestoneKpis.value ?? []).map(k => k.responsible.trim()).filter(Boolean),
)).sort((a, b) => a.localeCompare(b, 'es')))
const filteredKpis = computed(() => (milestoneKpis.value ?? []).filter(k =>
  (!kpiResponsible.value || k.responsible === kpiResponsible.value) &&
  (!kpiMilestone.value || k.milestone === Number(kpiMilestone.value)) &&
  (!kpiFrom.value || (k.measured_at !== null && k.measured_at.slice(0, 10) >= kpiFrom.value)) &&
  (!kpiTo.value || (k.measured_at !== null && k.measured_at.slice(0, 10) <= kpiTo.value)),
))
const kpiMeasured = computed(() => filteredKpis.value.filter(k => k.achievement_status !== 'NOT_MEASURED').length)
const kpiMet = computed(() => filteredKpis.value.filter(k => k.achievement_status === 'MET').length)
const kpiNotMet = computed(() => filteredKpis.value.filter(k => k.achievement_status === 'NOT_MET').length)
const kpiNotMeasured = computed(() => filteredKpis.value.filter(k => k.achievement_status === 'NOT_MEASURED').length)
const kpiCompliance = computed(() => kpiMeasured.value ? Math.round(kpiMet.value / kpiMeasured.value * 100) : null)
function kpiActual(k: MilestoneKpi): string {
  if (k.actual_value === null) return 'Sin medición'
  const n = Number(k.actual_value)
  return `${Number.isFinite(n) ? new Intl.NumberFormat('es-CL', {maximumFractionDigits: 2}).format(n) : k.actual_value} ${k.unit}`.trim()
}
function kpiState(k: MilestoneKpi): string {
  return k.achievement_status === 'MET' ? 'Cumple' : k.achievement_status === 'NOT_MET' ? 'No cumple' : 'Sin medición'
}
function applyKpiDates(): void {
  kpiFilterError.value = kpiFrom.value && kpiTo.value && kpiFrom.value > kpiTo.value
    ? 'La fecha inicial no puede ser posterior a la final.' : ''
  if (kpiFilterError.value) kpiTo.value = ''
}
function clearKpiFilters(): void {
  kpiResponsible.value = ''; kpiMilestone.value = ''; kpiFrom.value = ''; kpiTo.value = ''; kpiFilterError.value = ''
}
const milestoneCompleted = computed(() => milestones.value.filter(m => m.status === 'COMPLETED').length)
const milestoneOverdue = computed(() => milestones.value.filter(m => m.status !== 'COMPLETED' && m.due_date < today).length)
const availabilityRows = computed(() => availability.value?.weeks.filter(w => w.overallocated) ?? [])
const topAlerts = computed(() => {
  const list: { level: 'danger' | 'warning'; title: string; detail: string; route: string }[] = []
  for (const task of activeTasks.value.filter(t => isOverdue(t, today)).slice(0, 5)) {
    list.push({ level: 'danger', title: `Actividad atrasada: ${task.name}`, detail: `Término planificado: ${formatDate(task.end_date)}`, route: '/scheduling' })
  }
  for (const milestone of milestones.value.filter(m => m.status !== 'COMPLETED' && m.due_date < today).slice(0, 4)) {
    list.push({ level: 'warning', title: `Hito vencido: ${milestone.name}`, detail: `Fecha comprometida: ${formatDate(milestone.due_date)}`, route: '/scheduling' })
  }
  for (const row of availabilityRows.value.slice(0, 4)) {
    list.push({ level: 'warning', title: `Sobreasignación: ${row.resource_name}`, detail: `Semana del ${formatDate(row.week_start)} · ${formatHours(row.overallocation_hours)} h adicionales`, route: '/resources' })
  }
  return list
})
const criticalTasks = computed(() => tasks.value.filter(t => isOverdue(t, today) || isFinishedLate(t)).slice(0, 8))
const costDiff = computed(() => costs.value ? number(costs.value.actual_minus_planned) : null)
const costRatio = computed(() => {
  if (!costs.value) return null
  const budget = number(costs.value.baseline_budget)
  return budget > 0 ? Math.round(number(costs.value.actual_resource_cost) / budget * 100) : null
})

function number(value: string | number | null | undefined): number {
  const result = Number(value ?? 0)
  return Number.isFinite(result) ? result : 0
}
function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(number(value))
}
function formatHours(value: string | number): string {
  return new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 }).format(number(value))
}
function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = value.slice(0, 10).split('-')
  return date.length === 3 ? `${date[2]}/${date[1]}/${date[0]}` : value
}
function errorText(e: unknown): string {
  if (!isAxiosError(e)) return e instanceof Error ? e.message : 'Error inesperado.'
  if (!e.response) return 'No se pudo conectar con Django.'
  const data: unknown = e.response.data
  if (data && typeof data === 'object') return Object.entries(data).map(([k, v]) => `${k}: ${String(v)}`).join(' | ')
  return `Error HTTP ${e.response.status}`
}
function statusName(status: ScheduleTask['status']): string {
  const names: Record<ScheduleTask['status'], string> = {
    PENDING: 'Pendiente', IN_PROGRESS: 'En progreso', COMPLETED: 'Completada', CANCELLED: 'Cancelada',
  }
  return names[status]
}
async function loadProjects(): Promise<void> {
  loadingProjects.value = true
  try {
    projects.value = await projectService.list()
    if (projectId.value === null && projects.value.length) projectId.value = projects.value[0]?.id ?? null
  } catch (e) { error.value = errorText(e) }
  finally { loadingProjects.value = false }
}
async function reload(): Promise<void> {
  const current = ++sequence
  const id = projectId.value
  schedule.value = null; milestones.value = []; milestoneKpis.value = null; costs.value = null; availability.value = null
  warnings.value = []; error.value = ''
  if (id === null) { loading.value = false; return }
  loading.value = true
  const requests = await Promise.allSettled([
    schedulingService.getProjectSchedule(id),
    milestoneService.list(id),
    assignmentService.projectCosts(id),
    assignmentService.availability(id),
    milestoneKpiService.listByProject(id),
  ] as const)
  if (current !== sequence) return
  if (requests[0].status === 'fulfilled') schedule.value = requests[0].value
  else error.value = `No se pudo consultar el cronograma: ${errorText(requests[0].reason)}`
  if (requests[1].status === 'fulfilled') milestones.value = requests[1].value
  else warnings.value.push(`Hitos no disponibles: ${errorText(requests[1].reason)}`)
  if (requests[2].status === 'fulfilled') costs.value = requests[2].value
  else warnings.value.push(`Costos no disponibles: ${errorText(requests[2].reason)}`)
  if (requests[3].status === 'fulfilled') availability.value = requests[3].value
  else warnings.value.push(`Disponibilidad no disponible: ${errorText(requests[3].reason)}`)
  if (requests[4].status === 'fulfilled') milestoneKpis.value = requests[4].value
  else warnings.value.push(`KPI de hitos no disponibles: ${errorText(requests[4].reason)}`)
  loading.value = false
}
watch(projectId, () => { clearKpiFilters(); void reload() })
onMounted(() => { void loadProjects() })
</script>

<template>
  <main class="dashboard-page">
    <header class="page-header dashboard-heading">
      <div>
        <h1 class="page-title">Seguimiento del proyecto</h1>
        <p class="page-description">Estado del cronograma, avance, hitos, costos y capacidad de recursos.</p>
      </div>
      <div class="toolbar">
        <label class="sr-only" for="followup-project">Proyecto</label>
        <select id="followup-project" v-model.number="projectId" :disabled="loadingProjects || !projects.length">
          <option :value="null" disabled>Seleccionar proyecto</option>
          <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.code }} · {{ project.name }}</option>
        </select>
        <button class="secondary-button" type="button" :disabled="loading || projectId === null" @click="reload">Actualizar</button>
      </div>
    </header>

    <p v-if="error" class="message message-error" role="alert">{{ error }}</p>
    <div v-if="loadingProjects || loading" class="panel empty">Cargando indicadores del proyecto…</div>
    <div v-else-if="!projects.length" class="panel empty">No hay proyectos registrados. <RouterLink to="/projects">Crear proyecto</RouterLink></div>
    <div v-else-if="!schedule" class="panel empty">No hay un cronograma disponible para este proyecto.</div>
    <template v-else>
      <div v-if="warnings.length" class="message message-warning" role="status">
        <p v-for="warning in warnings" :key="warning">{{ warning }}</p>
      </div>
      <section class="project-strip panel" aria-label="Resumen del proyecto">
        <div><span class="eyebrow">PROYECTO SELECCIONADO</span><h2>{{ selectedProject?.name ?? schedule.project.name }}</h2><p class="muted">{{ selectedProject?.code ?? '' }} · Responsable: {{ selectedProject?.manager_name ?? '—' }} · {{ formatDate(schedule.project.start_date) }} — {{ formatDate(schedule.project.end_date) }}</p></div>
        <RouterLink :to="{ name: 'project-detail', params: { id: projectId } }" class="secondary-button link-button">Ver proyecto</RouterLink>
      </section>

      <section class="stats-grid" aria-label="Indicadores principales">
        <article class="panel stat"><span class="muted">Avance promedio</span><strong>{{ summary.averageProgress }}%</strong><div class="progress-track"><div class="progress-fill" :style="{ width: `${summary.averageProgress}%` }"></div></div><small>Promedio simple · sin tareas canceladas</small></article>
        <article class="panel stat"><span class="muted">Actividades atrasadas</span><strong :class="{ danger: summary.overdue > 0 }">{{ summary.overdue }}</strong><small>Vencidas y no completadas</small></article>
        <article class="panel stat"><span class="muted">Hitos cumplidos</span><strong>{{ milestoneCompleted }}/{{ milestones.length }}</strong><small>{{ milestoneOverdue }} pendiente(s) vencido(s)</small></article>
        <article class="panel stat"><span class="muted">Semanas sobreasignadas</span><strong :class="{ warning: (availability?.overallocated_weeks ?? 0) > 0 }">{{ availability?.overallocated_weeks ?? '—' }}</strong><small>Estimación de carga laboral</small></article>
      </section>

      <section class="main-grid">
        <article class="panel section-panel">
          <div class="section-header"><div><h2>Estado de actividades</h2><p class="muted">{{ totalTasks }} actividades · {{ activeTasks.length }} no canceladas</p></div><RouterLink to="/scheduling">Abrir Carta Gantt</RouterLink></div>
          <div class="activity-row" v-for="item in [
            { label: 'Completadas', amount: completedTasks, color: '#5cc8a1' },
            { label: 'En progreso', amount: inProgressTasks, color: '#4f8cff' },
            { label: 'Pendientes', amount: pendingTasks, color: '#f4b860' },
          ]" :key="item.label">
            <div class="activity-label"><span>{{ item.label }}</span><strong>{{ item.amount }}</strong></div>
            <div class="progress-track"><div class="progress-fill" :style="{ width: `${totalTasks ? item.amount / totalTasks * 100 : 0}%`, background: item.color }"></div></div>
          </div>
          <div class="activity-footer"><span>Finalizadas después de plazo: <strong>{{ summary.finishedLate }}</strong></span><span>Finalizadas en plazo: <strong>{{ summary.finishedOnTime }}</strong></span></div>
        </article>
        <article class="panel section-panel">
          <div class="section-header"><div><h2>Control de costos</h2><p class="muted">Costos de asignaciones de recursos</p></div><RouterLink to="/resources">Ver recursos</RouterLink></div>
          <template v-if="costs">
            <div class="cost-grid">
              <div><span class="muted">Presupuesto base</span><strong>{{ formatMoney(costs.baseline_budget) }}</strong></div>
              <div><span class="muted">Costo planificado</span><strong>{{ formatMoney(costs.planned_resource_cost) }}</strong></div>
              <div><span class="muted">Costo real registrado</span><strong>{{ formatMoney(costs.actual_resource_cost) }}</strong></div>
              <div><span class="muted">Real menos planificado</span><strong :class="{ danger: (costDiff ?? 0) > 0 }">{{ formatMoney(costDiff) }}</strong></div>
            </div>
            <div class="activity-label"><span>Real / presupuesto base</span><strong>{{ costRatio === null ? 'Sin presupuesto' : `${costRatio}%` }}</strong></div>
            <div class="progress-track"><div class="progress-fill" :style="{ width: `${Math.min(100, Math.max(0, costRatio ?? 0))}%`, background: (costRatio ?? 0) > 100 ? '#e76f51' : '#4f8cff' }"></div></div>
            <p class="footnote">Se comparan costos de asignaciones; los costos registrados en solicitudes de cambio no se suman para evitar duplicaciones.</p>
          </template>
          <p v-else class="muted">Sin información de costos disponible.</p>
        </article>
      </section>

      <section class="panel kpi-section" aria-label="KPI asociados a hitos">
        <div class="section-header">
          <div><h2>KPI asociados a hitos</h2><p class="muted">Metas y mediciones registradas en Django, vinculadas a los hitos del proyecto.</p></div>
          <RouterLink to="/scheduling">Administrar KPI</RouterLink>
        </div>
        <p v-if="milestoneKpis === null" class="muted">Los KPI no están disponibles; revisa el aviso de carga.</p>
        <template v-else>
          <div class="kpi-filters">
            <label>Hito
              <select v-model="kpiMilestone"><option value="">Todos</option><option v-for="m in milestones" :key="m.id" :value="String(m.id)">{{ m.name }}</option></select>
            </label>
            <label>Responsable
              <select v-model="kpiResponsible"><option value="">Todos</option><option v-for="name in kpiResponsibles" :key="name" :value="name">{{ name }}</option></select>
            </label>
            <label>Medido desde <input v-model="kpiFrom" type="date" @change="applyKpiDates" /></label>
            <label>Medido hasta <input v-model="kpiTo" type="date" @change="applyKpiDates" /></label>
            <button type="button" class="secondary-button" @click="clearKpiFilters">Limpiar filtros</button>
          </div>
          <p v-if="kpiFilterError" class="message message-error" role="alert">{{ kpiFilterError }}</p>
          <p class="footnote">Los filtros de esta sección se aplican únicamente a los KPI. Las fechas corresponden a la medición y excluyen indicadores sin medir cuando se especifica un período.</p>
          <div class="kpi-stats">
            <div><small>Indicadores</small><strong>{{ filteredKpis.length }}</strong></div>
            <div><small>Cumplen meta</small><strong class="kpi-good">{{ kpiMet }}</strong></div>
            <div><small>No cumplen</small><strong class="danger">{{ kpiNotMet }}</strong></div>
            <div><small>Sin medición</small><strong>{{ kpiNotMeasured }}</strong></div>
            <div><small>Cumplimiento (medidos)</small><strong>{{ kpiCompliance === null ? 'Sin datos' : `${kpiCompliance}%` }}</strong></div>
          </div>
          <p v-if="!filteredKpis.length" class="muted">No hay KPI para los filtros seleccionados.</p>
          <div v-else class="kpi-table-scroll"><table class="kpi-table">
            <thead><tr><th>Indicador</th><th>Hito</th><th>Responsable</th><th>Meta</th><th>Resultado</th><th>Estado</th></tr></thead>
            <tbody><tr v-for="k in filteredKpis" :key="k.id">
              <td>{{ k.name }}</td><td>{{ milestoneNameById.get(k.milestone) ?? `Hito ${k.milestone}` }}</td><td>{{ k.responsible || '—' }}</td>
              <td>{{ k.target_value }} {{ k.unit }}</td><td>{{ kpiActual(k) }}</td>
              <td><span :class="['kpi-tag', k.achievement_status === 'MET' ? 'kpi-good' : k.achievement_status === 'NOT_MET' ? 'danger' : '']">{{ kpiState(k) }}</span></td>
            </tr></tbody>
          </table></div>
        </template>
      </section>

      <section class="main-grid">
        <article class="panel section-panel">
          <div class="section-header"><div><h2>Alertas del proyecto</h2><p class="muted">Actividades, hitos y disponibilidad</p></div></div>
          <p v-if="!topAlerts.length" class="muted">No se detectan alertas en los datos disponibles.</p>
          <RouterLink v-for="(alert, index) in topAlerts" :key="index" :to="alert.route" class="alert-row">
            <span class="alert-dot" :class="alert.level"></span>
            <div><strong>{{ alert.title }}</strong><small>{{ alert.detail }}</small></div><span class="arrow">↗</span>
          </RouterLink>
        </article>
        <article class="panel section-panel">
          <div class="section-header"><div><h2>Actividades con desviaciones</h2><p class="muted">Vencidas o finalizadas fuera de plazo</p></div><RouterLink to="/scheduling">Ver detalle</RouterLink></div>
          <p v-if="!criticalTasks.length" class="muted">No se detectaron desviaciones de plazo.</p>
          <div v-for="task in criticalTasks" :key="task.id" class="deviation-row">
            <div><strong>{{ task.name }}</strong><small>{{ statusName(task.status) }} · término previsto {{ formatDate(task.end_date) }}</small></div>
            <span class="tag" :class="isOverdue(task, today) ? 'danger-tag' : 'warning-tag'">{{ isOverdue(task, today) ? 'Atrasada' : 'Terminó tarde' }}</span>
          </div>
        </article>
      </section>
      <p class="footnote">Indicadores calculados al actualizar la página. El atraso usa la fecha local actual y días calendario. La capacidad semanal se estima a partir de las asignaciones y del calendario laboral.</p>
    </template>
  </main>
</template>

<style scoped>
.dashboard-page { padding: 30px 38px 42px; max-width: 1500px; margin: 0 auto; }
.dashboard-heading { align-items: flex-start; flex-wrap: wrap; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; }
select { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px; max-width: 330px; min-width: 210px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
.panel { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; }
.empty { padding: 42px; text-align: center; color: var(--color-muted); }
.message { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 12px; }
.message-error { background: #422c32; color: #ffb9b9; }
.message-warning { background: #433a29; color: #f7d39b; }
.message p { margin: 3px 0; }
.project-strip { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 20px; margin-bottom: 18px; }
.project-strip h2 { margin: 6px 0; font-size: 19px; }
.eyebrow { font-size: 10px; color: #80aafa; letter-spacing: 1px; font-weight: 700; }
.muted, .footnote, small { color: var(--color-muted); }
.muted { font-size: 12px; line-height: 1.6; }
.link-button { display: inline-flex; align-items: center; text-decoration: none; padding: 10px 14px; white-space: nowrap; }
.stats-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 16px; margin-bottom: 18px; }
.stat { padding: 20px; display: flex; flex-direction: column; gap: 9px; }
.stat > span { font-size: 12px; }
.stat strong { font-size: 28px; letter-spacing: -1px; }
.stat small { font-size: 10px; line-height: 1.5; }
.danger { color: var(--color-danger); }
.warning { color: var(--color-warning); }
.progress-track { background: #161d27; height: 9px; border-radius: 999px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--color-primary); border-radius: inherit; }
.main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; align-items: start; }
.section-panel { padding: 22px; min-height: 245px; }
.section-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
.section-header h2 { margin: 0 0 5px; font-size: 16px; }
.section-header p { margin: 0; }
.section-header a { font-size: 12px; color: #80b4ff; white-space: nowrap; }
.activity-row { margin-bottom: 16px; }
.activity-label { display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 12px; margin: 0 0 7px; }
.activity-footer { margin-top: 22px; display: flex; gap: 20px; flex-wrap: wrap; font-size: 11px; color: var(--color-muted); }
.activity-footer strong { color: #fff; }
.cost-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 24px; }
.cost-grid div { display: flex; flex-direction: column; gap: 7px; }
.cost-grid strong { font-size: 18px; }
.footnote { font-size: 11px; line-height: 1.7; }
.alert-row, .deviation-row { display: flex; align-items: center; padding: 12px 0; border-top: 1px solid var(--color-border); gap: 12px; }
.alert-row:hover { color: #9bbcfb; }
.alert-row > div, .deviation-row > div { flex: 1; min-width: 0; }
.alert-row strong, .deviation-row strong { display: block; font-size: 12px; line-height: 1.5; font-weight: 600; }
.alert-row small, .deviation-row small { display: block; margin-top: 3px; font-size: 11px; }
.alert-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.alert-dot.danger { background: var(--color-danger); }
.alert-dot.warning { background: var(--color-warning); }
.arrow { font-size: 17px; }
.tag { font-size: 10px; padding: 5px 8px; white-space: nowrap; border-radius: 999px; }
.danger-tag { background: #542f30; color: #f0aaa7; }
.warning-tag { background: #4c402b; color: #eac78c; }
@media (max-width: 1100px) { .stats-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 760px) { .dashboard-page { padding: 20px 16px; } .stats-grid, .main-grid { grid-template-columns: 1fr; } .project-strip { align-items: flex-start; flex-direction: column; } .cost-grid { grid-template-columns: 1fr; } }
.kpi-section { padding: 22px; margin-bottom: 18px; }
.kpi-filters { display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin:18px 0 10px; }
.kpi-filters label { display:grid; gap:6px; color:var(--color-muted); font-size:11px; min-width:140px; flex:1; }
.kpi-filters input, .kpi-filters select { color:inherit; background:#151d29; border:1px solid var(--color-border); border-radius:7px; padding:10px; width:100%; min-width:0; }
.kpi-filters button { min-height:38px; }
.kpi-stats { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin:18px 0; }
.kpi-stats > div { background:#151d29; padding:12px; border-radius:8px; display:grid; gap:6px; }
.kpi-stats small { font-size:10px; } .kpi-stats strong { font-size:21px; }
.kpi-good { color:#65d3ae; }
.kpi-table-scroll { overflow-x:auto; } .kpi-table { width:100%; min-width:680px; border-collapse:collapse; font-size:12px; }
.kpi-table th,.kpi-table td { padding:12px 10px; text-align:left; border-bottom:1px solid var(--color-border); }
.kpi-table th {color:var(--color-muted); font-weight:500; } .kpi-tag {font-size:11px;font-weight:600;}
@media(max-width:880px){.kpi-stats{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
