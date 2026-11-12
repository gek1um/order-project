<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import type { Task } from '../../services/tasks'
import {
  dependencyService,
  type DependencyType,
  type TaskDependency,
} from '../../services/scheduling'

const props = defineProps<{ projectId: number; tasks: Task[] }>()
const dependencies = ref<TaskDependency[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const editingId = ref<number | null>(null)
const predecessor = ref<number | null>(null)
const successor = ref<number | null>(null)
const dependencyType = ref<DependencyType>('FS')
const lagDays = ref(0)
const deletingId = ref<number | null>(null)
let requestVersion = 0

const taskNames = computed(() => new Map(props.tasks.map(task => [task.id, task.name])))
const hasTasks = computed(() => props.tasks.length >= 2)
const canSubmit = computed(() =>
  !saving.value && hasTasks.value &&
  predecessor.value !== null && successor.value !== null &&
  predecessor.value !== successor.value &&
  Number.isInteger(lagDays.value) &&
  props.tasks.some(t => t.id === predecessor.value) &&
  props.tasks.some(t => t.id === successor.value),
)
const types: { value: DependencyType; label: string }[] = [
  { value: 'FS', label: 'FS · Fin → Inicio' },
  { value: 'SS', label: 'SS · Inicio → Inicio' },
  { value: 'FF', label: 'FF · Fin → Fin' },
  { value: 'SF', label: 'SF · Inicio → Fin' },
]

function getError(err: unknown): string {
  if (!isAxiosError(err)) return 'No fue posible completar la operación.'
  if (!err.response) return 'No se pudo conectar con Django.'
  const data: unknown = err.response.data
  if (data && typeof data === 'object') {
    return Object.entries(data).map(([key, value]) =>
      `${key}: ${Array.isArray(value) ? value.map(String).join(', ') : String(value)}`,
    ).join(' | ')
  }
  return `Error HTTP ${err.response.status}.`
}

async function load() {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  try {
    const result = await dependencyService.list({ project: props.projectId })
    if (version === requestVersion) dependencies.value = result
  } catch (err) {
    if (version === requestVersion) error.value = getError(err)
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  predecessor.value = null
  successor.value = null
  dependencyType.value = 'FS'
  lagDays.value = 0
}

function edit(item: TaskDependency) {
  editingId.value = item.id
  predecessor.value = item.predecessor
  successor.value = item.successor
  dependencyType.value = item.dependency_type
  lagDays.value = item.lag_days
  notice.value = ''
  error.value = ''
}

async function save() {
  if (!canSubmit.value || predecessor.value === null || successor.value === null) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const payload = {
      predecessor: predecessor.value,
      successor: successor.value,
      dependency_type: dependencyType.value,
      lag_days: lagDays.value,
    }
    if (editingId.value === null) {
      await dependencyService.create(payload)
      notice.value = 'Dependencia creada correctamente.'
    } else {
      await dependencyService.update(editingId.value, payload)
      notice.value = 'Dependencia actualizada correctamente.'
    }
    resetForm()
    await load()
  } catch (err) {
    error.value = getError(err)
  } finally {
    saving.value = false
  }
}

async function remove(item: TaskDependency) {
  if (deletingId.value !== null) return
  if (!window.confirm(`¿Eliminar la dependencia entre «${taskNames.value.get(item.predecessor) ?? item.predecessor}» y «${taskNames.value.get(item.successor) ?? item.successor}»?`)) return
  deletingId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await dependencyService.remove(item.id)
    if (editingId.value === item.id) resetForm()
    notice.value = 'Dependencia eliminada correctamente.'
    await load()
  } catch (err) {
    error.value = getError(err)
  } finally {
    deletingId.value = null
  }
}

watch(() => props.projectId, () => { ++requestVersion; dependencies.value = []; resetForm(); void load() })
onMounted(() => { void load() })
</script>

<template>
  <section class="setting-panel">
    <header class="setting-header">
      <div>
        <h3>Dependencias entre actividades</h3>
        <p>Configura las relaciones FS, SS, FF o SF y sus desfases laborales.</p>
      </div>
      <button class="small-button" type="button" :disabled="loading" @click="load">Actualizar</button>
    </header>

    <p class="warning">Importante: crear, modificar o eliminar una dependencia todavía no recalcula automáticamente las fechas guardadas. Revisa el cronograma y utiliza «Reprogramar» para aplicar cambios necesarios.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>

    <form class="setting-form" @submit.prevent="save">
      <div class="field">
        <label for="dep-predecessor">Predecesora</label>
        <select id="dep-predecessor" v-model.number="predecessor" required>
          <option :value="null" disabled>Selecciona una actividad</option>
          <option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.name }} (#{{ task.id }})</option>
        </select>
      </div>
      <div class="field">
        <label for="dep-successor">Sucesora</label>
        <select id="dep-successor" v-model.number="successor" required>
          <option :value="null" disabled>Selecciona una actividad</option>
          <option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.name }} (#{{ task.id }})</option>
        </select>
      </div>
      <div class="field">
        <label for="dep-type">Relación</label>
        <select id="dep-type" v-model="dependencyType">
          <option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option>
        </select>
      </div>
      <div class="field">
        <label for="dep-lag">Desfase (días laborales)</label>
        <input id="dep-lag" v-model.number="lagDays" type="number" step="1" required />
      </div>
      <div class="form-actions">
        <button class="primary" type="submit" :disabled="!canSubmit">{{ saving ? 'Guardando…' : editingId === null ? 'Agregar dependencia' : 'Guardar dependencia' }}</button>
        <button v-if="editingId !== null" class="small-button" type="button" :disabled="saving" @click="resetForm">Cancelar edición</button>
      </div>
    </form>

    <p v-if="!hasTasks" class="muted">Se necesitan al menos dos actividades para establecer una relación.</p>
    <p v-if="loading" class="muted">Cargando dependencias…</p>
    <div v-else class="scroll-table">
      <table>
        <thead><tr><th>Predecesora</th><th>Relación</th><th>Sucesora</th><th>Desfase</th><th>Acciones</th></tr></thead>
        <tbody>
          <tr v-for="item in dependencies" :key="item.id">
            <td>{{ taskNames.get(item.predecessor) ?? item.predecessor_name }}</td>
            <td><span class="chip">{{ item.dependency_type }}</span></td>
            <td>{{ taskNames.get(item.successor) ?? item.successor_name }}</td>
            <td>{{ item.lag_days > 0 ? '+' : '' }}{{ item.lag_days }} días</td>
            <td class="inline-actions">
              <button type="button" class="small-button" :disabled="saving || deletingId !== null" @click="edit(item)">Editar</button>
              <button type="button" class="small-button danger" :disabled="saving || deletingId !== null" @click="remove(item)">Eliminar</button>
            </td>
          </tr>
          <tr v-if="dependencies.length === 0"><td colspan="5" class="muted empty">Sin dependencias registradas.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.setting-panel { padding: 24px; }
.setting-header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 18px; }
h3 { font-size: 16px; margin: 0 0 7px; }
p { font-size: 12px; line-height: 1.6; margin: 0; color: #aab4c3; }
.warning { background: #473c2c; color: #f4c781; border: 1px solid #69553b; padding: 12px; border-radius: 8px; margin-bottom: 16px; }
.error, .success { border-radius: 8px; padding: 11px 12px; margin-bottom: 12px; }
.error { color: #ffc0ba; background: #4c3036; }
.success { color: #8bdfc1; background: #29443d; }
.setting-form { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; margin-bottom: 24px; }
.field { display: flex; flex-direction: column; gap: 7px; }
label { font-size: 12px; color: #cbd5e1; }
input, select { min-width: 0; background: #1e232a; border: 1px solid #425065; color: #f1f5f9; border-radius: 8px; padding: 10px; font-size: 12px; }
.form-actions { grid-column: 1/-1; display: flex; gap: 10px; flex-wrap: wrap; }
.primary { background: #4f8cff; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font-weight: 600; font-size: 12px; }
.small-button { border: 1px solid #405470; background: #303d51; color: #9ec0ff; padding: 8px 11px; border-radius: 7px; font-size: 11px; }
.danger { background: #473238; border-color: #67464e; color: #f0a099; }
.muted { color: #aab4c3; }
.scroll-table { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; text-align: left; min-width: 580px; }
th { background: #20262f; color: #9ba9ba; font-size: 11px; padding: 12px; }
td { color: #cbd5e1; font-size: 12px; padding: 12px; border-top: 1px solid #343d49; }
.inline-actions { display: flex; gap: 8px; }
.chip { color: #8fb6ff; background: #273c5a; border-radius: 5px; padding: 5px 8px; }
.empty { text-align: center; }
@media(max-width: 700px) { .setting-panel { padding: 16px; } .setting-form { grid-template-columns: 1fr; } .setting-header { align-items: flex-start; flex-direction: column; } }
</style>
