<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import {
  calendarService,
  calendarExceptionService,
  type CalendarException,
  type WorkCalendar,
} from '../../services/calendars'

const props = defineProps<{ projectId: number; tasksCount: number }>()
const calendar = ref<WorkCalendar | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const deletingId = ref<number | null>(null)
const editingExceptionId = ref<number | null>(null)
const days = reactive({
  monday: true, tuesday: true, wednesday: true, thursday: true,
  friday: true, saturday: false, sunday: false,
})
const calendarName = ref('Calendario laboral')
const exceptionDate = ref('')
const exceptionWorking = ref(false)
const exceptionDescription = ref('')
let requestVersion = 0

const weekdays = [
  { key: 'monday', label: 'Lunes' },
  { key: 'tuesday', label: 'Martes' },
  { key: 'wednesday', label: 'Miércoles' },
  { key: 'thursday', label: 'Jueves' },
  { key: 'friday', label: 'Viernes' },
  { key: 'saturday', label: 'Sábado' },
  { key: 'sunday', label: 'Domingo' },
] as const

const hasWorkingDays = computed(() => Object.values(days).some(Boolean))
const exceptions = computed(() => [...(calendar.value?.exceptions ?? [])].sort((a, b) => a.date.localeCompare(b.date)))

function getError(err: unknown): string {
  if (!isAxiosError(err)) return 'Ocurrió un error inesperado.'
  if (!err.response) return 'No se pudo conectar con Django.'
  const data: unknown = err.response.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([key, value]) =>
      `${key}: ${Array.isArray(value) ? value.map(String).join(', ') : String(value)}`,
    ).join(' | ')
  }
  return `Error HTTP ${err.response.status}.`
}

function applyCalendar(value: WorkCalendar | null) {
  calendar.value = value
  calendarName.value = value?.name ?? 'Calendario laboral'
  for (const day of weekdays) days[day.key] = value?.[day.key] ?? (day.key !== 'saturday' && day.key !== 'sunday')
}

async function load() {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  try {
    const result = await calendarService.list(props.projectId)
    if (version === requestVersion) applyCalendar(result[0] ?? null)
  } catch (err) {
    if (version === requestVersion) error.value = getError(err)
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

function confirmImpact(): boolean {
  return props.tasksCount === 0 || window.confirm(
    'Este proyecto ya tiene actividades. Cambiar el calendario puede volver incompatibles sus fechas y el backend todavía no recalcula automáticamente todo el cronograma al editar calendarios. ¿Deseas continuar?',
  )
}

async function saveCalendar() {
  if (saving.value || !hasWorkingDays.value || !calendarName.value.trim()) return
  if (!confirmImpact()) return
  saving.value = true
  error.value = ''
  notice.value = ''
  const payload = { project: props.projectId, name: calendarName.value.trim(), ...days }
  try {
    if (calendar.value) {
      await calendarService.update(calendar.value.id, payload)
    } else {
      await calendarService.create(payload)
    }
    await load()
    notice.value = 'Calendario guardado correctamente. Revisa las fechas del cronograma.'
  } catch (err) {
    error.value = getError(err)
  } finally {
    saving.value = false
  }
}

function resetException() {
  editingExceptionId.value = null
  exceptionDate.value = ''
  exceptionWorking.value = false
  exceptionDescription.value = ''
}

function editException(item: CalendarException) {
  editingExceptionId.value = item.id
  exceptionDate.value = item.date
  exceptionWorking.value = item.is_working
  exceptionDescription.value = item.description
  error.value = ''
  notice.value = ''
}

async function saveException() {
  if (saving.value || !calendar.value || !exceptionDate.value) return
  if (!confirmImpact()) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const payload = {
      calendar: calendar.value.id,
      date: exceptionDate.value,
      is_working: exceptionWorking.value,
      description: exceptionDescription.value.trim(),
    }
    if (editingExceptionId.value !== null) {
      await calendarExceptionService.update(editingExceptionId.value, payload)
    } else {
      await calendarExceptionService.create(payload)
    }
    resetException()
    await load()
    notice.value = 'Excepción guardada. Revisa las fechas del cronograma.'
  } catch (err) {
    error.value = getError(err)
  } finally {
    saving.value = false
  }
}

async function removeException(item: CalendarException) {
  if (deletingId.value !== null || !confirmImpact()) return
  if (!window.confirm(`¿Eliminar la excepción del ${item.date}?`)) return
  deletingId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await calendarExceptionService.remove(item.id)
    if (editingExceptionId.value === item.id) resetException()
    await load()
    notice.value = 'Excepción eliminada. Revisa las fechas del cronograma.'
  } catch (err) {
    error.value = getError(err)
  } finally {
    deletingId.value = null
  }
}

watch(() => props.projectId, () => { ++requestVersion; applyCalendar(null); resetException(); void load() })
onMounted(() => { void load() })
</script>

<template>
  <section class="calendar-panel">
    <header class="setting-header">
      <div>
        <h3>Calendario laboral del proyecto</h3>
        <p>Selecciona los días habituales de trabajo y registra excepciones puntuales.</p>
      </div>
      <button class="small-button" type="button" :disabled="loading" @click="load">Actualizar</button>
    </header>
    <p class="warning">Cambiar días laborables o excepciones no propaga automáticamente los cambios a las tareas ya guardadas. Si el proyecto tiene actividades, revisa la planificación después de guardar.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="loading" class="muted">Cargando calendario…</p>

    <template v-else>
      <p class="muted calendar-source">{{ calendar ? 'Calendario configurado' : 'Se usa el calendario predeterminado de lunes a viernes hasta que guardes uno.' }}</p>
      <form class="settings-form" @submit.prevent="saveCalendar">
        <div class="field">
          <label for="calendar-name">Nombre</label>
          <input id="calendar-name" v-model="calendarName" required maxlength="150" />
        </div>
        <fieldset class="weekdays">
          <legend>Días laborables</legend>
          <label v-for="day in weekdays" :key="day.key" class="check-day">
            <input v-model="days[day.key]" type="checkbox" /> {{ day.label }}
          </label>
        </fieldset>
        <p v-if="!hasWorkingDays" class="error">Debes seleccionar al menos un día laborable.</p>
        <button class="primary" type="submit" :disabled="saving || !hasWorkingDays || !calendarName.trim()">{{ saving ? 'Guardando…' : calendar ? 'Guardar calendario' : 'Crear calendario' }}</button>
      </form>

      <div class="exceptions">
        <h4>Excepciones del calendario</h4>
        <p v-if="!calendar" class="muted">Primero crea y guarda el calendario para registrar excepciones.</p>
        <template v-else>
          <form class="exception-form" @submit.prevent="saveException">
            <div class="field">
              <label for="exception-date">Fecha</label>
              <input id="exception-date" v-model="exceptionDate" type="date" required />
            </div>
            <div class="field">
              <label for="exception-kind">Tipo</label>
              <select id="exception-kind" v-model="exceptionWorking">
                <option :value="false">Día no laborable</option>
                <option :value="true">Día laborable extraordinario</option>
              </select>
            </div>
            <div class="field description">
              <label for="exception-description">Descripción (opcional)</label>
              <input id="exception-description" v-model="exceptionDescription" maxlength="250" placeholder="Feriado, cierre, turno especial…" />
            </div>
            <div class="form-actions">
              <button class="primary" type="submit" :disabled="saving || !exceptionDate">{{ saving ? 'Guardando…' : editingExceptionId ? 'Guardar excepción' : 'Agregar excepción' }}</button>
              <button v-if="editingExceptionId" class="small-button" type="button" @click="resetException">Cancelar edición</button>
            </div>
          </form>
          <div class="scroll-table">
            <table>
              <thead><tr><th>Fecha</th><th>Tipo</th><th>Descripción</th><th>Acciones</th></tr></thead>
              <tbody>
                <tr v-for="item in exceptions" :key="item.id">
                  <td>{{ item.date }}</td>
                  <td>{{ item.is_working ? 'Laborable extraordinario' : 'No laborable' }}</td>
                  <td>{{ item.description || '—' }}</td>
                  <td class="inline-actions">
                    <button class="small-button" type="button" :disabled="saving || deletingId !== null" @click="editException(item)">Editar</button>
                    <button class="small-button danger" type="button" :disabled="saving || deletingId !== null" @click="removeException(item)">Eliminar</button>
                  </td>
                </tr>
                <tr v-if="exceptions.length === 0"><td colspan="4" class="muted empty">No hay excepciones registradas.</td></tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </template>
  </section>
</template>

<style scoped>
.calendar-panel { padding: 24px; }
.setting-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
h3 { font-size: 16px; margin: 0 0 7px; }
h4 { font-size: 14px; margin: 0 0 12px; }
p { font-size: 12px; line-height: 1.6; margin: 0; color: #aab4c3; }
.warning { background: #473c2c; color: #f4c781; border: 1px solid #69553b; padding: 12px; border-radius: 8px; margin-bottom: 16px; }
.error, .success { border-radius: 8px; padding: 11px 12px; margin-bottom: 12px; }
.error { background: #4c3036; color: #ffc0ba; }
.success { background: #29443d; color: #8bdfc1; }
.calendar-source { margin-bottom: 14px; }
.settings-form { display: flex; flex-direction: column; align-items: flex-start; gap: 15px; }
.field { display: flex; flex-direction: column; gap: 7px; width: 100%; }
label, legend { font-size: 12px; color: #cbd5e1; }
input:not([type='checkbox']), select { min-width: 0; width: 100%; background: #1e232a; border: 1px solid #425065; color: #f1f5f9; border-radius: 8px; padding: 10px; font-size: 12px; }
.weekdays { border: 1px solid #343d49; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 14px; padding: 14px; width: 100%; }
.weekdays legend { padding: 0 6px; }
.check-day { display: inline-flex; gap: 7px; align-items: center; }
.check-day input { accent-color: #4f8cff; }
.primary { background: #4f8cff; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font-weight: 600; font-size: 12px; }
.small-button { border: 1px solid #405470; background: #303d51; color: #9ec0ff; padding: 8px 11px; border-radius: 7px; font-size: 11px; }
.danger { background: #473238; border-color: #67464e; color: #f0a099; }
.exceptions { border-top: 1px solid #343d49; margin-top: 25px; padding-top: 20px; }
.exception-form { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 13px; margin-bottom: 20px; }
.description, .form-actions { grid-column: 1/-1; }
.form-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.scroll-table { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; text-align: left; min-width: 540px; }
th { background: #20262f; color: #9ba9ba; font-size: 11px; padding: 12px; }
td { color: #cbd5e1; font-size: 12px; padding: 12px; border-top: 1px solid #343d49; }
.inline-actions { display: flex; gap: 8px; }
.muted { color: #aab4c3; }
.empty { text-align: center; }
@media(max-width:700px) { .calendar-panel { padding: 16px; } .setting-header { align-items: flex-start; flex-direction: column; } .exception-form { grid-template-columns: 1fr; } .description, .form-actions { grid-column: auto; } }
</style>
