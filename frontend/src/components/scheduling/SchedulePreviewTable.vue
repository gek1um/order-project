<script setup lang="ts">
import type { ScheduleResult } from '../../services/scheduling'

defineProps<{
  result: ScheduleResult
}>()

function displayDate(value: string): string {
  const [year, month, day] = value.split('-')
  return year && month && day ? `${day}/${month}/${year}` : value
}
</script>

<template>
  <section class="preview" aria-label="Vista previa de reprogramación">
    <div class="summary">
      <strong>Resultado de la simulación</strong>
      <span>{{ result.updated_tasks }} modificada(s) de {{ result.affected_tasks }} evaluada(s)</span>
    </div>

    <p v-if="result.changes.length === 0" class="muted">
      No es necesario modificar ninguna fecha: el cronograma ya cumple esta programación.
    </p>

    <div v-else class="scroll">
      <table>
        <thead>
          <tr>
            <th>Actividad</th>
            <th>Inicio anterior</th>
            <th>Nuevo inicio</th>
            <th>Término anterior</th>
            <th>Nuevo término</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="change in result.changes" :key="change.task_id">
            <td>
              <strong>{{ change.name }}</strong>
              <span v-if="change.is_origin" class="origin">Origen</span>
            </td>
            <td>{{ displayDate(change.old_start_date) }}</td>
            <td :class="{ changed: change.old_start_date !== change.new_start_date }">
              {{ displayDate(change.new_start_date) }}
            </td>
            <td>{{ displayDate(change.old_end_date) }}</td>
            <td :class="{ changed: change.old_end_date !== change.new_end_date }">
              {{ displayDate(change.new_end_date) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.preview { margin-top: 20px; border: 1px solid #405470; border-radius: 10px; overflow: hidden; }
.summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 14px 16px; background: #263446; font-size: 12px; }
.summary span, .muted { color: #aab4c3; font-size: 12px; }
.muted { padding: 0 16px 12px; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 11px; white-space: nowrap; }
th { padding: 12px; background: #20262f; color: #aab4c3; }
td { padding: 12px; border-top: 1px solid #343d49; color: #d9e3ef; }
.changed { color: #5cc8a1; font-weight: 700; }
.origin { display: block; margin-top: 4px; color: #8fb6ff; font-size: 10px; }
</style>
