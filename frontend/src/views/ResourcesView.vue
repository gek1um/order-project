<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { RouterLink } from 'vue-router'
import { projectService, type Project } from '../services/projects'
import { taskService, type Task } from '../services/tasks'
import {
  resourceService, assignmentService, type Resource, type ResourcePayload,
  type ResourceKind, type TaskResourceAssignment, type AssignmentPayload,
  type ProjectCostSummary, type WeeklyAvailability,
} from '../services/resources'

type Tab = 'catalog' | 'assignments' | 'summary'
const tabs: { id: Tab; label: string }[] = [
  { id: 'catalog', label: 'Catálogo de recursos' },
  { id: 'assignments', label: 'Asignaciones a actividades' },
  { id: 'summary', label: 'Costos y disponibilidad' },
]
const kindOptions: { value: ResourceKind; label: string }[] = [
  { value: 'PROFESSIONAL', label: 'Profesional' },
  { value: 'PROFESSIONAL_TYPE', label: 'Tipo de profesional' },
  { value: 'LICENSE', label: 'Licencia de software' },
  { value: 'MATERIAL', label: 'Material' },
  { value: 'EQUIPMENT', label: 'Equipamiento' },
  { value: 'OTHER', label: 'Otro' },
]
const projects = ref<Project[]>([])
const selectedProjectId = ref<number | null>(null)
const tab = ref<Tab>('catalog')
const resources = ref<Resource[]>([])
const assignments = ref<TaskResourceAssignment[]>([])
const tasks = ref<Task[]>([])
const costSummary = ref<ProjectCostSummary | null>(null)
const availability = ref<WeeklyAvailability | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const notice = ref('')
const showResourceForm = ref(false)
const showAssignmentForm = ref(false)
const editingResourceId = ref<number | null>(null)
const editingAssignmentId = ref<number | null>(null)
let requestVersion = 0

const emptyResource = (): ResourcePayload => ({
  project: selectedProjectId.value ?? 0,
  kind: 'MATERIAL', name: '', description: '', specialty: '', unit: '',
  quantity: '1', periods: 1, hours_per_week: null, weeks: null,
  hourly_rate: null, unit_cost: '0',
})
const resourceForm = ref<ResourcePayload>(emptyResource())
const emptyAssignment = (): AssignmentPayload => ({
  task: tasks.value[0]?.id ?? 0,
  resource: resources.value[0]?.id ?? 0,
  planned_units: '1', actual_units: '0', notes: '',
})
const assignmentForm = ref<AssignmentPayload>(emptyAssignment())
const isHuman = computed(() => resourceForm.value.kind === 'PROFESSIONAL' || resourceForm.value.kind === 'PROFESSIONAL_TYPE')
const canAssign = computed(() => tasks.value.length > 0 && resources.value.length > 0)
const overallocated = computed(() => availability.value?.weeks.filter(row => row.overallocated) ?? [])
const money = (v: string | number | null | undefined) =>
  v === null || v === undefined ? '—' : new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 }).format(Number(v))
const dateLabel = (date: string) => {
  const [y, m, d] = date.split('-')
  return y && m && d ? `${d}/${m}/${y}` : date
}
const kindName = (kind: ResourceKind) => kindOptions.find(item => item.value === kind)?.label ?? kind
function errorMessage(err: unknown): string {
  if (!isAxiosError(err)) return err instanceof Error ? err.message : 'Error inesperado.'
  if (!err.response) return 'No se pudo conectar con Django.'
  const data: unknown = err.response.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([field, value]) => {
      const description = Array.isArray(value) ? value.map(String).join(', ') : String(value)
      return field === 'detail' ? description : `${field}: ${description}`
    }).join(' | ')
  }
  return `Error HTTP ${err.response.status}`
}
async function loadProjects() {
  try {
    projects.value = await projectService.list()
    if (!selectedProjectId.value && projects.value.length > 0) selectedProjectId.value = projects.value[0]?.id ?? null
  } catch (err) { error.value = errorMessage(err) }
}
async function loadData() {
  const version = ++requestVersion
  const projectId = selectedProjectId.value
  resources.value = []; assignments.value = []; tasks.value = []
  costSummary.value = null; availability.value = null; error.value = ''
  if (!projectId) return
  loading.value = true
  try {
    const [resourceData, assignmentData, taskData, costData, availabilityData] = await Promise.all([
      resourceService.list(projectId), assignmentService.list(projectId),
      taskService.list({ project: projectId }), assignmentService.projectCosts(projectId),
      assignmentService.availability(projectId),
    ])
    if (version !== requestVersion) return
    resources.value = resourceData
    assignments.value = assignmentData
    tasks.value = taskData.filter(task => task.project === projectId)
    costSummary.value = costData
    availability.value = availabilityData
  } catch (err) {
    if (version === requestVersion) error.value = errorMessage(err)
  } finally { if (version === requestVersion) loading.value = false }
}
watch(selectedProjectId, () => {
  showResourceForm.value = false
  showAssignmentForm.value = false
  formError.value = ''; notice.value = ''
  void loadData()
})
onMounted(() => { void loadProjects() })

function createResource() {
  editingResourceId.value = null; resourceForm.value = emptyResource()
  formError.value = ''; showResourceForm.value = true
}
function editResource(resource: Resource) {
  editingResourceId.value = resource.id
  resourceForm.value = {
    project: resource.project, kind: resource.kind, name: resource.name,
    description: resource.description, specialty: resource.specialty, unit: resource.unit,
    quantity: resource.quantity, periods: resource.periods,
    hours_per_week: resource.hours_per_week, weeks: resource.weeks,
    hourly_rate: resource.hourly_rate, unit_cost: resource.unit_cost,
  }
  formError.value = ''; showResourceForm.value = true
}
function validNonNegative(value: string | null, allowZero = true): boolean {
  if (value === null || value.trim() === '') return false
  const n = Number(value)
  return Number.isFinite(n) && (allowZero ? n >= 0 : n > 0)
}
async function saveResource() {
  if (saving.value) return
  const f = resourceForm.value
  if (!f.name.trim() || !validNonNegative(f.quantity, false) || !Number.isInteger(Number(f.periods)) || f.periods < 1) {
    formError.value = 'Ingresa nombre, cantidad positiva y períodos válidos.'; return
  }
  if (f.kind === 'PROFESSIONAL' && (!f.specialty.trim() || Number(f.quantity) !== 1)) {
    formError.value = 'El profesional individual requiere especialidad y cantidad igual a 1.'; return
  }
  if (isHuman.value && (!validNonNegative(f.hours_per_week, false) || !validNonNegative(f.weeks, false) || !validNonNegative(f.hourly_rate))) {
    formError.value = 'Completa horas semanales, semanas y tarifa por hora.'; return
  }
  if (!isHuman.value && !validNonNegative(f.unit_cost)) { formError.value = 'Ingresa un costo unitario válido.'; return }
  saving.value = true; formError.value = ''; notice.value = ''
  try {
    const payload: ResourcePayload = {
      ...f, project: selectedProjectId.value ?? 0,
      hours_per_week: isHuman.value ? f.hours_per_week : null,
      weeks: isHuman.value ? f.weeks : null,
      hourly_rate: isHuman.value ? f.hourly_rate : null,
      unit_cost: isHuman.value ? null : f.unit_cost,
      periods: f.kind === 'LICENSE' || f.kind === 'EQUIPMENT' ? Number(f.periods) : 1,
    }
    if (editingResourceId.value) await resourceService.update(editingResourceId.value, payload)
    else await resourceService.create(payload)
    showResourceForm.value = false; notice.value = 'Recurso guardado correctamente.'
    await loadData()
  } catch (err) { formError.value = errorMessage(err) }
  finally { saving.value = false }
}
async function removeResource(resource: Resource) {
  if (saving.value || !window.confirm(`¿Eliminar el recurso «${resource.name}»? No será posible si tiene asignaciones.`)) return
  saving.value = true; error.value = ''; notice.value = ''
  try { await resourceService.remove(resource.id); notice.value = 'Recurso eliminado.'; await loadData() }
  catch (err) { error.value = errorMessage(err) }
  finally { saving.value = false }
}
function createAssignment() {
  editingAssignmentId.value = null; assignmentForm.value = emptyAssignment()
  formError.value = ''; showAssignmentForm.value = true
}
function editAssignment(item: TaskResourceAssignment) {
  editingAssignmentId.value = item.id
  assignmentForm.value = {
    task: item.task, resource: item.resource, planned_units: item.planned_units,
    actual_units: item.actual_units, planned_unit_cost: item.planned_unit_cost,
    actual_unit_cost: item.actual_unit_cost, notes: item.notes,
  }
  formError.value = ''; showAssignmentForm.value = true
}
async function saveAssignment() {
  if (saving.value) return
  const f = assignmentForm.value
  if (!tasks.value.some(t => t.id === f.task) || !resources.value.some(r => r.id === f.resource)
      || !validNonNegative(f.planned_units, false) || !validNonNegative(f.actual_units)
      || (f.planned_unit_cost !== undefined && !validNonNegative(f.planned_unit_cost))
      || (f.actual_unit_cost !== undefined && !validNonNegative(f.actual_unit_cost))) {
    formError.value = 'Revisa la actividad, recurso, unidades y costos.'; return
  }
  saving.value = true; formError.value = ''; notice.value = ''
  try {
    if (editingAssignmentId.value) await assignmentService.update(editingAssignmentId.value, f)
    else await assignmentService.create(f)
    showAssignmentForm.value = false; notice.value = 'Asignación guardada correctamente.'
    await loadData()
  } catch (err) { formError.value = errorMessage(err) }
  finally { saving.value = false }
}
async function removeAssignment(item: TaskResourceAssignment) {
  if (saving.value || !window.confirm(`¿Eliminar la asignación de «${item.resource_name}» a «${item.task_name}»?`)) return
  saving.value = true; error.value = ''; notice.value = ''
  try { await assignmentService.remove(item.id); notice.value = 'Asignación eliminada.'; await loadData() }
  catch (err) { error.value = errorMessage(err) }
  finally { saving.value = false }
}
</script>

<template>
  <section class="resources-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Recursos y costos</h1>
        <p class="page-description">Catálogo, asignaciones, costos planificados/reales y disponibilidad semanal estimada.</p>
      </div>
      <button class="secondary-button" :disabled="loading || !selectedProjectId" @click="loadData">Actualizar datos</button>
    </header>

    <div class="panel project-filter">
      <label for="resource-project">Proyecto</label>
      <select id="resource-project" v-model.number="selectedProjectId" :disabled="loading || projects.length === 0">
        <option :value="null" disabled>Selecciona un proyecto</option>
        <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.code }} — {{ project.name }}</option>
      </select>
      <RouterLink v-if="selectedProjectId" :to="`/projects/${selectedProjectId}`" class="text-link">Ver proyecto</RouterLink>
    </div>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="notice" class="message ok" role="status">{{ notice }}</p>
    <p v-if="loading" class="message">Cargando recursos y costos...</p>
    <p v-else-if="!selectedProjectId" class="message">Crea o selecciona un proyecto para comenzar.</p>

    <template v-if="selectedProjectId && !loading">
      <nav class="tabs" aria-label="Secciones de recursos">
        <button v-for="item in tabs" :key="item.id" type="button" :class="['tab', { active: tab === item.id }]" @click="tab = item.id">{{ item.label }}</button>
      </nav>

      <section v-if="tab === 'catalog'" class="panel">
        <div class="section-heading">
          <div><h2>Catálogo de recursos</h2><p>Los precios del catálogo son estimaciones. No representan costos ejecutados.</p></div>
          <button class="primary-button" @click="createResource">+ Nuevo recurso</button>
        </div>
        <div class="table-scroll">
          <table><thead><tr><th>Recurso</th><th>Tipo</th><th>Cantidad</th><th>Unidad / especialidad</th><th>Costo estimado</th><th>Acciones</th></tr></thead>
            <tbody>
              <tr v-for="item in resources" :key="item.id">
                <td><strong>{{ item.name }}</strong><small v-if="item.description">{{ item.description }}</small></td>
                <td>{{ kindName(item.kind) }}</td><td>{{ item.quantity }}</td>
                <td>{{ item.specialty || item.unit || '—' }}</td><td>${{ money(item.estimated_catalog_cost) }}</td>
                <td class="actions"><button class="small-button" @click="editResource(item)">Editar</button><button class="small-button danger-text" :disabled="saving" @click="removeResource(item)">Eliminar</button></td>
              </tr>
              <tr v-if="resources.length === 0"><td colspan="6" class="empty">Este proyecto todavía no tiene recursos.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="tab === 'assignments'" class="panel">
        <div class="section-heading">
          <div><h2>Asignaciones por actividad</h2><p>Las unidades de profesionales son horas-persona; las licencias y equipos se expresan en unidades-período.</p></div>
          <button class="primary-button" :disabled="!canAssign" @click="createAssignment">+ Nueva asignación</button>
        </div>
        <p v-if="!canAssign" class="hint">Primero crea al menos una actividad y un recurso en este proyecto.</p>
        <div class="table-scroll">
          <table><thead><tr><th>Actividad</th><th>Recurso</th><th>Unidades plan.</th><th>Unidades reales</th><th>Costo plan.</th><th>Costo real</th><th>Acciones</th></tr></thead>
            <tbody>
              <tr v-for="item in assignments" :key="item.id"><td>{{ item.task_name }}</td><td>{{ item.resource_name }}</td><td>{{ item.planned_units }}</td><td>{{ item.actual_units }}</td><td>${{ money(item.planned_cost) }}</td><td>${{ money(item.actual_cost) }}</td>
                <td class="actions"><button class="small-button" @click="editAssignment(item)">Editar</button><button class="small-button danger-text" :disabled="saving" @click="removeAssignment(item)">Eliminar</button></td></tr>
              <tr v-if="assignments.length === 0"><td colspan="7" class="empty">Todavía no existen asignaciones.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="tab === 'summary'" class="summary-layout">
        <div class="metrics" v-if="costSummary">
          <div class="metric"><span>Presupuesto inicial</span><strong>${{ money(costSummary.baseline_budget) }}</strong></div>
          <div class="metric"><span>Costo planificado</span><strong>${{ money(costSummary.planned_resource_cost) }}</strong></div>
          <div class="metric"><span>Costo real acumulado</span><strong>${{ money(costSummary.actual_resource_cost) }}</strong></div>
          <div class="metric"><span>Real menos planificado</span><strong :class="Number(costSummary.actual_minus_planned) > 0 ? 'danger-text' : 'success-text'">${{ money(costSummary.actual_minus_planned) }}</strong></div>
        </div>
        <div class="panel" v-if="costSummary">
          <h2>Comparación con el presupuesto</h2>
          <div class="budget-grid"><p>Saldo presupuestario frente al plan: <strong>${{ money(costSummary.planned_budget_variance) }}</strong></p><p>Saldo presupuestario frente al costo real: <strong>${{ money(costSummary.actual_budget_variance) }}</strong></p><p>Asignaciones registradas: <strong>{{ costSummary.assignment_count }}</strong></p></div>
          <p class="hint">El saldo compara el presupuesto inicial con recursos valorizados. No representa flujo de caja ni todos los gastos posibles del proyecto.</p>
        </div>
        <div class="panel" v-if="availability">
          <div class="section-heading"><div><h2>Disponibilidad semanal de profesionales</h2><p>{{ availability.note }}</p></div><span :class="['pill', overallocated.length ? 'pill-warning' : 'pill-ok']">{{ overallocated.length }} semanas/recurso sobreasignadas</span></div>
          <div class="table-scroll"><table><thead><tr><th>Recurso</th><th>Semana</th><th>Capacidad</th><th>Carga</th><th>Disponible</th><th>Exceso</th><th>Estado</th></tr></thead>
            <tbody><tr v-for="(row, index) in availability.weeks" :key="`${row.resource_id}-${row.week_start}-${index}`" :class="{ overallocated: row.overallocated }"><td>{{ row.resource_name }}</td><td>{{ dateLabel(row.week_start) }} – {{ dateLabel(row.week_end) }}</td><td>{{ row.capacity_hours }} h</td><td>{{ row.planned_hours }} h</td><td>{{ row.available_hours }} h</td><td>{{ row.overallocation_hours }} h</td><td><span :class="['pill', row.overallocated ? 'pill-warning' : 'pill-ok']">{{ row.overallocated ? 'Sobreasignado' : 'Disponible' }}</span></td></tr>
              <tr v-if="availability.weeks.length === 0"><td colspan="7" class="empty">No hay profesionales o semanas para mostrar.</td></tr></tbody></table></div>
          <p v-for="(warning, index) in availability.warnings" :key="index" class="message error">Actividad #{{ warning.task_id }}: {{ warning.detail }}</p>
        </div>
      </section>
    </template>

    <div v-if="showResourceForm" class="overlay" @click.self="showResourceForm = false">
      <form class="dialog panel" @submit.prevent="saveResource">
        <div class="section-heading"><h2>{{ editingResourceId ? 'Editar recurso' : 'Crear recurso' }}</h2><button type="button" class="small-button" @click="showResourceForm = false">Cerrar ×</button></div>
        <div class="form-grid">
          <label>Nombre<input v-model.trim="resourceForm.name" maxlength="200" required /></label>
          <label>Tipo<select v-model="resourceForm.kind"><option v-for="kind in kindOptions" :key="kind.value" :value="kind.value">{{ kind.label }}</option></select></label>
          <label class="full">Descripción<textarea v-model="resourceForm.description" rows="2" /></label>
          <label>Cantidad<input v-model="resourceForm.quantity" type="number" min="0.01" step="0.01" required /></label>
          <template v-if="isHuman">
            <label>Especialidad<input v-model.trim="resourceForm.specialty" :required="resourceForm.kind === 'PROFESSIONAL'" /></label>
            <label>Horas por semana<input v-model="resourceForm.hours_per_week" type="number" min="0.01" step="0.01" required /></label>
            <label>Número de semanas<input v-model="resourceForm.weeks" type="number" min="0.01" step="0.01" required /></label>
            <label>Tarifa por hora ($)<input v-model="resourceForm.hourly_rate" type="number" min="0" step="0.01" required /></label>
          </template>
          <template v-else>
            <label>Unidad<input v-model.trim="resourceForm.unit" placeholder="unidad, metro, caja..." /></label>
            <label>Costo unitario ($)<input v-model="resourceForm.unit_cost" type="number" min="0" step="0.01" required /></label>
            <label v-if="resourceForm.kind === 'LICENSE' || resourceForm.kind === 'EQUIPMENT'">Períodos<input v-model.number="resourceForm.periods" type="number" min="1" step="1" required /></label>
          </template>
        </div>
        <p v-if="formError" class="message error" role="alert">{{ formError }}</p>
        <div class="dialog-actions"><button class="secondary-button" type="button" @click="showResourceForm = false">Cancelar</button><button class="primary-button" type="submit" :disabled="saving">{{ saving ? 'Guardando...' : 'Guardar recurso' }}</button></div>
      </form>
    </div>

    <div v-if="showAssignmentForm" class="overlay" @click.self="showAssignmentForm = false">
      <form class="dialog panel" @submit.prevent="saveAssignment">
        <div class="section-heading"><h2>{{ editingAssignmentId ? 'Editar asignación' : 'Crear asignación' }}</h2><button type="button" class="small-button" @click="showAssignmentForm = false">Cerrar ×</button></div>
        <div class="form-grid">
          <label>Actividad<select v-model.number="assignmentForm.task" required><option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.name }}</option></select></label>
          <label>Recurso<select v-model.number="assignmentForm.resource" required><option v-for="resource in resources" :key="resource.id" :value="resource.id">{{ resource.name }}</option></select></label>
          <label>Unidades planificadas<input v-model="assignmentForm.planned_units" type="number" min="0.01" step="0.01" required /></label>
          <label>Unidades reales<input v-model="assignmentForm.actual_units" type="number" min="0" step="0.01" required /></label>
          <template v-if="editingAssignmentId">
            <label>Costo unitario planificado ($)<input v-model="assignmentForm.planned_unit_cost" type="number" min="0" step="0.01" required /></label>
            <label>Costo unitario real ($)<input v-model="assignmentForm.actual_unit_cost" type="number" min="0" step="0.01" required /></label>
          </template>
          <p v-else class="hint full">Los precios unitarios se tomarán del catálogo y quedarán congelados en esta asignación. Podrás ajustarlos después.</p>
          <label class="full">Notas<textarea v-model="assignmentForm.notes" rows="2" /></label>
        </div>
        <p v-if="formError" class="message error" role="alert">{{ formError }}</p>
        <div class="dialog-actions"><button type="button" class="secondary-button" @click="showAssignmentForm = false">Cancelar</button><button type="submit" class="primary-button" :disabled="saving">{{ saving ? 'Guardando...' : 'Guardar asignación' }}</button></div>
      </form>
    </div>
  </section>
</template>

<style scoped>
.resources-page { display: flex; flex-direction: column; gap: 22px; }
.panel { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 22px; }
.project-filter { display: flex; gap: 16px; align-items: end; flex-wrap: wrap; }
.project-filter label { display: flex; flex-direction: column; gap: 8px; color: var(--color-muted); font-size: 12px; }
.project-filter select { min-width: 280px; }
.text-link { color: #8bb7ff; font-size: 12px; }
.tabs { display: flex; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid var(--color-border); padding-bottom: 12px; }
.tab { padding: 10px 15px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); color: var(--color-muted); font-size: 12px; }
.tab.active { color: #b8d2ff; border-color: #5079b7; background: #263951; font-weight: 650; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.section-heading h2, .panel h2 { margin: 0; font-size: 17px; }
.section-heading p, .hint { margin: 7px 0 0; font-size: 12px; line-height: 1.6; color: var(--color-muted); }
input, select, textarea { width: 100%; min-height: 39px; border: 1px solid #485264; border-radius: 7px; background: #1e2530; padding: 9px 11px; outline: none; }
input:focus, select:focus, textarea:focus { border-color: var(--color-primary); }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid var(--color-border); padding: 13px 12px; text-align: left; white-space: nowrap; }
th { color: var(--color-muted); font-size: 11px; font-weight: 600; }
td strong { font-size: 12px; } td small { display: block; color: var(--color-muted); margin-top: 5px; max-width: 320px; overflow: hidden; text-overflow: ellipsis; }
.actions { display: flex; gap: 5px; }
.small-button { padding: 7px 10px; border: 1px solid #3e4c61; border-radius: 6px; color: #adcaff; background: #202b3a; font-size: 11px; }
.small-button:hover { background: #293c55; }
.danger-text { color: #f19489 !important; }.success-text { color: #70d8b2; }
.message { margin: 0; padding: 12px 15px; background: #293444; border-radius: 7px; color: var(--color-muted); font-size: 12px; }
.message.error { color: #ffaba6; background: #4b282d; }.message.ok { color: #8ee1b8; background: #243f36; }
.empty { text-align: center; padding: 30px; color: var(--color-muted); }
.summary-layout { display: flex; flex-direction: column; gap: 16px; }
.metrics { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 14px; }
.metric { border: 1px solid var(--color-border); padding: 22px; background: var(--color-surface); border-radius: 11px; display: flex; flex-direction: column; gap: 12px; }
.metric span { color: var(--color-muted); font-size: 11px; }.metric strong { font-size: 21px; overflow-wrap: anywhere; }
.budget-grid { display: flex; gap: 35px; flex-wrap: wrap; }.budget-grid p { color: var(--color-muted); font-size: 12px; }.budget-grid strong { color: var(--color-text); }
.pill { display: inline-block; font-size: 11px; font-weight: 600; padding: 6px 9px; border-radius: 14px; white-space: nowrap; }
.pill-warning { color: #ffcb99; background: #64452b; }.pill-ok { color: #8bddbb; background: #27463d; }
.overallocated { background: rgba(231,111,81,.09); }
.overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(9,14,23,.8); display: flex; align-items: center; justify-content: center; padding: 18px; }
.dialog { width: min(640px,100%); max-height: 92vh; overflow-y: auto; }
.form-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 15px; }
.form-grid label { display: flex; flex-direction: column; gap: 7px; color: #c8d2e0; font-size: 12px; }
.full { grid-column: 1/-1; }.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
@media(max-width: 900px) { .metrics { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media(max-width: 600px) { .metrics,.form-grid { grid-template-columns: 1fr; } .project-filter select { min-width: 0; } .dialog-actions { flex-wrap: wrap; } }
</style>
