<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { milestoneService, type Milestone, type MilestonePayload, type MilestoneStatus } from '../../services/milestones'
import MilestoneKpisManager from './MilestoneKpisManager.vue'

const props = defineProps<{
  projectId: number
  startDate: string
  endDate: string
  milestones: Milestone[]
  tasks: { id: number; name: string }[]
}>()
const emit = defineEmits<{ (event: 'changed'): void }>()
const opened = ref(false)
const editingId = ref<number | null>(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const form = ref<MilestonePayload>(initialForm())
const selectedKpiMilestoneId = ref<number | null>(null)
const selectedKpiMilestone = computed(() => props.milestones.find(item => item.id === selectedKpiMilestoneId.value) ?? null)
const completed = computed(() => props.milestones.filter(m => m.status === 'COMPLETED').length)

function initialForm(): MilestonePayload {
  return {
    project: props.projectId, name: '', due_date: props.startDate,
    responsible: '', acceptance_criteria: '', evidence: '',
    status: 'PENDING', completed_at: null, tasks: [],
  }
}
function displayDate(date: string | null): string {
  if (!date) return '—'
  const [y, m, d] = date.split('-')
  return `${d}/${m}/${y}`
}
function message(err: unknown): string {
  if (!isAxiosError(err)) return 'No se pudo completar la operación.'
  const data: unknown = err.response?.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`).join(' | ')
  }
  return `Error HTTP ${err.response?.status ?? 'de conexión'}`
}
function reset() {
  opened.value = false
  editingId.value = null
  form.value = initialForm()
  error.value = ''
}
function create() {
  reset()
  opened.value = true
}
function edit(milestone: Milestone) {
  editingId.value = milestone.id
  form.value = {
    project: milestone.project, name: milestone.name, due_date: milestone.due_date,
    responsible: milestone.responsible, acceptance_criteria: milestone.acceptance_criteria,
    evidence: milestone.evidence, status: milestone.status, completed_at: milestone.completed_at, tasks: [...(milestone.tasks ?? [])],
  }
  error.value = ''
  notice.value = ''
  opened.value = true
}
function statusChanged(value: Event) {
  const target = value.target as HTMLSelectElement
  form.value.status = target.value as MilestoneStatus
  if (form.value.status === 'PENDING') form.value.completed_at = null
}
async function save() {
  error.value = ''
  notice.value = ''
  if (!form.value.name.trim() || !form.value.responsible.trim() || !form.value.acceptance_criteria.trim()) {
    error.value = 'Nombre, responsable y criterio de aceptación son obligatorios.'
    return
  }
  if (form.value.due_date < props.startDate || form.value.due_date > props.endDate) {
    error.value = 'La fecha del hito debe estar dentro del proyecto.'
    return
  }
  if (form.value.status === 'COMPLETED' && (!form.value.completed_at || !form.value.evidence.trim())) {
    error.value = 'Para cumplir un hito debes registrar fecha de cumplimiento y evidencia.'
    return
  }
  busy.value = true
  try {
    const payload = { ...form.value }
    if (editingId.value === null) await milestoneService.create(payload)
    else await milestoneService.update(editingId.value, payload)
    reset()
    notice.value = 'Hito guardado correctamente.'
    emit('changed')
  } catch (err) {
    error.value = message(err)
  } finally {
    busy.value = false
  }
}
async function remove(milestone: Milestone) {
  if (!window.confirm(`¿Eliminar el hito «${milestone.name}»?`)) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await milestoneService.remove(milestone.id)
    if (selectedKpiMilestoneId.value === milestone.id) selectedKpiMilestoneId.value = null
    notice.value = 'Hito eliminado.'
    emit('changed')
  } catch (err) {
    error.value = message(err)
  } finally {
    busy.value = false
  }
}
function toggleTask(taskId: number, checked: boolean) {
  if (checked && !form.value.tasks.includes(taskId)) form.value.tasks = [...form.value.tasks, taskId]
  if (!checked) form.value.tasks = form.value.tasks.filter(id => id !== taskId)
}
function selectKpis(milestoneId: number) {
  selectedKpiMilestoneId.value = selectedKpiMilestoneId.value === milestoneId ? null : milestoneId
  opened.value = false
}
watch(() => props.projectId, () => { reset(); selectedKpiMilestoneId.value = null; notice.value = '' })
</script>

<template>
  <section class="milestones-manager">
    <div class="milestones-title">
      <div>
        <h2>Hitos del proyecto</h2>
        <p class="muted">{{ milestones.length }} hitos · {{ completed }} cumplidos. Los hitos no son actividades ni se reprograman mediante dependencias.</p>
      </div>
      <button type="button" class="primary-button" :disabled="busy" @click="create">Nuevo hito</button>
    </div>
    <p v-if="error" class="milestone-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="milestone-notice" role="status">{{ notice }}</p>
    <div class="milestone-table-scroll">
      <table class="milestone-table">
        <thead><tr><th>Hito</th><th>Fecha prevista</th><th>Responsable</th><th>Estado</th><th>Cumplimiento real</th><th>Evidencia</th><th>Actividades asociadas</th><th>Acciones</th></tr></thead>
        <tbody>
          <tr v-for="milestone in milestones" :key="milestone.id">
            <td :title="milestone.acceptance_criteria">{{ milestone.name }}<small>{{ milestone.acceptance_criteria }}</small></td>
            <td>{{ displayDate(milestone.due_date) }}</td>
            <td>{{ milestone.responsible }}</td>
            <td><span :class="['milestone-state', milestone.status === 'COMPLETED' ? 'complete' : 'pending']">{{ milestone.status_display }}</span></td>
            <td>{{ displayDate(milestone.completed_at) }}</td>
            <td class="milestone-evidence">{{ milestone.evidence || '—' }}</td>
            <td class="milestone-associations">
              <span v-if="!(milestone.tasks ?? []).length" class="muted">Sin actividades</span>
              <template v-else>
                <span v-for="taskId in (milestone.tasks ?? [])" :key="taskId" class="task-tag">{{ tasks.find(t => t.id === taskId)?.name ?? `#${taskId}` }}</span>
              </template>
            </td>
            <td class="milestone-actions"><button type="button" :disabled="busy" @click="edit(milestone)">Editar</button><button type="button" :disabled="busy" @click="selectKpis(milestone.id)">{{ selectedKpiMilestoneId === milestone.id ? 'Ocultar KPI' : 'Ver KPI' }}</button><button type="button" :disabled="busy" @click="remove(milestone)">Eliminar</button></td>
          </tr>
          <tr v-if="milestones.length === 0"><td colspan="8" class="muted">Todavía no hay hitos definidos.</td></tr>
        </tbody>
      </table>
    </div>
    <form v-if="opened" class="milestone-editor" @submit.prevent="save">
      <h3>{{ editingId === null ? 'Crear hito' : 'Editar hito' }}</h3>
      <div class="milestone-fields">
        <label>Nombre <input v-model="form.name" class="form-control" required maxlength="200" /></label>
        <label>Fecha prevista <input v-model="form.due_date" class="form-control" type="date" :min="startDate" :max="endDate" required /></label>
        <label>Responsable <input v-model="form.responsible" class="form-control" maxlength="150" required /></label>
        <label>Estado <select :value="form.status" class="form-control" @change="statusChanged"><option value="PENDING">Pendiente</option><option value="COMPLETED">Cumplido</option></select></label>
        <div class="full task-selection">
          <strong>Actividades asociadas</strong>
          <p class="muted">Selecciona las actividades de este proyecto que contribuyen al hito. Un hito puede tener varias.</p>
          <div v-if="tasks.length" class="task-selection-options">
            <label v-for="task in tasks" :key="task.id" class="task-option">
              <input type="checkbox" :checked="form.tasks.includes(task.id)" @change="toggleTask(task.id, ($event.target as HTMLInputElement).checked)" />
              <span>{{ task.name }}</span>
            </label>
          </div>
          <p v-else class="muted">El proyecto todavía no tiene actividades.</p>
        </div>
        <label class="full">Criterio de aceptación <textarea v-model="form.acceptance_criteria" class="form-control" rows="2" required /></label>
        <label class="full">Evidencia (texto, referencia o URL) <textarea v-model="form.evidence" class="form-control" rows="2" /></label>
        <label v-if="form.status === 'COMPLETED'">Fecha de cumplimiento <input v-model="form.completed_at" class="form-control" type="date" required /></label>
      </div>
      <div class="milestone-actions"><button class="primary-button" type="submit" :disabled="busy">{{ busy ? 'Guardando…' : 'Guardar hito' }}</button><button class="secondary-button" type="button" :disabled="busy" @click="reset">Cancelar</button></div>
    </form>
    <MilestoneKpisManager
      v-if="selectedKpiMilestone"
      :key="selectedKpiMilestone.id"
      :milestone-id="selectedKpiMilestone.id"
      :milestone-name="selectedKpiMilestone.name"
    />
  </section>
</template>

<style scoped>
.milestones-manager { min-width: 0; }
.milestones-title { display:flex; justify-content:space-between; align-items:flex-start; gap:14px; margin-bottom:16px; }
.milestones-title h2 { margin:0 0 7px; font-size:17px; }
.muted { color: var(--color-muted); font-size:12px; line-height:1.6; }
.milestone-table-scroll { overflow-x:auto; }
.milestone-table { width:100%; border-collapse:collapse; font-size:12px; }
.milestone-table th, .milestone-table td { text-align:left; vertical-align:top; padding:12px; border-bottom:1px solid var(--color-border); }
.milestone-table th { color:var(--color-muted); white-space:nowrap; }
.milestone-table small { display:block; max-width:250px; overflow:hidden; text-overflow:ellipsis; color:var(--color-muted); margin-top:5px; }
.milestone-evidence { max-width:200px; overflow-wrap:anywhere; }
.milestone-associations { min-width:155px; max-width:240px; }
.task-tag { display:inline-block; margin:2px 4px 2px 0; padding:4px 7px; border:1px solid var(--color-border); border-radius:5px; font-size:11px; }
.task-selection { grid-column:1/-1; border:1px solid var(--color-border); padding:12px; border-radius:8px; }
.task-selection strong { font-size:12px; }
.task-selection-options { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; max-height:170px; overflow-y:auto; margin-top:12px; }
.task-selection-options .task-option { display:flex; flex-direction:row; align-items:center; gap:8px; color:var(--color-text); }
.milestone-actions { display:flex; gap:8px; align-items:center; }
.milestone-actions button:not(.primary-button):not(.secondary-button) { background:transparent; border:1px solid var(--color-border); color:var(--color-text); border-radius:5px; padding:6px 8px; cursor:pointer; }
.milestone-state { white-space:nowrap; } .milestone-state.complete { color:#65d1ad; } .milestone-state.pending { color:#dfb86b; }
.milestone-error { color:#f19b88; margin:10px 0; } .milestone-notice { color:#65d1ad; margin:10px 0; }
.milestone-editor { margin-top:16px; padding:18px; border:1px solid var(--color-border); border-radius:9px; }
.milestone-editor h3 { margin:0 0 16px; font-size:15px; }
.milestone-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
.milestone-fields label { display:flex; flex-direction:column; gap:7px; font-size:12px; color:var(--color-muted); }
.milestone-fields label.full { grid-column:1/-1; }
.milestone-editor .milestone-actions { margin-top:18px; }
@media(max-width:700px){ .task-selection-options { grid-template-columns:1fr; } .milestone-fields {grid-template-columns:1fr;} .milestones-title {flex-direction:column;} }
</style>
