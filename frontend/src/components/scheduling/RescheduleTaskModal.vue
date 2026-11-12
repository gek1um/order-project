<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import type { Task } from '../../services/tasks'
import { calendarService } from '../../services/calendars'
import {
  schedulingService,
  type ReschedulePayload,
  type ScheduleResult,
} from '../../services/scheduling'
import SchedulePreviewTable from './SchedulePreviewTable.vue'

const props = defineProps<{
  task: Task
  projectId: number
  projectStartDate: string
  projectEndDate: string
}>()

const emit = defineEmits<{
  close: []
  confirmed: [result: ScheduleResult]
}>()

const startDate = ref('')
const durationDays = ref<number | null>(null)
const preview = ref<ScheduleResult | null>(null)
const loadingDuration = ref(false)
const simulating = ref(false)
const confirming = ref(false)
const error = ref('')

// Invalida respuestas de simulaciones anteriores cuando cambia el formulario.
let previewRequestVersion = 0
let initializationVersion = 0

const locked = computed(() =>
  props.task.status !== 'PENDING' ||
  props.task.actual_start_date !== null ||
  props.task.actual_end_date !== null ||
  Number(props.task.progress_percent) > 0,
)

const busy = computed(() => loadingDuration.value || simulating.value || confirming.value)

const validInput = computed(() =>
  startDate.value !== '' &&
  startDate.value >= props.projectStartDate &&
  startDate.value <= props.projectEndDate &&
  durationDays.value !== null &&
  Number.isInteger(durationDays.value) &&
  durationDays.value >= 1 &&
  durationDays.value <= 36500,
)

function errorMessage(err: unknown): string {
  if (!isAxiosError(err)) return 'Ocurrió un error inesperado.'
  if (!err.response) return 'No se pudo conectar con el backend de Django.'
  const data: unknown = err.response.data
  if (data && typeof data === 'object') {
    const messages = Object.entries(data).map(([key, value]) => {
      const text = Array.isArray(value) ? value.map(String).join(', ') : String(value)
      return key === 'detail' ? text : `${key}: ${text}`
    })
    if (messages.length) return messages.join(' | ')
  }
  return `Error HTTP ${err.response.status}.`
}

watch(
  () => [props.task.id, props.projectId] as const,
  async () => {
    const version = ++initializationVersion
    ++previewRequestVersion
    preview.value = null
    error.value = ''
    startDate.value = props.task.start_date
    durationDays.value = props.task.estimated_duration_days
    loadingDuration.value = false

    if (durationDays.value !== null) return

    loadingDuration.value = true
    try {
      const calculation = await calendarService.calculate(props.projectId, {
        operation: 'count',
        start_date: props.task.start_date,
        end_date: props.task.end_date,
      })
      if (version !== initializationVersion) return
      durationDays.value = calculation.working_days ?? null
      if (!durationDays.value) {
        error.value = 'La duración no se pudo inferir. Introduce los días laborables manualmente.'
      }
    } catch (err) {
      if (version === initializationVersion) {
        error.value = `${errorMessage(err)} Introduce la duración manualmente.`
      }
    } finally {
      if (version === initializationVersion) loadingDuration.value = false
    }
  },
  { immediate: true },
)

watch([startDate, durationDays], () => {
  ++previewRequestVersion
  preview.value = null
  if (!simulating.value && !confirming.value) error.value = ''
})

function payload(): ReschedulePayload {
  return {
    start_date: startDate.value,
    duration_days: durationDays.value!,
  }
}

async function simulate() {
  if (busy.value || locked.value || !validInput.value) return
  const version = ++previewRequestVersion
  simulating.value = true
  preview.value = null
  error.value = ''
  try {
    const result = await schedulingService.preview(props.task.id, payload())
    if (version === previewRequestVersion) preview.value = result
  } catch (err) {
    if (version === previewRequestVersion) error.value = errorMessage(err)
  } finally {
    simulating.value = false
  }
}

async function confirm() {
  if (busy.value || locked.value || !validInput.value || !preview.value) return
  confirming.value = true
  error.value = ''
  try {
    // El servidor vuelve a calcular y validar al confirmar.
    const result = await schedulingService.reschedule(props.task.id, payload())
    emit('confirmed', result)
  } catch (err) {
    error.value = errorMessage(err)
    preview.value = null
  } finally {
    confirming.value = false
  }
}

function close() {
  if (!busy.value) emit('close')
}
</script>

<template>
  <div class="modal-backdrop" @click.self="close">
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="reschedule-title">
      <header class="modal-header">
        <div>
          <h2 id="reschedule-title">Reprogramar actividad</h2>
          <p class="muted">{{ task.name }}</p>
        </div>
        <button type="button" class="close-button" aria-label="Cerrar" :disabled="busy" @click="close">×</button>
      </header>

      <div class="current-schedule">
        <span>Inicio actual: <strong>{{ task.start_date }}</strong></span>
        <span>Término actual: <strong>{{ task.end_date }}</strong></span>
      </div>

      <p v-if="locked" class="warning" role="alert">
        Esta actividad registra ejecución, está completada o cancelada. La reprogramación está bloqueada.
      </p>

      <form @submit.prevent="simulate">
        <div class="form-grid">
          <div>
            <label for="reschedule-start">Nuevo inicio *</label>
            <input
              id="reschedule-start"
              v-model="startDate"
              type="date"
              :min="projectStartDate"
              :max="projectEndDate"
              :disabled="busy || locked"
              required
            />
          </div>
          <div>
            <label for="reschedule-duration">Duración (días laborables) *</label>
            <input
              id="reschedule-duration"
              v-model.number="durationDays"
              type="number"
              min="1"
              max="36500"
              step="1"
              :disabled="busy || locked"
              required
            />
          </div>
        </div>

        <p v-if="loadingDuration" class="muted">Calculando duración actual...</p>
        <div v-if="error" class="error" role="alert">{{ error }}</div>

        <SchedulePreviewTable v-if="preview" :result="preview" />

        <div class="actions">
          <button type="button" class="secondary" :disabled="busy" @click="close">Cancelar</button>
          <button type="submit" class="secondary" :disabled="busy || locked || !validInput">
            {{ simulating ? 'Simulando...' : 'Simular cambios' }}
          </button>
          <button
            type="button"
            class="primary"
            :disabled="busy || locked || !validInput || !preview || preview.updated_tasks === 0"
            @click="confirm"
          >
            {{ confirming ? 'Confirmando...' : 'Confirmar reprogramación' }}
          </button>
        </div>
      </form>
      <p class="muted footnote">La simulación no guarda cambios. Al confirmar, Django vuelve a validar el cronograma completo.</p>
    </section>
  </div>
</template>

<style scoped>
.modal-backdrop { position: fixed; inset: 0; z-index: 120; display: flex; align-items: center; justify-content: center; padding: 20px; background: rgba(9,13,19,.82); }
.modal { width: min(880px, 100%); max-height: 92vh; overflow-y: auto; padding: 26px; background: #252b34; border: 1px solid #343d49; border-radius: 12px; color: #f1f5f9; }
.modal-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 20px; }
.modal-header h2 { margin: 0 0 6px; font-size: 19px; }
.muted { margin: 6px 0; color: #aab4c3; font-size: 12px; line-height: 1.6; }
.close-button { background: transparent; border: 0; color: #aab4c3; font-size: 28px; }
.current-schedule { display: flex; flex-wrap: wrap; gap: 12px 24px; padding: 13px 16px; border: 1px solid #343d49; background: #20262f; border-radius: 8px; color: #cbd5e1; font-size: 12px; }
.current-schedule strong { color: #f1f5f9; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; margin-top: 22px; }
.form-grid label { display: block; margin-bottom: 8px; font-size: 12px; color: #aab4c3; }
.form-grid input { width: 100%; padding: 10px 12px; border: 1px solid #424d5e; border-radius: 8px; background: #20262f; color: #f1f5f9; color-scheme: dark; }
.error, .warning { padding: 12px 14px; margin-top: 15px; border-radius: 8px; font-size: 12px; line-height: 1.6; }
.error { background: #473238; color: #ffb4a8; }
.warning { background: #473d2a; color: #f4b860; }
.actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; padding-top: 20px; margin-top: 22px; border-top: 1px solid #343d49; }
.actions button { min-height: 39px; padding: 0 14px; border-radius: 8px; font-size: 12px; cursor: pointer; }
.actions button:disabled { opacity: .5; cursor: not-allowed; }
.secondary { background: #303d51; border: 1px solid #405470; color: #a9c5ff; }
.primary { background: #4f8cff; border: 1px solid #4f8cff; color: #111b2d; font-weight: 700; }
.footnote { margin-top: 14px; }
@media(max-width:650px) { .form-grid { grid-template-columns: 1fr; } .modal { padding: 18px; } }
</style>
