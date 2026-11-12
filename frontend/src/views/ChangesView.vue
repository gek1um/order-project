<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { projectService, type Project } from '../services/projects'
import { taskService, type Task } from '../services/tasks'
import {
  changeService, type ChangeRequest, type ChangePayload, type ChangeKind,
  type ChangePriority, type ChangeStatus, type ChangeKpis,
  type ChangeScheduleResult, type SchedulePayload,
} from '../services/changes'

const auth = useAuthStore()
type Section = 'requests' | 'kpis'
type Operation = 'submit' | 'approve' | 'reject' | 'start' | 'schedule' | 'cost' | 'close'
const projects = ref<Project[]>([])
const projectId = ref<number | null>(null)
const requests = ref<ChangeRequest[]>([])
const tasks = ref<Task[]>([])
const selectedId = ref<number | null>(null)
const section = ref<Section>('requests')
const filterStatus = ref<'ALL' | ChangeStatus>('ALL')
const kpis = ref<ChangeKpis | null>(null)
const dateFrom = ref('')
const dateTo = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const formError = ref('')
const showForm = ref(false)
const editingId = ref<number | null>(null)
const operation = ref<Operation | null>(null)
const actor = ref('')
const reason = ref('')
const committedDate = ref('')
const closeDate = ref('')
const resultText = ref('')
const costValue = ref('')
const costDetail = ref('')
const plan = ref<SchedulePayload>({ actor: '', task_id: 0, start_date: '', duration_days: 1, detail: '' })
const preview = ref<ChangeScheduleResult | null>(null)
const previewFingerprint = ref('')
let loadSequence = 0

const kindOptions: { value: ChangeKind; label: string }[] = [
  { value: 'SCOPE', label: 'Alcance' }, { value: 'TIME', label: 'Tiempo' },
  { value: 'COST', label: 'Costo' }, { value: 'RESOURCE', label: 'Recursos' },
  { value: 'TECHNOLOGY', label: 'Tecnología' }, { value: 'ORGANIZATION', label: 'Organización' },
]
const priorities: { value: ChangePriority; label: string }[] = [
  { value: 'LOW', label: 'Baja' }, { value: 'MEDIUM', label: 'Media' },
  { value: 'HIGH', label: 'Alta' }, { value: 'CRITICAL', label: 'Crítica' },
]
const statusNames: Record<ChangeStatus, string> = {
  OPEN: 'Abierta', UNDER_REVIEW: 'En evaluación', APPROVED: 'Aprobada',
  REJECTED: 'Rechazada', IMPLEMENTING: 'En implementación', CLOSED: 'Cerrada',
}
const isoToday = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function newForm(): ChangePayload {
  return {
    project: projectId.value ?? 0, title: '', requester: '', requested_at: isoToday(),
    description: '', justification: '', kind: 'SCOPE', priority: 'MEDIUM',
    risk: '', impact_scope: '', impact_resources: '', estimated_delay_days: 0,
    estimated_cost: '0', responsible: '', committed_date: null,
  }
}
const form = ref<ChangePayload>(newForm())
const selected = computed(() => requests.value.find(r => r.id === selectedId.value) ?? null)
const filtered = computed(() => requests.value.filter(r => filterStatus.value === 'ALL' || r.status === filterStatus.value))
const projectTasks = computed(() => tasks.value.filter(t => t.project === projectId.value))
const fingerprint = computed(() => JSON.stringify({ ...plan.value, change: selectedId.value }))
const money = (value: string | number | null) => value === null ? '—' : '$' + new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(Number(value))
const humanDate = (value: string | null | undefined) => {
  if (!value) return '—'
  const part = value.slice(0, 10).split('-')
  return part.length === 3 ? `${part[2]}/${part[1]}/${part[0]}` : value
}
const metric = (value: number | null | undefined, suffix: string) => value === null || value === undefined ? 'Sin datos' : `${new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(value)}${suffix}`
function errorMessage(err: unknown): string {
  if (!isAxiosError(err)) return err instanceof Error ? err.message : 'Error inesperado.'
  if (!err.response) return 'No se pudo conectar con el backend.'
  const data: unknown = err.response.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([field, value]) => {
      const str = Array.isArray(value) ? value.map(String).join(', ') : typeof value === 'object' ? JSON.stringify(value) : String(value)
      return field === 'detail' ? str : `${field}: ${str}`
    }).join(' | ')
  }
  return `HTTP ${err.response.status}`
}
async function loadProjects() {
  try {
    projects.value = await projectService.list()
    if (projects.value.length && projectId.value === null) projectId.value = projects.value[0]?.id ?? null
  } catch (e) { error.value = errorMessage(e) }
}
async function reload() {
  const seq = ++loadSequence
  const id = projectId.value
  error.value = ''
  if (!id) { requests.value = []; tasks.value = []; kpis.value = null; return }
  loading.value = true
  try {
    const [items, taskItems, metrics] = await Promise.all([
      changeService.list(id), taskService.list({ project: id }),
      changeService.kpis(id, dateFrom.value || undefined, dateTo.value || undefined),
    ])
    if (seq !== loadSequence) return
    requests.value = items
    tasks.value = taskItems
    kpis.value = metrics
    if (!items.some(item => item.id === selectedId.value)) selectedId.value = items[0]?.id ?? null
  } catch (e) { if (seq === loadSequence) error.value = errorMessage(e) }
  finally { if (seq === loadSequence) loading.value = false }
}
watch(projectId, () => {
  selectedId.value = null; showForm.value = false; operation.value = null
  filterStatus.value = 'ALL'; dateFrom.value = ''; dateTo.value = ''; notice.value = ''
  void reload()
})
watch(selectedId, () => { operation.value = null; preview.value = null; formError.value = '' })
watch(fingerprint, () => { preview.value = null })
onMounted(() => { void loadProjects() })

function create() { editingId.value = null; form.value = newForm(); showForm.value = true; formError.value = '' }
function edit(item: ChangeRequest) {
  if (item.status !== 'OPEN') return
  editingId.value = item.id
  form.value = {
    project: item.project, title: item.title, requester: item.requester,
    requested_at: item.requested_at, description: item.description,
    justification: item.justification, kind: item.kind, priority: item.priority,
    risk: item.risk, impact_scope: item.impact_scope, impact_resources: item.impact_resources,
    estimated_delay_days: item.estimated_delay_days, estimated_cost: item.estimated_cost,
    responsible: item.responsible, committed_date: item.committed_date,
  }
  showForm.value = true; formError.value = ''
}
async function save() {
  if (busy.value) return
  const f = form.value
  if (!f.title.trim() || !f.requester.trim() || !f.requested_at || !f.description.trim() || !f.justification.trim()) {
    formError.value = 'Completa título, solicitante, fecha, descripción y justificación.'; return
  }
  if (!Number.isInteger(Number(f.estimated_delay_days)) || !Number.isFinite(Number(f.estimated_cost)) || Number(f.estimated_cost) < 0) {
    formError.value = 'Revisa el impacto en días y el costo estimado.'; return
  }
  busy.value = true; formError.value = ''; notice.value = ''
  try {
    const payload = { ...f, project: projectId.value ?? 0, committed_date: f.committed_date || null }
    const item = editingId.value ? await changeService.update(editingId.value, payload) : await changeService.create(payload)
    showForm.value = false
    await reload(); selectedId.value = item.id
    notice.value = editingId.value ? 'Solicitud actualizada.' : 'Solicitud registrada.'
  } catch (e) { formError.value = errorMessage(e) }
  finally { busy.value = false }
}
function startOperation(op: Operation) {
  if ((op === 'approve' || op === 'reject') && !auth.isAdmin) return
  operation.value = op; formError.value = ''; reason.value = ''; committedDate.value = selected.value?.committed_date ?? ''
  closeDate.value = isoToday(); resultText.value = ''; costValue.value = selected.value?.actual_cost ?? '0'
  costDetail.value = ''; preview.value = null; actor.value = selected.value?.responsible || selected.value?.requester || ''
  plan.value = {
    actor: actor.value, task_id: projectTasks.value[0]?.id ?? 0,
    start_date: projectTasks.value[0]?.start_date ?? '',
    duration_days: projectTasks.value[0]?.estimated_duration_days ?? 1, detail: '',
  }
}
function onTaskSelected() {
  const t = projectTasks.value.find(item => item.id === plan.value.task_id)
  if (t) { plan.value.start_date = t.start_date; plan.value.duration_days = t.estimated_duration_days ?? 1 }
}
async function runAction() {
  const item = selected.value
  const op = operation.value
  if (!item || !op || busy.value) return
  if ((op === 'approve' || op === 'reject') && !auth.isAdmin) {
    formError.value = 'Solo ADMIN puede aprobar o rechazar solicitudes.'
    return
  }
  if (!actor.value.trim()) { formError.value = 'Ingresa el nombre de quien realiza la acción.'; return }
  if ((op === 'approve' || op === 'reject') && !reason.value.trim()) { formError.value = 'La decisión requiere una justificación.'; return }
  if (op === 'close' && (!closeDate.value || !resultText.value.trim())) { formError.value = 'Completa fecha y resultado del cierre.'; return }
  if (op === 'cost' && (!costValue.value.trim() || !Number.isFinite(Number(costValue.value)) || Number(costValue.value) < 0)) { formError.value = 'Ingresa un costo real válido.'; return }
  if (op === 'schedule' && (!plan.value.task_id || !plan.value.start_date || !Number.isInteger(Number(plan.value.duration_days)) || Number(plan.value.duration_days) < 1)) { formError.value = 'Completa actividad, fecha y duración.'; return }
  if (op === 'schedule' && (!preview.value || previewFingerprint.value !== fingerprint.value)) { formError.value = 'Primero simula los parámetros actuales.'; return }
  if (op === 'schedule' && !window.confirm('¿Confirmar la reprogramación de todas las actividades indicadas en la simulación?')) return
  busy.value = true; formError.value = ''; notice.value = ''
  try {
    if (op === 'submit') await changeService.submit(item.id, actor.value.trim())
    else if (op === 'approve' || op === 'reject') await changeService.decide(item.id, op, actor.value.trim(), reason.value.trim())
    else if (op === 'start') await changeService.start(item.id, actor.value.trim(), committedDate.value)
    else if (op === 'cost') await changeService.recordCost(item.id, actor.value.trim(), costValue.value, costDetail.value)
    else if (op === 'close') await changeService.close(item.id, actor.value.trim(), closeDate.value, resultText.value.trim())
    else if (op === 'schedule') await changeService.apply(item.id, { ...plan.value, actor: actor.value.trim() })
    operation.value = null; preview.value = null
    await reload()
    notice.value = 'Operación registrada correctamente. Historial y métricas actualizados.'
  } catch (e) { formError.value = errorMessage(e) }
  finally { busy.value = false }
}
async function simulate() {
  if (busy.value || !selected.value) return
  if (!actor.value.trim() || !plan.value.task_id || !plan.value.start_date || !Number.isInteger(Number(plan.value.duration_days)) || Number(plan.value.duration_days) < 1) {
    formError.value = 'Completa actor, actividad, fecha y duración válida.'; return
  }
  busy.value = true; formError.value = ''; preview.value = null
  try {
    preview.value = await changeService.preview(selected.value.id, { ...plan.value, actor: actor.value.trim() })
    previewFingerprint.value = fingerprint.value
  } catch (e) { formError.value = errorMessage(e) }
  finally { busy.value = false }
}
async function refreshKpis() {
  if (!projectId.value) return
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) { error.value = 'La fecha desde no puede superar a la fecha hasta.'; return }
  error.value = ''; loading.value = true
  try { kpis.value = await changeService.kpis(projectId.value, dateFrom.value || undefined, dateTo.value || undefined) }
  catch (e) { error.value = errorMessage(e) }
  finally { loading.value = false }
}
</script>

<template>
  <main class="changes-page">
    <div class="heading">
      <div><p class="eyebrow">CONTROL DE PROYECTOS</p><h1>Gestión de cambios</h1><p class="subtitle">Solicitudes, decisiones, implementación y trazabilidad.</p></div>
      <button class="btn secondary" type="button" :disabled="loading || !projectId" @click="reload">Actualizar</button>
    </div>
    <div v-if="error" class="message error" role="alert">{{ error }}</div>
    <div v-if="notice" class="message ok" role="status">{{ notice }}</div>
    <section class="surface control-row">
      <label class="field grow"><span>Proyecto</span><select v-model.number="projectId"><option :value="null" disabled>Selecciona un proyecto</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.code }} — {{ p.name }}</option></select></label>
      <RouterLink v-if="projectId" :to="`/projects/${projectId}`" class="plain-link">Ir al proyecto</RouterLink>
      <div class="tabs"><button type="button" :class="{ active: section === 'requests' }" @click="section = 'requests'">Solicitudes</button><button type="button" :class="{ active: section === 'kpis' }" @click="section = 'kpis'">Indicadores</button></div>
    </section>
    <template v-if="projectId">
      <section v-if="section === 'kpis'" class="surface">
        <div class="section-header"><div><h2>Indicadores de gestión del cambio</h2><p class="muted">El período filtra por la fecha original de la solicitud.</p></div></div>
        <div class="filter-row"><label class="field"><span>Desde</span><input v-model="dateFrom" type="date" /></label><label class="field"><span>Hasta</span><input v-model="dateTo" type="date" /></label><button class="btn" type="button" :disabled="loading" @click="refreshKpis">Aplicar filtros</button><button class="btn secondary" type="button" @click="dateFrom = ''; dateTo = ''; refreshKpis()">Limpiar</button></div>
        <div v-if="kpis" class="metric-grid">
          <div class="metric"><small>Tasa de aprobación</small><strong>{{ metric(kpis.kpis.approval_rate.value, '%') }}</strong><span>{{ kpis.kpis.approval_rate.numerator }} aprobadas / {{ kpis.kpis.approval_rate.denominator }} decididas</span></div>
          <div class="metric"><small>Tiempo promedio de decisión</small><strong>{{ metric(kpis.kpis.average_decision_days.value, ' días') }}</strong><span>{{ kpis.kpis.average_decision_days.observations }} observaciones válidas</span></div>
          <div class="metric"><small>Cierres dentro de plazo</small><strong>{{ metric(kpis.kpis.on_time_closure_rate.value, '%') }}</strong><span>{{ kpis.kpis.on_time_closure_rate.numerator }} / {{ kpis.kpis.on_time_closure_rate.denominator }} cierres medibles</span></div>
        </div>
        <div v-if="kpis" class="muted footnote">Solicitudes: {{ kpis.counts.total }} · Decididas: {{ kpis.counts.decided }} · Rechazadas: {{ kpis.counts.rejected }} · Cerradas: {{ kpis.counts.closed }} · Excluidas de tiempo promedio: {{ kpis.kpis.average_decision_days.excluded_missing_or_invalid_date ?? 0 }} · Cierres sin fechas completas: {{ kpis.kpis.on_time_closure_rate.excluded_without_dates ?? 0 }}</div>
      </section>
      <template v-else>
        <section class="surface">
          <div class="section-header"><div><h2>Solicitudes de cambio</h2><p class="muted">{{ filtered.length }} solicitudes visibles</p></div><div class="header-actions"><select v-model="filterStatus" aria-label="Filtrar por estado"><option value="ALL">Todos los estados</option><option v-for="(label, key) in statusNames" :key="key" :value="key">{{ label }}</option></select><button class="btn" type="button" @click="create">+ Nueva solicitud</button></div></div>
          <div v-if="loading" class="empty">Cargando solicitudes…</div>
          <div v-else-if="!filtered.length" class="empty">No hay solicitudes para este filtro.</div>
          <div v-else class="table-wrap"><table class="data-table"><thead><tr><th>ID</th><th>Solicitud</th><th>Tipo</th><th>Prioridad</th><th>Estado</th><th>Solicitada</th><th>Acción</th></tr></thead><tbody><tr v-for="item in filtered" :key="item.id" :class="{ chosen: selectedId === item.id }"><td>#{{ item.id }}</td><td><strong>{{ item.title }}</strong><small>{{ item.requester }}</small></td><td>{{ kindOptions.find(x => x.value === item.kind)?.label }}</td><td>{{ priorities.find(x => x.value === item.priority)?.label }}</td><td><span class="pill" :class="item.status.toLowerCase()">{{ statusNames[item.status] }}</span></td><td>{{ humanDate(item.requested_at) }}</td><td><button class="link-btn" type="button" @click="selectedId = item.id">Ver detalle</button></td></tr></tbody></table></div>
        </section>
        <section v-if="selected" class="surface detail">
          <div class="section-header"><div><p class="eyebrow">SOLICITUD #{{ selected.id }}</p><h2>{{ selected.title }}</h2><span class="pill" :class="selected.status.toLowerCase()">{{ statusNames[selected.status] }}</span></div><button v-if="selected.status === 'OPEN'" class="btn secondary" @click="edit(selected)">Editar solicitud</button></div>
          <div class="info-grid"><div><small>Solicitante</small><b>{{ selected.requester }}</b></div><div><small>Responsable</small><b>{{ selected.responsible || 'Sin asignar' }}</b></div><div><small>Fecha solicitud</small><b>{{ humanDate(selected.requested_at) }}</b></div><div><small>Impacto plazo</small><b>{{ selected.estimated_delay_days }} días</b></div><div><small>Costo estimado</small><b>{{ money(selected.estimated_cost) }}</b></div><div><small>Costo real de cambio</small><b>{{ money(selected.actual_cost) }}</b></div><div><small>Fecha comprometida</small><b>{{ humanDate(selected.committed_date) }}</b></div><div><small>Cierre real</small><b>{{ humanDate(selected.actual_completion_date) }}</b></div></div>
          <div class="description-grid"><div><h3>Descripción</h3><p>{{ selected.description }}</p></div><div><h3>Justificación</h3><p>{{ selected.justification }}</p></div><div><h3>Riesgos</h3><p>{{ selected.risk || 'No informados' }}</p></div><div><h3>Impacto en alcance / recursos</h3><p>{{ selected.impact_scope || '—' }} / {{ selected.impact_resources || '—' }}</p></div></div>
          <div v-if="selected.decision_reason || selected.result" class="description-grid"><div v-if="selected.decision_reason"><h3>Decisión</h3><p>{{ selected.decided_by }} · {{ humanDate(selected.decided_at) }}</p><p>{{ selected.decision_reason }}</p></div><div v-if="selected.result"><h3>Resultado final</h3><p>{{ selected.result }}</p></div></div>
          <div class="actions"><button v-if="selected.status === 'OPEN'" class="btn" @click="startOperation('submit')">Enviar a evaluación</button><template v-if="selected.status === 'UNDER_REVIEW' && auth.isAdmin"><button class="btn" @click="startOperation('approve')">Aprobar</button><button class="btn danger" @click="startOperation('reject')">Rechazar</button></template><button v-if="selected.status === 'APPROVED'" class="btn" @click="startOperation('start')">Iniciar implementación</button><template v-if="selected.status === 'IMPLEMENTING'"><button class="btn" @click="startOperation('schedule')">Reprogramar actividades</button><button class="btn secondary" @click="startOperation('cost')">Registrar costo real</button><button class="btn secondary" @click="startOperation('close')">Cerrar solicitud</button></template></div>
          <div v-if="operation" class="operation-panel"><div class="section-header"><h3>{{ { submit: 'Enviar a evaluación', approve: 'Aprobar solicitud', reject: 'Rechazar solicitud', start: 'Iniciar implementación', schedule: 'Reprogramación controlada', cost: 'Registrar costo real', close: 'Cerrar solicitud' }[operation] }}</h3><button class="btn secondary" @click="operation = null">Cancelar</button></div>
            <div v-if="formError" class="message error" role="alert">{{ formError }}</div>
            <label class="field"><span>Actor responsable de la acción *</span><input v-model="actor" type="text" maxlength="150" /></label>
            <label v-if="operation === 'approve' || operation === 'reject'" class="field"><span>Motivo de la decisión *</span><textarea v-model="reason" rows="2" /></label>
            <label v-if="operation === 'start'" class="field"><span>Fecha comprometida (opcional)</span><input v-model="committedDate" type="date" /></label>
            <template v-if="operation === 'schedule'"><p class="muted">Simular no escribe en PostgreSQL. La confirmación aplicará todas las actividades afectadas.</p><div class="form-grid"><label class="field"><span>Actividad</span><select v-model.number="plan.task_id" @change="onTaskSelected"><option v-for="task in projectTasks" :key="task.id" :value="task.id">{{ task.name }}</option></select></label><label class="field"><span>Nuevo inicio</span><input v-model="plan.start_date" type="date" /></label><label class="field"><span>Duración laboral (días)</span><input v-model.number="plan.duration_days" type="number" min="1" step="1" /></label><label class="field"><span>Nota de ejecución (opcional)</span><input v-model="plan.detail" type="text" /></label></div><button class="btn secondary" type="button" :disabled="busy || !projectTasks.length" @click="simulate">Simular cambios</button>
              <div v-if="preview" class="preview"><h3>Vista previa — {{ preview.changes.length }} actividades afectadas</h3><div v-if="!preview.changes.length" class="muted">No se detectaron modificaciones.</div><div v-else class="table-wrap"><table class="data-table"><thead><tr><th>Actividad</th><th>Inicio anterior</th><th>Inicio nuevo</th><th>Término anterior</th><th>Término nuevo</th></tr></thead><tbody><tr v-for="row in preview.changes" :key="row.task_id"><td>{{ row.name }}</td><td>{{ humanDate(row.old_start_date) }}</td><td>{{ humanDate(row.new_start_date) }}</td><td>{{ humanDate(row.old_end_date) }}</td><td>{{ humanDate(row.new_end_date) }}</td></tr></tbody></table></div></div>
            </template>
            <template v-if="operation === 'cost'"><label class="field"><span>Costo real de esta solicitud (CLP) *</span><input v-model="costValue" type="number" min="0" step="0.01" /></label><label class="field"><span>Detalle</span><textarea v-model="costDetail" rows="2" /></label><p class="muted">Este costo no altera el presupuesto base ni el costo de asignaciones.</p></template>
            <template v-if="operation === 'close'"><label class="field"><span>Fecha real de cumplimiento *</span><input v-model="closeDate" type="date" /></label><label class="field"><span>Resultado del cambio *</span><textarea v-model="resultText" rows="3" /></label><p class="muted">Para cerrar debe existir al menos una aplicación registrada de programación o costo.</p></template>
            <button class="btn" type="button" :disabled="busy || (operation === 'schedule' && (!preview || !preview.changes.length || previewFingerprint !== fingerprint))" @click="runAction">{{ busy ? 'Procesando…' : operation === 'schedule' ? 'Confirmar reprogramación' : 'Confirmar acción' }}</button>
          </div>
          <div class="audit-grid"><div><h3>Bitácora de eventos ({{ selected.events.length }})</h3><div v-if="!selected.events.length" class="muted">Sin eventos.</div><div v-for="event in selected.events" :key="event.id" class="audit-item"><strong>{{ event.action }}</strong><small>{{ event.actor }} · {{ new Date(event.created_at).toLocaleString('es-CL') }}</small><p>{{ event.from_status ? (statusNames[event.from_status as ChangeStatus] ?? event.from_status) : 'Inicio' }} → {{ statusNames[event.to_status] ?? event.to_status }}</p><p v-if="event.detail">{{ event.detail }}</p></div></div><div><h3>Aplicaciones reales ({{ selected.applications.length }})</h3><div v-if="!selected.applications.length" class="muted">Aún no hay ejecuciones.</div><div v-for="application in selected.applications" :key="application.id" class="audit-item"><strong>{{ application.kind === 'SCHEDULE' ? 'Reprogramación' : 'Costo real' }} {{ application.task ? `· Tarea #${application.task}` : '' }}</strong><small>{{ application.actor }} · {{ new Date(application.created_at).toLocaleString('es-CL') }}</small><p v-if="application.detail">{{ application.detail }}</p><details><summary>Ver antes y después</summary><pre>{{ JSON.stringify({ antes: application.before, despues: application.after }, null, 2) }}</pre></details></div></div></div>
        </section>
      </template>
    </template>
    <div v-else class="surface empty">Selecciona un proyecto para consultar sus cambios.</div>
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false"><div class="modal" role="dialog" aria-modal="true" aria-label="Formulario de solicitud de cambio"><div class="section-header"><h2>{{ editingId ? 'Editar solicitud' : 'Nueva solicitud de cambio' }}</h2><button class="btn secondary" @click="showForm = false">Cerrar</button></div><div v-if="formError" class="message error" role="alert">{{ formError }}</div><form @submit.prevent="save"><div class="form-grid"><label class="field wide"><span>Título *</span><input v-model="form.title" maxlength="200" required /></label><label class="field"><span>Solicitante *</span><input v-model="form.requester" maxlength="150" required /></label><label class="field"><span>Fecha solicitud *</span><input v-model="form.requested_at" type="date" required /></label><label class="field"><span>Tipo</span><select v-model="form.kind"><option v-for="type in kindOptions" :key="type.value" :value="type.value">{{ type.label }}</option></select></label><label class="field"><span>Prioridad</span><select v-model="form.priority"><option v-for="p in priorities" :key="p.value" :value="p.value">{{ p.label }}</option></select></label><label class="field wide"><span>Descripción *</span><textarea v-model="form.description" rows="2" required /></label><label class="field wide"><span>Justificación *</span><textarea v-model="form.justification" rows="2" required /></label><label class="field wide"><span>Riesgos</span><textarea v-model="form.risk" rows="2" /></label><label class="field wide"><span>Impacto en alcance</span><textarea v-model="form.impact_scope" rows="2" /></label><label class="field wide"><span>Impacto en recursos</span><textarea v-model="form.impact_resources" rows="2" /></label><label class="field"><span>Retraso estimado (días calendario)</span><input v-model.number="form.estimated_delay_days" type="number" step="1" /></label><label class="field"><span>Costo estimado (CLP)</span><input v-model="form.estimated_cost" type="number" min="0" step="0.01" /></label><label class="field"><span>Responsable</span><input v-model="form.responsible" maxlength="150" /></label><label class="field"><span>Fecha comprometida (opcional)</span><input :value="form.committed_date ?? ''" type="date" @input="form.committed_date = ($event.target as HTMLInputElement).value || null" /></label></div><div class="actions"><button class="btn secondary" type="button" @click="showForm = false">Cancelar</button><button class="btn" type="submit" :disabled="busy">{{ busy ? 'Guardando…' : 'Guardar solicitud' }}</button></div></form></div></div>
  </main>
</template>

<style scoped>
.changes-page{padding:30px 36px 55px;display:grid;gap:18px;color:#e5eaf1;max-width:1550px;margin:auto}.heading,.section-header,.control-row,.filter-row,.header-actions,.actions{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.heading h1{font-size:25px;margin:4px 0}.eyebrow{font-size:10px;color:#8db9ff;font-weight:800;letter-spacing:1.3px;margin:0}.subtitle,.muted,.footnote{color:#9daabd;font-size:12px}.surface{background:#1c2430;border:1px solid #303d50;border-radius:12px;padding:22px}.surface h2,.surface h3{margin:0 0 8px}.surface h2{font-size:17px}.surface h3{font-size:13px}.control-row{justify-content:space-between}.grow{flex:1;min-width:240px}.field{display:flex;flex-direction:column;gap:6px;font-size:12px;min-width:155px}.field span,.info-grid small,.metric small{color:#aab8c9;font-size:11px}.field input,.field select,.field textarea,.header-actions select{color:#e8edf5;background:#141b25;border:1px solid #3b495b;border-radius:7px;padding:10px 11px;font:inherit;min-height:38px}.field textarea{resize:vertical}.field input:focus,.field select:focus,.field textarea:focus{outline:2px solid #4f8cff55;border-color:#4f8cff}.btn{border:1px solid #4f8cff;background:#4f8cff;color:#fff;border-radius:7px;padding:10px 14px;font-size:12px;cursor:pointer;font-weight:650}.btn:hover{filter:brightness(1.1)}.btn:disabled{opacity:.5;cursor:not-allowed}.btn.secondary{background:#293749;border-color:#43546b;color:#d9e7f9}.btn.danger{background:#592d35;border-color:#9a4c58;color:#ffd4d8}.tabs{display:flex;gap:5px}.tabs button{border:0;background:transparent;color:#a6b6c7;padding:10px 12px;border-radius:7px;cursor:pointer}.tabs button.active{background:#263951;color:#91bcff;font-weight:bold}.plain-link,.link-btn{color:#92bbff;font-size:12px}.link-btn{background:none;border:0;cursor:pointer;text-decoration:underline}.table-wrap{overflow:auto}.data-table{width:100%;border-collapse:collapse;font-size:12px;min-width:680px}.data-table th{text-align:left;color:#9cabbd;font-size:11px;background:#212c39;padding:12px}.data-table td{padding:12px;border-bottom:1px solid #303a49;vertical-align:middle}.data-table td small{display:block;color:#95a5b9;margin-top:4px}.chosen{background:#253650}.pill{display:inline-flex;border-radius:30px;background:#324356;color:#d3e4f8;padding:4px 9px;font-size:10px}.pill.approved,.pill.closed{background:#1c4c43;color:#a0ecd0}.pill.rejected{background:#59323b;color:#ffbdc9}.pill.implementing{background:#254b6a;color:#b9dcff}.pill.under_review{background:#5b4a29;color:#ffdf9d}.info-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:20px 0}.info-grid div{display:grid;gap:5px}.info-grid b{font-size:12px;overflow-wrap:anywhere}.description-grid,.audit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:20px 0}.description-grid p,.audit-item p{white-space:pre-wrap;overflow-wrap:anywhere;margin:3px 0 7px;font-size:12px;line-height:1.5}.actions{justify-content:flex-start;margin-top:16px}.message{border-radius:8px;padding:11px 14px;font-size:12px}.message.error{background:#4b2832;color:#ffd6dc}.message.ok{background:#1c473c;color:#b1f1d9}.empty{text-align:center;padding:25px;color:#9aabc0;font-size:13px}.operation-panel{margin-top:20px;padding:18px;border-radius:10px;background:#151f2b;border:1px solid #3c4f67;display:grid;gap:12px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.wide{grid-column:1/-1}.preview{padding-top:10px}.audit-item{border-left:2px solid #4f8cff;padding:8px 11px;margin:9px 0;background:#212d3b;border-radius:0 7px 7px 0}.audit-item strong,.audit-item small{display:block;font-size:11px}.audit-item small{color:#9daabd;margin:4px 0}.audit-item summary{cursor:pointer;color:#92bbff;font-size:11px}.audit-item pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:10px}.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;margin-top:15px}.metric{background:#141e29;border:1px solid #334357;border-radius:9px;padding:17px;display:grid;gap:9px}.metric strong{font-size:23px;color:#93beff}.metric span{font-size:11px;color:#a2b0c1}.footnote{margin-top:15px;line-height:1.7}.modal-backdrop{position:fixed;inset:0;background:#03070dc9;z-index:100;display:grid;place-items:center;padding:15px}.modal{background:#1b2532;border:1px solid #42516a;border-radius:12px;padding:22px;width:min(760px,100%);max-height:90vh;overflow:auto}.modal form{display:grid;gap:14px}.filter-row{justify-content:flex-start;margin-top:14px}@media(max-width:900px){.info-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.description-grid,.audit-grid{grid-template-columns:1fr}}@media(max-width:640px){.changes-page{padding:15px}.surface{padding:14px}.form-grid,.metric-grid{grid-template-columns:1fr}.field{min-width:0}.info-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
