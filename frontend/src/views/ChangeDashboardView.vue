<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { RouterLink } from 'vue-router'
import { projectService, type Project } from '../services/projects'
import { changeService, type ChangeKpis, type ChangeRequest, type ChangeStatus, type ChangePriority } from '../services/changes'

type StatusMeta = { status: ChangeStatus; label: string; color: string }
const statuses: StatusMeta[] = [
  { status: 'OPEN', label: 'Abiertas', color: '#94a3b8' },
  { status: 'UNDER_REVIEW', label: 'En evaluación', color: '#60a5fa' },
  { status: 'APPROVED', label: 'Aprobadas', color: '#34d399' },
  { status: 'REJECTED', label: 'Rechazadas', color: '#f87171' },
  { status: 'IMPLEMENTING', label: 'En implementación', color: '#fbbf24' },
  { status: 'CLOSED', label: 'Cerradas', color: '#a78bfa' },
]
const priorityOptions: ChangePriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const priorityName: Record<ChangePriority, string> = {
  LOW: 'Baja', MEDIUM: 'Media', HIGH: 'Alta', CRITICAL: 'Crítica',
}
const projects = ref<Project[]>([])
const projectId = ref<number | null>(null)
const allRequests = ref<ChangeRequest[]>([])
const kpis = ref<ChangeKpis | null>(null)
const dateFrom = ref('')
const dateTo = ref('')
const appliedFrom = ref('')
const appliedTo = ref('')
const statusFilter = ref<ChangeStatus | ''>('')
const priorityFilter = ref<ChangePriority | ''>('')
const loadingProjects = ref(false)
const loading = ref(false)
const error = ref('')
const warning = ref('')
let requestSeq = 0

const selectedProject = computed(() => projects.value.find(p => p.id === projectId.value) ?? null)
// La misma cohorte de los KPI: filtros aplicados a requested_at.
const cohortRequests = computed(() => allRequests.value.filter(item =>
  (!appliedFrom.value || item.requested_at >= appliedFrom.value) &&
  (!appliedTo.value || item.requested_at <= appliedTo.value),
))
// Los KPI oficiales de Django toman toda la cohorte de fechas;
// estado/prioridad solo refinan las tablas y contadores exploratorios.
const requests = computed(() => cohortRequests.value.filter(item =>
  (!statusFilter.value || item.status === statusFilter.value) &&
  (!priorityFilter.value || item.priority === priorityFilter.value),
))
const cohortTotal = computed(() => cohortRequests.value.length)
const statusRows = computed(() => statuses.map(meta => ({ ...meta, count: requests.value.filter(r => r.status === meta.status).length })))
const largestCount = computed(() => Math.max(1, ...statusRows.value.map(r => r.count)))
const totalRequests = computed(() => requests.value.length)
const implementingRequests = computed(() => requests.value.filter(r => r.status === 'IMPLEMENTING'))
const pendingDecision = computed(() => requests.value.filter(r => r.status === 'OPEN' || r.status === 'UNDER_REVIEW'))
const approvedAwaiting = computed(() => requests.value.filter(r => r.status === 'APPROVED'))
const highPriorityPending = computed(() => pendingDecision.value.filter(r => r.priority === 'HIGH' || r.priority === 'CRITICAL'))
const applicationsCount = computed(() => requests.value.reduce((sum, r) => sum + (r.applications?.length ?? 0), 0))
const totalActualChangeCosts = computed(() => requests.value.reduce((sum, r) => {
  const value = r.actual_cost === null ? 0 : Number(r.actual_cost)
  return sum + (Number.isFinite(value) ? value : 0)
}, 0))
const withRecordedCost = computed(() => requests.value.filter(r => r.actual_cost !== null).length)
const recentRequests = computed(() => [...requests.value].sort((a, b) =>
  b.requested_at.localeCompare(a.requested_at) || b.id - a.id,
).slice(0, 8))
const timeline = computed(() => [...requests.value].filter(r => r.decided_at).sort((a, b) =>
  (b.decided_at ?? '').localeCompare(a.decided_at ?? ''),
).slice(0, 5))

function displayDate(value: string | null | undefined): string {
  if (!value) return '—'
  const parts = value.slice(0, 10).split('-')
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value
}
function metric(value: number | null | undefined, suffix: string): string {
  return value === null || value === undefined ? 'Sin datos' : `${new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(value)}${suffix}`
}
function money(value: number): string {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(value)
}
function errorText(e: unknown): string {
  if (!isAxiosError(e)) return e instanceof Error ? e.message : 'Error inesperado.'
  if (!e.response) return 'No se pudo conectar al backend.'
  const data: unknown = e.response.data
  if (data && typeof data === 'object') return Object.entries(data).map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(', ') : String(val)}`).join(' | ')
  return `Error HTTP ${e.response.status}`
}
function width(count: number): string { return `${count / largestCount.value * 100}%` }
function statusLabel(value: ChangeStatus): string { return statuses.find(s => s.status === value)?.label ?? value }

async function loadProjects(): Promise<void> {
  loadingProjects.value = true
  error.value = ''
  try {
    projects.value = await projectService.list()
    if (projectId.value === null && projects.value.length) projectId.value = projects.value[0]?.id ?? null
  } catch (e) { error.value = errorText(e) }
  finally { loadingProjects.value = false }
}
async function reload(): Promise<void> {
  const seq = ++requestSeq
  const id = projectId.value
  if (id === null) { allRequests.value = []; kpis.value = null; loading.value = false; return }
  error.value = ''; warning.value = ''; loading.value = true
  const [requestsResult, kpiResult] = await Promise.allSettled([
    changeService.list(id),
    changeService.kpis(id, appliedFrom.value || undefined, appliedTo.value || undefined),
  ] as const)
  if (seq !== requestSeq) return
  if (requestsResult.status === 'fulfilled') allRequests.value = requestsResult.value
  else { allRequests.value = []; error.value = `No se pudieron cargar las solicitudes: ${errorText(requestsResult.reason)}` }
  if (kpiResult.status === 'fulfilled') kpis.value = kpiResult.value
  else { kpis.value = null; warning.value = `Indicadores no disponibles: ${errorText(kpiResult.reason)}` }
  loading.value = false
}
function applyFilters(): void {
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
    error.value = 'La fecha desde no puede ser posterior a la fecha hasta.'
    return
  }
  appliedFrom.value = dateFrom.value
  appliedTo.value = dateTo.value
  void reload()
}
function clearFilters(): void {
  dateFrom.value = ''; dateTo.value = ''; appliedFrom.value = ''; appliedTo.value = ''; statusFilter.value = ''; priorityFilter.value = ''
  void reload()
}
watch(projectId, () => { void reload() })
onMounted(() => { void loadProjects() })
</script>

<template>
  <main class="dashboard-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">VISIÓN GENERAL</p>
        <h1>Dashboard de Gestión del Cambio</h1>
        <p class="subtitle">Decisiones, implementación, trazabilidad e indicadores por proyecto.</p>
      </div>
      <div class="toolbar">
        <label class="visually-hidden" for="change-project">Proyecto</label>
        <select id="change-project" v-model.number="projectId" :disabled="loadingProjects || !projects.length">
          <option :value="null" disabled>Selecciona un proyecto</option>
          <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.code }} · {{ project.name }}</option>
        </select>
        <button class="secondary-button" type="button" :disabled="loading || projectId === null" @click="reload">Actualizar</button>
      </div>
    </header>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="warning" class="message warning" role="status">{{ warning }}</p>

    <section class="panel filter-panel">
      <div><h2>Período de solicitudes</h2><p class="muted">Las fechas filtran por fecha original de solicitud, igual que los KPI de Django.</p></div>
      <div class="filter-controls">
        <label class="field">Estado
          <select v-model="statusFilter"><option value="">Todos</option><option v-for="s in statuses" :key="s.status" :value="s.status">{{ s.label }}</option></select>
        </label>
        <label class="field">Prioridad
          <select v-model="priorityFilter"><option value="">Todas</option><option v-for="p in priorityOptions" :key="p" :value="p">{{ priorityName[p] }}</option></select>
        </label>
        <label class="field">Desde <input v-model="dateFrom" type="date" /></label>
        <label class="field">Hasta <input v-model="dateTo" type="date" /></label>
        <button class="primary-button" type="button" :disabled="loading || projectId === null" @click="applyFilters">Aplicar</button>
        <button class="secondary-button" type="button" :disabled="loading || projectId === null" @click="clearFilters">Limpiar</button>
      </div>
    </section>

    <p class="footnote">Los KPI superiores consideran todas las solicitudes cuya fecha original está dentro del período, independientemente de los filtros Estado/Prioridad. Estos dos filtros refinan los listados y contadores exploratorios.</p>

    <p v-if="loadingProjects || loading" class="panel empty" role="status">Cargando indicadores del proyecto…</p>
    <p v-else-if="!projects.length" class="panel empty">No hay proyectos registrados. <RouterLink to="/projects">Ver proyectos</RouterLink></p>
    <template v-else-if="projectId !== null">
      <section class="panel project-strip">
        <div><span class="eyebrow">PROYECTO SELECCIONADO</span><h2>{{ selectedProject?.name ?? `Proyecto ${projectId}` }}</h2><p class="muted">{{ selectedProject?.code }} · {{ totalRequests }} solicitudes visibles de {{ cohortTotal }} en el período</p></div>
        <RouterLink to="/changes" class="secondary-button link-button">Administrar solicitudes</RouterLink>
      </section>

      <section class="kpi-grid" aria-label="Indicadores de gestión del cambio">
        <article class="panel metric"><span>Tasa de aprobación</span><strong class="positive">{{ metric(kpis?.kpis.approval_rate.value, '%') }}</strong><small>{{ kpis?.kpis.approval_rate.numerator ?? '—' }} aprobadas / {{ kpis?.kpis.approval_rate.denominator ?? '—' }} decididas</small></article>
        <article class="panel metric"><span>Tiempo promedio de decisión</span><strong class="blue">{{ metric(kpis?.kpis.average_decision_days.value, ' días') }}</strong><small>{{ kpis?.kpis.average_decision_days.observations ?? '—' }} decisiones con fechas válidas</small></article>
        <article class="panel metric"><span>Cierres dentro del plazo</span><strong class="violet">{{ metric(kpis?.kpis.on_time_closure_rate.value, '%') }}</strong><small>{{ kpis?.kpis.on_time_closure_rate.numerator ?? '—' }} a tiempo / {{ kpis?.kpis.on_time_closure_rate.denominator ?? '—' }} medibles</small></article>
      </section>

      <section class="mini-grid" aria-label="Contadores adicionales">
        <article class="panel mini"><span>Por decidir</span><strong>{{ pendingDecision.length }}</strong><small>{{ highPriorityPending.length }} de prioridad alta o crítica</small></article>
        <article class="panel mini"><span>Esperando implementación</span><strong>{{ approvedAwaiting.length }}</strong><small>Aprobadas, aún sin iniciar</small></article>
        <article class="panel mini"><span>En implementación</span><strong>{{ implementingRequests.length }}</strong><small>Solicitudes activas</small></article>
        <article class="panel mini"><span>Aplicaciones registradas</span><strong>{{ applicationsCount }}</strong><small>Eventos SCHEDULE y COST</small></article>
      </section>

      <div class="two-columns">
        <section class="panel">
          <div class="panel-heading"><h2>Solicitudes por estado</h2><span class="muted">{{ totalRequests }} en total</span></div>
          <div v-if="totalRequests === 0" class="empty-inline">Sin solicitudes para el período seleccionado.</div>
          <div v-else class="status-list">
            <div v-for="row in statusRows" :key="row.status" class="status-row">
              <div class="status-line"><span>{{ row.label }}</span><strong>{{ row.count }}</strong></div>
              <div class="bar-track"><div class="bar-fill" :style="{ width: width(row.count), background: row.color }"></div></div>
            </div>
          </div>
          <p class="hint">La distribución corresponde al estado actual de las solicitudes creadas durante el período.</p>
        </section>
        <section class="panel">
          <div class="panel-heading"><h2>Seguimiento y alertas</h2><RouterLink to="/changes" class="text-link">Gestionar</RouterLink></div>
          <div class="attention-row"><span class="dot orange"></span><div><strong>{{ highPriorityPending.length }} solicitudes prioritarias pendientes</strong><small>Abiertas o en evaluación, con prioridad alta/crítica</small></div></div>
          <div class="attention-row"><span class="dot yellow"></span><div><strong>{{ implementingRequests.length }} en implementación</strong><small>En ejecución, todavía sin cierre</small></div></div>
          <div class="attention-row"><span class="dot blue-dot"></span><div><strong>{{ approvedAwaiting.length }} aprobadas por iniciar</strong><small>Pendientes de comenzar la implementación</small></div></div>
          <div class="attention-row"><span class="dot green"></span><div><strong>{{ kpis?.counts.closed ?? '—' }} cerradas</strong><small>Incluye cierres a tiempo y fuera de plazo</small></div></div>
        </section>
      </div>

      <div class="two-columns">
        <section class="panel">
          <div class="panel-heading"><h2>Solicitudes recientes</h2><RouterLink to="/changes" class="text-link">Ver todas</RouterLink></div>
          <p v-if="!recentRequests.length" class="empty-inline">No hay solicitudes recientes.</p>
          <div v-else class="request-list">
            <div v-for="item in recentRequests" :key="item.id" class="request-line">
              <div class="request-title"><strong>{{ item.title }}</strong><small>{{ displayDate(item.requested_at) }} · {{ priorityName[item.priority] }}</small></div>
              <span class="status-pill" :style="{ borderColor: statuses.find(s => s.status === item.status)?.color }">{{ statusLabel(item.status) }}</span>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-heading"><h2>Decisiones recientes</h2><span class="muted">Fecha de decisión</span></div>
          <p v-if="!timeline.length" class="empty-inline">No hay decisiones registradas.</p>
          <div v-else class="request-list">
            <div v-for="item in timeline" :key="item.id" class="request-line">
              <div class="request-title"><strong>{{ item.title }}</strong><small>{{ displayDate(item.decided_at) }} · {{ item.decided_by || 'Sin actor registrado' }}</small></div>
              <span class="status-pill">{{ item.status === 'REJECTED' ? 'Rechazada' : 'Aprobada' }}</span>
            </div>
          </div>
        </section>
      </div>

      <section class="panel note">
        <h2>Costos de solicitudes de cambio</h2>
        <p><strong>{{ money(totalActualChangeCosts) }}</strong> de costos reales declarados en <strong>{{ withRecordedCost }}</strong> solicitudes del período.</p>
        <p class="muted">Este total es informativo y no se suma a los costos de recursos ni modifica el presupuesto base. No representa gasto contable verificado.</p>
      </section>
      <p class="footnote">Los KPI provienen de Django. Las distribuciones y contadores exploratorios respetan el estado y la prioridad seleccionados; los tres KPI oficiales solo aplican el filtro de fecha de solicitud. Las solicitudes abiertas no cuentan como rechazadas.</p>
    </template>
  </main>
</template>

<style scoped>
.dashboard-page { padding: 28px 38px 50px; max-width: 1600px; margin: 0 auto; display: grid; gap: 18px; color: #e5ebf4; }
.page-head,.toolbar,.filter-controls,.panel-heading,.project-strip,.status-line,.request-line { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
h1 { font-size: 26px; margin: 5px 0 6px; letter-spacing: -.6px; } h2 { font-size: 15px; margin: 0 0 7px; } p { margin: 0; } .subtitle,.muted,.hint,.footnote,.metric small,.mini small { color: #93a3b8; font-size: 12px; line-height: 1.55; }
.eyebrow { color: #729ad6; font-size: 10px; letter-spacing: 1.5px; font-weight: 700; }
.panel { background: #1c2532; border: 1px solid #344153; border-radius: 11px; padding: 20px; min-width: 0; } .filter-panel { display:flex; justify-content: space-between; align-items: end; gap: 20px; flex-wrap: wrap; } .field { display:grid; gap: 5px; color:#aab8ca; font-size:12px; } input,select { color:#e5ebf4; background:#151d29; border:1px solid #3d4b5f; border-radius:7px; padding:10px; font:inherit; } input:focus-visible,select:focus-visible,button:focus-visible,a:focus-visible {outline:2px solid #7baeff; outline-offset:2px;} button { cursor:pointer; } button:disabled { cursor: not-allowed; opacity:.6; } .primary-button,.secondary-button { display:inline-flex; align-items:center; justify-content:center; border-radius:7px; min-height:37px; padding:8px 13px; font-size:12px; text-decoration:none; } .primary-button {border:1px solid #4f8cff; background:#4f8cff; color:#0c1725; font-weight:700;} .secondary-button {border:1px solid #455a72; background:#273449; color:#dae5f5;} .link-button {white-space:nowrap;} .text-link {color:#86b7ff; font-size:12px;} .visually-hidden {position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0;}
.kpi-grid,.mini-grid {display:grid; gap:14px; grid-template-columns: repeat(3,minmax(0,1fr));} .mini-grid { grid-template-columns:repeat(4,minmax(0,1fr)); } .metric,.mini { display:flex; flex-direction:column; gap:9px; } .metric>span,.mini>span {color:#9faec2;font-size:12px;} .metric strong {font-size:27px;letter-spacing:-.6px;} .mini strong {font-size:24px;} .positive {color:#66d5ac;} .blue {color:#8db9ff;} .violet {color:#c4a7fb;} .two-columns {display:grid;gap:14px;grid-template-columns:1fr 1fr;} .status-list {display:grid;gap:14px;margin-top:20px;} .status-line {font-size:12px;margin-bottom:7px;} .bar-track {height:9px;background:#2b3645;border-radius:30px;overflow:hidden;} .bar-fill {height:100%;border-radius:30px;transition:width .2s ease;} .hint {margin-top:15px;} .attention-row {display:flex;gap:12px;padding:13px 0;border-bottom:1px solid #344153;} .attention-row:last-child {border:0;} .attention-row strong,.attention-row small,.request-title strong,.request-title small {display:block;} .attention-row strong {font-size:13px;} .attention-row small {margin-top:5px;color:#93a3b8;font-size:11px;} .dot {flex-shrink:0;width:9px;height:9px;border-radius:50%;margin-top:4px;} .orange {background:#f87171;} .yellow {background:#fbbf24;} .blue-dot {background:#60a5fa;} .green {background:#34d399;} .request-line {padding:12px 0;border-bottom:1px solid #344153;} .request-line:last-child {border:0;} .request-title {min-width:0;} .request-title strong {font-size:12px;overflow-wrap:anywhere;} .request-title small {margin-top:5px;color:#94a3b8;font-size:11px;} .status-pill {font-size:10px;border:1px solid #586b84;color:#ccd7e5;border-radius:20px;padding:5px 8px;white-space:nowrap;} .empty,.empty-inline {padding:22px;text-align:center;color:#93a3b8;} .message {border-radius:8px;padding:12px;font-size:12px;} .error {color:#fbb8b8;border:1px solid #8d4f59;background:#472c36;} .warning {color:#ffe1a4;border:1px solid #795b37;background:#3b3225;} .project-strip h2 {margin:5px 0;} .note p + p {margin-top:8px;} .footnote {padding-bottom:5px;}
@media (max-width:1100px) { .mini-grid {grid-template-columns:repeat(2,minmax(0,1fr));} .two-columns {grid-template-columns:1fr;} }
@media (max-width:750px) { .dashboard-page {padding:18px;gap:12px;} .page-head,.toolbar,.filter-controls {align-items:stretch;flex-direction:column;} .kpi-grid {grid-template-columns:1fr;} .mini-grid {grid-template-columns:repeat(2,minmax(0,1fr));} .project-strip {align-items:start;flex-direction:column;} }
</style>
