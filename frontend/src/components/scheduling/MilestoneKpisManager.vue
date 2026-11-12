<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import {
  milestoneKpiService,
  type MilestoneKpi,
  type MilestoneKpiDirection,
  type MilestoneKpiKind,
  type MilestoneKpiPayload,
} from '../../services/milestoneKpis'

const props = defineProps<{ milestoneId: number; milestoneName: string }>()
const rows = ref<MilestoneKpi[]>([])
const busy = ref(false)
const loading = ref(false)
const opened = ref(false)
const editingId = ref<number | null>(null)
const error = ref('')
const notice = ref('')
let requestId = 0

function initialForm(): MilestoneKpiPayload {
  return {
    milestone: props.milestoneId, name: '', description: '', responsible: '',
    kind: 'VALUE', direction: 'AT_LEAST', unit: 'unidad', target_value: '0',
    measured_value: null, numerator: null, denominator: null, measured_at: null,
  }
}
const form = ref<MilestoneKpiPayload>(initialForm())
const summary = computed(() => ({
  total: rows.value.length,
  met: rows.value.filter(kpi => kpi.achievement_status === 'MET').length,
  notMet: rows.value.filter(kpi => kpi.achievement_status === 'NOT_MET').length,
  notMeasured: rows.value.filter(kpi => kpi.achievement_status === 'NOT_MEASURED').length,
}))
function errorText(err: unknown): string {
  if (!isAxiosError(err)) return 'No se pudo realizar la operación.'
  const data: unknown = err.response?.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([key, value]) => {
      const description = Array.isArray(value) ? value.map(String).join(', ') : String(value)
      return key === 'detail' ? description : `${key}: ${description}`
    }).join(' | ')
  }
  return `Error HTTP ${err.response?.status ?? 'de conexión'}`
}
async function load(): Promise<void> {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await milestoneKpiService.listByMilestone(props.milestoneId)
    if (id === requestId) rows.value = data
  } catch (err) {
    if (id === requestId) error.value = errorText(err)
  } finally {
    if (id === requestId) loading.value = false
  }
}
function cancel(): void { opened.value = false; editingId.value = null; error.value = '' }
function create(): void {
  form.value = initialForm()
  editingId.value = null
  error.value = ''
  notice.value = ''
  opened.value = true
}
function edit(row: MilestoneKpi): void {
  editingId.value = row.id
  form.value = {
    milestone: row.milestone, name: row.name, description: row.description,
    responsible: row.responsible, kind: row.kind, direction: row.direction,
    unit: row.unit, target_value: row.target_value, measured_value: row.measured_value,
    numerator: row.numerator, denominator: row.denominator, measured_at: row.measured_at,
  }
  error.value = ''
  notice.value = ''
  opened.value = true
}
function kindChanged(value: Event): void {
  const target = value.target as HTMLSelectElement
  form.value.kind = target.value as MilestoneKpiKind
  if (form.value.kind === 'PERCENTAGE') {
    form.value.unit = '%'
    form.value.measured_value = null
  } else {
    form.value.unit = 'unidad'
    form.value.numerator = null
    form.value.denominator = null
  }
  form.value.measured_at = null
}
function directionChanged(value: Event): void {
  form.value.direction = (value.target as HTMLSelectElement).value as MilestoneKpiDirection
}
const isNumber = (value: string | null): boolean => value !== null && value.trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0
function validate(): boolean {
  if (!form.value.name.trim() || !form.value.responsible.trim()) {
    error.value = 'Nombre y responsable son obligatorios.'
    return false
  }
  if (!isNumber(form.value.target_value)) {
    error.value = 'La meta debe ser un número mayor o igual a cero.'
    return false
  }
  if (form.value.kind === 'VALUE') {
    if (!form.value.unit.trim()) { error.value = 'Indica la unidad del indicador.'; return false }
    if (form.value.measured_value !== null && !isNumber(form.value.measured_value)) {
      error.value = 'La medición debe ser mayor o igual a cero.'; return false
    }
  } else {
    const onlyOne = (form.value.numerator === null) !== (form.value.denominator === null)
    if (onlyOne) { error.value = 'Ingresa numerador y denominador juntos.'; return false }
    if (form.value.numerator !== null && (!isNumber(form.value.numerator) || !isNumber(form.value.denominator) || Number(form.value.denominator) <= 0)) {
      error.value = 'El numerador no puede ser negativo y el denominador debe ser mayor que cero.'; return false
    }
  }
  const hasMeasurement = form.value.kind === 'VALUE' ? form.value.measured_value !== null : form.value.numerator !== null
  if (hasMeasurement && !form.value.measured_at) {
    error.value = 'Indica la fecha de medición para un resultado registrado.'; return false
  }
  return true
}
async function save(): Promise<void> {
  error.value = ''
  notice.value = ''
  if (!validate()) return
  busy.value = true
  try {
    const payload: MilestoneKpiPayload = {
      ...form.value,
      milestone: props.milestoneId,
      unit: form.value.kind === 'PERCENTAGE' ? '%' : form.value.unit.trim(),
      measured_value: form.value.kind === 'VALUE' ? form.value.measured_value : null,
      numerator: form.value.kind === 'PERCENTAGE' ? form.value.numerator : null,
      denominator: form.value.kind === 'PERCENTAGE' ? form.value.denominator : null,
    }
    if (editingId.value === null) await milestoneKpiService.create(payload)
    else await milestoneKpiService.update(editingId.value, payload)
    cancel()
    notice.value = 'Indicador guardado correctamente.'
    await load()
  } catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
async function remove(row: MilestoneKpi): Promise<void> {
  if (!window.confirm(`¿Eliminar el indicador «${row.name}»?`)) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await milestoneKpiService.remove(row.id)
    notice.value = 'Indicador eliminado.'
    await load()
  } catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
function statusText(status: MilestoneKpi['achievement_status']): string {
  return status === 'MET' ? 'Cumple' : status === 'NOT_MET' ? 'No cumple' : 'Sin medición'
}
function valueText(row: MilestoneKpi): string {
  return row.actual_value === null ? '—' : `${row.actual_value} ${row.unit}`
}
watch(() => props.milestoneId, () => {
  ++requestId
  rows.value = []
  cancel()
  notice.value = ''
  void load()
}, { immediate: true })
</script>

<template>
  <section class="kpi-manager">
    <header class="kpi-header">
      <div>
        <h3>Indicadores del hito: {{ milestoneName }}</h3>
        <p class="muted">{{ summary.total }} indicadores · {{ summary.met }} cumplen · {{ summary.notMet }} no cumplen · {{ summary.notMeasured }} sin medición.</p>
      </div>
      <div class="kpi-actions">
        <button type="button" class="secondary-button" :disabled="busy || loading" @click="load">Actualizar</button>
        <button type="button" class="primary-button" :disabled="busy" @click="create">Nuevo KPI</button>
      </div>
    </header>
    <p v-if="error" class="kpi-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="kpi-ok" role="status">{{ notice }}</p>
    <p v-if="loading" class="muted">Consultando indicadores…</p>
    <div class="kpi-table-scroll">
      <table class="kpi-table">
        <thead><tr><th>Indicador</th><th>Responsable</th><th>Meta</th><th>Resultado</th><th>Estado</th><th>Acciones</th></tr></thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td><strong>{{ row.name }}</strong><small>{{ row.description || row.kind_display }}</small></td>
            <td>{{ row.responsible }}</td>
            <td>{{ row.direction === 'AT_LEAST' ? '≥' : '≤' }} {{ row.target_value }} {{ row.unit }}</td>
            <td>{{ valueText(row) }}</td>
            <td><span :class="['kpi-status', row.achievement_status.toLowerCase().replaceAll('_', '-')]">{{ statusText(row.achievement_status) }}</span></td>
            <td><div class="kpi-actions"><button type="button" :disabled="busy" @click="edit(row)">Editar</button><button type="button" :disabled="busy" @click="remove(row)">Eliminar</button></div></td>
          </tr>
          <tr v-if="!loading && rows.length === 0"><td colspan="6" class="muted">Este hito todavía no tiene KPI registrados.</td></tr>
        </tbody>
      </table>
    </div>
    <form v-if="opened" class="kpi-editor" @submit.prevent="save">
      <h4>{{ editingId === null ? 'Crear KPI' : 'Editar KPI' }}</h4>
      <div class="kpi-fields">
        <label>Nombre <input v-model="form.name" class="form-control" maxlength="200" required /></label>
        <label>Responsable <input v-model="form.responsible" class="form-control" maxlength="150" required /></label>
        <label>Tipo <select class="form-control" :value="form.kind" @change="kindChanged"><option value="VALUE">Valor directo</option><option value="PERCENTAGE">Porcentaje</option></select></label>
        <label>Sentido de cumplimiento <select class="form-control" :value="form.direction" @change="directionChanged"><option value="AT_LEAST">Al menos la meta (≥)</option><option value="AT_MOST">Como máximo la meta (≤)</option></select></label>
        <label>Meta <input v-model="form.target_value" type="number" min="0" step="0.01" class="form-control" required /></label>
        <label v-if="form.kind === 'VALUE'">Unidad <input v-model="form.unit" maxlength="30" class="form-control" required /></label>
        <label v-if="form.kind === 'VALUE'">Resultado medido <input :value="form.measured_value ?? ''" type="number" min="0" step="0.01" class="form-control" placeholder="Sin medición" @input="form.measured_value = ($event.target as HTMLInputElement).value || null" /></label>
        <template v-else>
          <label>Numerador <input :value="form.numerator ?? ''" type="number" min="0" step="0.01" class="form-control" placeholder="Sin medición" @input="form.numerator = ($event.target as HTMLInputElement).value || null" /></label>
          <label>Denominador <input :value="form.denominator ?? ''" type="number" min="0.01" step="0.01" class="form-control" placeholder="Sin medición" @input="form.denominator = ($event.target as HTMLInputElement).value || null" /></label>
        </template>
        <label>Fecha de medición <input :value="form.measured_at ?? ''" type="date" class="form-control" @input="form.measured_at = ($event.target as HTMLInputElement).value || null" /></label>
        <label class="full">Descripción <textarea v-model="form.description" class="form-control" rows="2" /></label>
      </div>
      <p class="muted">El cumplimiento se calcula en Django. Dejar el resultado vacío conserva el estado «Sin medición».</p>
      <div class="kpi-actions"><button class="primary-button" type="submit" :disabled="busy">{{ busy ? 'Guardando…' : 'Guardar KPI' }}</button><button type="button" class="secondary-button" :disabled="busy" @click="cancel">Cancelar</button></div>
    </form>
  </section>
</template>

<style scoped>
.kpi-manager { margin-top: 22px; border-top:1px solid var(--color-border); padding-top:20px; }
.kpi-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:15px; }
.kpi-header h3 { margin:0 0 7px; font-size:15px; }
.muted { color:var(--color-muted); font-size:12px; line-height:1.6; }
.kpi-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.kpi-actions button:not(.primary-button):not(.secondary-button) { border:1px solid var(--color-border); border-radius:6px; background:transparent; color:var(--color-text); padding:6px 9px; cursor:pointer; }
.kpi-table-scroll { overflow-x:auto; }
.kpi-table { width:100%; border-collapse:collapse; font-size:12px; }
.kpi-table th,.kpi-table td { border-bottom:1px solid var(--color-border); padding:11px 9px; text-align:left; vertical-align:top; }
.kpi-table th { color:var(--color-muted); }
.kpi-table small { display:block; color:var(--color-muted); margin-top:5px; }
.kpi-status.met { color:#65d1ad; } .kpi-status.not-met { color:#f19b88; } .kpi-status.not-measured { color:#dfb86b; }
.kpi-editor { border:1px solid var(--color-border); border-radius:9px; padding:18px; margin-top:18px; }
.kpi-editor h4 { margin:0 0 14px; font-size:14px; }
.kpi-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px; }
.kpi-fields label { display:flex; flex-direction:column; gap:7px; color:var(--color-muted); font-size:12px; }
.kpi-fields label.full { grid-column:1/-1; }
.kpi-error { color:#f19b88; margin:10px 0; } .kpi-ok { color:#65d1ad; margin:10px 0; }
@media(max-width:700px){ .kpi-header {flex-direction:column;} .kpi-fields {grid-template-columns:1fr;} }
</style>
