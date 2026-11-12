<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ProjectSchedule } from '../../services/scheduling'
import type { Milestone } from '../../services/milestones'
import { isOverdue, isFinishedLate, localTodayISO, overdueDays, numericProgress } from '../../utils/scheduleHealth'

/**
 * Fase 4.3: dependencias FS, SS, FF y SF en la línea planificada.
 * Esta vista no realiza escrituras al backend. Emite una selección para abrir el modal de simulación.
 * Fechas interpretadas en UTC para evitar diferencias por zona horaria / DST.
 */
const props = defineProps<{ schedule: ProjectSchedule; milestones: Milestone[] }>()
const emit = defineEmits<{ 'select-task': [taskId: number] }>()

type Scale = 'day' | 'week'
const scale = ref<Scale>('day')
const showDependencies = ref(true)
const LABEL_WIDTH = 310
const ROW_HEIGHT = 64
const MS_DAY = 86_400_000
const todayISO = localTodayISO()

function parseDate(value: string): number {
  const [year, month, day] = value.split('-').map(Number)
  return Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)
}
function daysBetween(a: number, b: number): number {
  return Math.round((b - a) / MS_DAY)
}
function dateAt(time: number): string {
  return new Date(time).toISOString().slice(0, 10)
}
function shortDate(value: string): string {
  const [y, m, d] = value.split('-')
  return `${d ?? ''}/${m ?? ''}/${y ?? ''}`
}
const tasks = computed(() => [...props.schedule.tasks].sort(
  (a, b) => (a.position - b.position) || (a.id - b.id),
))
const limits = computed(() => {
  const dates = [props.schedule.project.start_date, props.schedule.project.end_date]
  if (tasks.value.some(task => isOverdue(task, todayISO))) dates.push(todayISO)
  for (const milestone of props.milestones) {
    dates.push(milestone.due_date)
    if (milestone.completed_at) dates.push(milestone.completed_at)
  }
  for (const task of tasks.value) {
    dates.push(task.start_date, task.end_date)
    if (task.actual_start_date) dates.push(task.actual_start_date)
    if (task.actual_end_date) dates.push(task.actual_end_date)
  }
  const start = Math.min(...dates.map(parseDate))
  const end = Math.max(...dates.map(parseDate))
  // Alineación con lunes/domingo: facilita la lectura de semanas.
  const firstWeekday = (new Date(start).getUTCDay() + 6) % 7
  const lastWeekday = (new Date(end).getUTCDay() + 6) % 7
  return {
    first: start - firstWeekday * MS_DAY,
    last: end + (6 - lastWeekday) * MS_DAY,
  }
})
const totalDays = computed(() => daysBetween(limits.value.first, limits.value.last) + 1)
const effectiveScale = computed<Scale>(() => totalDays.value > 550 ? 'week' : scale.value)
const cellWidth = computed(() => effectiveScale.value === 'day' ? 36 : 84)
const columnCount = computed(() => effectiveScale.value === 'day'
  ? totalDays.value : Math.ceil(totalDays.value / 7))
const timelineWidth = computed(() => columnCount.value * cellWidth.value)
const calendarColumns = computed(() => Array.from({ length: columnCount.value }, (_, index) => {
  const when = limits.value.first + index * (effectiveScale.value === 'day' ? 1 : 7) * MS_DAY
  const date = new Date(when)
  const weekday = date.getUTCDay()
  const dayLabel = date.getUTCDate().toString().padStart(2, '0')
  const monthLabel = new Intl.DateTimeFormat('es-CL', { month: 'short', timeZone: 'UTC' }).format(date)
  return {
    key: index,
    label: effectiveScale.value === 'day' ? dayLabel : `${dayLabel} ${monthLabel}`,
    subtitle: effectiveScale.value === 'day'
      ? ['D', 'L', 'M', 'M', 'J', 'V', 'S'][weekday] : `Sem. ${index + 1}`,
    weekend: effectiveScale.value === 'day' && (weekday === 0 || weekday === 6),
    firstOfMonth: date.getUTCDate() === 1 || index === 0,
    title: dateAt(when),
  }
}))
const unitDays = computed(() => effectiveScale.value === 'day' ? 1 : 7)
const today = new Date()
const todayUtc = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
const todayX = computed(() => {
  const distance = daysBetween(limits.value.first, todayUtc)
  return distance >= 0 && distance < totalDays.value
    ? (distance / unitDays.value) * cellWidth.value : null
})
function milestoneX(date: string): string {
  const offset = daysBetween(limits.value.first, parseDate(date))
  return `${((offset + 0.5) / unitDays.value) * cellWidth.value}px`
}
function geometry(task: ProjectSchedule['tasks'][number]): { left: string; width: string } {
  const start = daysBetween(limits.value.first, parseDate(task.start_date))
  const duration = Math.max(1, daysBetween(parseDate(task.start_date), parseDate(task.end_date)) + 1)
  const left = (start / unitDays.value) * cellWidth.value
  const width = (duration / unitDays.value) * cellWidth.value
  return { left: `${left + 3}px`, width: `${Math.max(5, width - 6)}px` }
}
/**
 * Conectores entre hitos temporales de las barras planificadas.
 * FS: fin predecesora → inicio sucesora
 * SS: inicio predecesora → inicio sucesora
 * FF: fin predecesora → fin sucesora
 * SF: inicio predecesora → fin sucesora
 * Un desfase es metadata de la dependencia: no desplazamos las flechas
 * artificialmente porque las barras ya incorporan las fechas efectivas.
 */
type DependencyKind = 'FS' | 'SS' | 'FF' | 'SF'
const DEPENDENCY_COLORS: Record<DependencyKind, string> = {
  FS: '#a8b7d2',
  SS: '#67c3df',
  FF: '#d6a9e8',
  SF: '#e6b66a',
}
function endpointX(task: ProjectSchedule['tasks'][number], edge: 'start' | 'finish'): number {
  const start = daysBetween(limits.value.first, parseDate(task.start_date))
  const finishExclusive = daysBetween(limits.value.first, parseDate(task.end_date)) + 1
  const days = edge === 'start' ? start : finishExclusive
  const pixel = (days / unitDays.value) * cellWidth.value
  return pixel + (edge === 'start' ? 3 : -3)
}
function dependencyPath(sourceX: number, sourceY: number, targetX: number, targetY: number, index: number): string {
  // Desplazamos las rutas verticales ligeramente para reducir superposiciones.
  const laneShift = (index % 5) * 7
  if (targetX >= sourceX + 36) {
    const columnX = Math.min(targetX - 12, sourceX + 14 + laneShift)
    return `M ${sourceX} ${sourceY} H ${columnX} V ${targetY} H ${targetX}`
  }
  // Desfases negativos o tareas solapadas pueden invertir la dirección horizontal.
  const outerX = Math.min(timelineWidth.value - 3, Math.max(sourceX, targetX) + 16 + laneShift)
  return `M ${sourceX} ${sourceY} H ${outerX} V ${targetY} H ${targetX}`
}
const connectors = computed(() => {
  const byId = new Map(tasks.value.map((task, rowIndex) => [task.id, { task, rowIndex }]))
  return props.schedule.dependencies.flatMap((dependency, index) => {
    const predecessor = byId.get(dependency.predecessor_id)
    const successor = byId.get(dependency.successor_id)
    if (!predecessor || !successor) return []
    const kind = dependency.dependency_type as DependencyKind
    if (!(kind in DEPENDENCY_COLORS)) return []
    const sourceEdge = kind === 'FS' || kind === 'FF' ? 'finish' : 'start'
    const targetEdge = kind === 'FS' || kind === 'SS' ? 'start' : 'finish'
    const sourceX = endpointX(predecessor.task, sourceEdge)
    const targetX = endpointX(successor.task, targetEdge)
    const sourceY = predecessor.rowIndex * ROW_HEIGHT + 18
    const targetY = successor.rowIndex * ROW_HEIGHT + 18
    const lag = dependency.lag_days
    return [{
      id: dependency.id,
      kind,
      color: DEPENDENCY_COLORS[kind],
      path: dependencyPath(sourceX, sourceY, targetX, targetY, index),
      description: `${predecessor.task.name} → ${successor.task.name} (${kind}, desfase ${lag > 0 ? '+' : ''}${lag} días laborables)`,
    }]
  })
})
const missingDependencyCount = computed(() => props.schedule.dependencies.length - connectors.value.length)

function actualGeometry(task: ProjectSchedule['tasks'][number]): { left: string; width: string } | null {
  if (!task.actual_start_date || !task.actual_end_date) return null
  const start = daysBetween(limits.value.first, parseDate(task.actual_start_date))
  const duration = Math.max(1, daysBetween(parseDate(task.actual_start_date), parseDate(task.actual_end_date)) + 1)
  return {
    left: `${(start / unitDays.value) * cellWidth.value + 3}px`,
    width: `${Math.max(5, (duration / unitDays.value) * cellWidth.value - 6)}px`,
  }
}
function actualStartX(task: ProjectSchedule['tasks'][number]): string {
  if (!task.actual_start_date) return '0px'
  return `${(daysBetween(limits.value.first, parseDate(task.actual_start_date)) / unitDays.value) * cellWidth.value + 3}px`
}
function finishDeviation(task: ProjectSchedule['tasks'][number]): number | null {
  if (!task.actual_end_date) return null
  return daysBetween(parseDate(task.end_date), parseDate(task.actual_end_date))
}
function deviationLabel(task: ProjectSchedule['tasks'][number]): string {
  const days = finishDeviation(task)
  if (days === null) return 'Sin término real'
  if (days === 0) return 'A tiempo'
  return days > 0 ? `+${days} d` : `${days} d`
}
function progress(task: ProjectSchedule['tasks'][number]): number {
  return numericProgress(task)
}
function overdueGeometry(task: ProjectSchedule['tasks'][number]): { left: string; width: string } | null {
  if (!isOverdue(task, todayISO)) return null
  const from = daysBetween(limits.value.first, parseDate(task.end_date)) + 1
  const until = daysBetween(limits.value.first, parseDate(todayISO)) + 1
  return {
    left: `${(from / unitDays.value) * cellWidth.value}px`,
    width: `${Math.max(2, ((until - from) / unitDays.value) * cellWidth.value)}px`,
  }
}
function taskFlag(task: ProjectSchedule['tasks'][number]): string {
  if (isOverdue(task, todayISO)) return `Atrasada ${overdueDays(task, todayISO)} d`
  if (isFinishedLate(task)) return 'Terminó tarde'
  return ''
}
function stateClass(task: ProjectSchedule['tasks'][number]): string {
  return task.status === 'COMPLETED' ? 'completed'
    : task.status === 'IN_PROGRESS' ? 'active'
    : task.status === 'CANCELLED' ? 'cancelled' : 'pending'
}
const rulerBackground = computed(() => ({
  backgroundImage: 'linear-gradient(to right, var(--color-border) 1px, transparent 1px)',
  backgroundSize: `${cellWidth.value}px 100%`,
}))
</script>

<template>
  <div class="gantt">
    <div class="gantt-toolbar">
      <div>
        <h3>Carta Gantt · Progreso y retrasos</h3>
        <p>Planificación, ejecución real, progreso y retrasos respecto a hoy. Las distancias representan días calendario.</p>
      </div>
      <div class="gantt-controls">
        <label class="dependency-toggle">
          <input v-model="showDependencies" type="checkbox" :disabled="connectors.length === 0" />
          Mostrar dependencias ({{ connectors.length }})
        </label>
        <label class="scale-picker">
          Escala
          <select v-model="scale" class="form-control" :disabled="totalDays > 550">
            <option value="day">Días</option>
            <option value="week">Semanas</option>
          </select>
        </label>
      </div>
    </div>

    <p v-if="totalDays > 550" class="info-note">Este proyecto supera los 550 días: se utiliza la escala semanal para mantener una visualización fluida.</p>
    <p v-if="tasks.length === 0 && milestones.length === 0" class="empty-state">El proyecto aún no tiene actividades ni hitos para mostrar.</p>
    <template v-else>
      <div class="gantt-scroll" tabindex="0" role="region" aria-label="Carta Gantt desplazable horizontalmente">
        <div class="gantt-inner" :style="{ width: `${LABEL_WIDTH + timelineWidth}px` }">
          <div class="gantt-header">
            <div class="activity-heading" :style="{ width: `${LABEL_WIDTH}px` }">Actividad</div>
            <div class="ruler" :style="{ width: `${timelineWidth}px` }">
              <div
                v-for="column in calendarColumns" :key="column.key"
                class="ruler-cell" :class="{ weekend: column.weekend, month: column.firstOfMonth }"
                :style="{ width: `${cellWidth}px` }" :title="column.title"
              >
                <strong>{{ column.label }}</strong>
                <small>{{ column.subtitle }}</small>
              </div>
            </div>
          </div>
          <svg
            v-if="showDependencies && connectors.length > 0"
            class="dependency-overlay"
            :style="{ left: `${LABEL_WIDTH}px`, top: `${55}px` }"
            :width="timelineWidth"
            :height="tasks.length * ROW_HEIGHT"
            :viewBox="`0 0 ${timelineWidth} ${tasks.length * ROW_HEIGHT}`"
            aria-hidden="true"
          >
            <defs>
              <marker
                v-for="(color, kind) in DEPENDENCY_COLORS" :id="`gantt-arrow-${kind}`" :key="kind"
                markerWidth="8" markerHeight="8" refX="6.5" refY="3" orient="auto" markerUnits="userSpaceOnUse"
              >
                <path d="M 0 0 L 7 3 L 0 6 Z" :fill="color" />
              </marker>
            </defs>
            <path
              v-for="connector in connectors" :key="connector.id"
              class="dependency-line" :d="connector.path" :stroke="connector.color"
              :marker-end="`url(#gantt-arrow-${connector.kind})`"
            />
          </svg>
          <div v-for="task in tasks" :key="task.id" class="gantt-row" :class="{ overdue: isOverdue(task, todayISO), late: isFinishedLate(task) }" :style="{ height: `${ROW_HEIGHT}px` }">
            <div class="activity-name" :style="{ width: `${LABEL_WIDTH}px` }" :title="task.name">
              <span class="activity-index">{{ task.position }}</span>
              <span class="activity-text">{{ task.name }}</span>
              <span class="progress-number" :title="taskFlag(task) || `Avance: ${progress(task)}%`">{{ progress(task) }}%<span v-if="taskFlag(task)" class="task-warning-icon" aria-label="Actividad con retraso"> !</span></span>
              <button class="reprogram-button" type="button" :title="`Abrir reprogramación de ${task.name}`" @click="emit('select-task', task.id)">Reprogramar</button>
            </div>
            <div class="track" :style="[{ width: `${timelineWidth}px` }, rulerBackground]">
              <div v-if="overdueGeometry(task)" class="overdue-extension" :style="overdueGeometry(task) || undefined" :title="`Atrasada ${overdueDays(task, todayISO)} días calendario al ${shortDate(todayISO)}`"></div>
              <div v-if="todayX !== null" class="today-line" :style="{ left: `${todayX}px` }" aria-hidden="true"></div>
              <button
                type="button"
                class="task-bar planned interactive-bar" :class="stateClass(task)" :style="geometry(task)"
                @click="emit('select-task', task.id)"
                :title="`Planificado: ${shortDate(task.start_date)} – ${shortDate(task.end_date)} · avance ${progress(task)}%${taskFlag(task) ? ` · ${taskFlag(task)}` : ''}`"
                :aria-label="`${task.name}, planificado del ${shortDate(task.start_date)} al ${shortDate(task.end_date)}, avance ${progress(task)}%`"
              >
                <div class="task-progress" :style="{ width: `${progress(task)}%` }"></div>
              </button>
              <div
                v-if="actualGeometry(task)"
                class="task-bar actual"
                :style="actualGeometry(task) || undefined"
                :title="`Real: ${shortDate(task.actual_start_date || '')} – ${shortDate(task.actual_end_date || '')} · ${deviationLabel(task)} respecto al término planificado`"
                :aria-label="`${task.name}, ejecución real del ${shortDate(task.actual_start_date || '')} al ${shortDate(task.actual_end_date || '')}; ${deviationLabel(task)}`"
              ></div>
              <div
                v-else-if="task.actual_start_date"
                class="actual-start-marker"
                :style="{ left: actualStartX(task) }"
                :title="`Inicio real: ${shortDate(task.actual_start_date)} · sin término real registrado`"
                :aria-label="`${task.name}, inicio real ${shortDate(task.actual_start_date)}, sin término real`"
              ></div>
            </div>
          </div>
          <div v-for="milestone in milestones" :key="`milestone-${milestone.id}`" class="gantt-row milestone-row" :style="{ height: `${ROW_HEIGHT}px` }">
            <div class="activity-name" :style="{ width: `${LABEL_WIDTH}px` }" :title="milestone.name">
              <span class="milestone-diamond-label">◆</span>
              <span class="activity-text">{{ milestone.name }}</span>
              <span class="milestone-status" :class="{ complete: milestone.status === 'COMPLETED' }">{{ milestone.status === 'COMPLETED' ? 'Cumplido' : 'Pendiente' }}</span>
            </div>
            <div class="track" :style="[{ width: `${timelineWidth}px` }, rulerBackground]">
              <div v-if="todayX !== null" class="today-line" :style="{ left: `${todayX}px` }" aria-hidden="true"></div>
              <span
                class="milestone-diamond" :class="{ complete: milestone.status === 'COMPLETED' }"
                :style="{ left: milestoneX(milestone.due_date) }"
                :title="`${milestone.name} · ${shortDate(milestone.due_date)} · ${milestone.responsible} · ${milestone.status === 'COMPLETED' ? 'Cumplido' : 'Pendiente'}`"
                :aria-label="`Hito ${milestone.name} previsto el ${shortDate(milestone.due_date)}`"
              >◆</span>
              <span v-if="milestone.completed_at" class="milestone-real-date" :style="{ left: milestoneX(milestone.completed_at) }" :title="`Cumplido el ${shortDate(milestone.completed_at)}`">●</span>
            </div>
          </div>
        </div>
      </div>
      <p v-if="missingDependencyCount > 0" class="info-note" role="status">
        {{ missingDependencyCount }} dependencia(s) no pudieron representarse porque sus actividades o tipos no están disponibles en este cronograma.
      </p>
      <div class="gantt-legend">
        <span><i class="legend-swatch planned-legend"></i>Planificación vigente (barra superior)</span>
        <span><i class="milestone-diamond-legend">◆</i> Hito (rombo)</span>
        <span><i class="legend-swatch real-legend"></i>Ejecución real finalizada (barra inferior)</span>
        <span><i class="legend-start"></i>Inicio real sin término registrado</span>
        <span><i class="legend-today"></i>Hoy (si está dentro del período)</span>
        <span><i class="legend-overdue"></i>Período atrasado sin término real</span>
        <span><i class="legend-late"></i>Término real posterior al planificado</span>
        <span v-for="(color, kind) in DEPENDENCY_COLORS" :key="kind">
          <i class="legend-dependency" :style="{ borderColor: color }"></i>{{ kind }}
        </span>
      </div>
      <p class="info-note">Una tarea está atrasada cuando su término planificado ya pasó y no consta terminada, cancelada ni con término real. Una tarea finalizada tarde tiene término real posterior al planificado. El avance medio no pondera la duración ni el costo. Los hitos son registros independientes de las actividades y no participan en las dependencias FS/SS/FF/SF.</p>
      <p class="info-note">Las diferencias entre fechas son días calendario, no días laborables. El término real solo se representa cuando fue registrado. Esta comparación usa la planificación vigente, no una línea base histórica.</p>
    </template>
  </div>
</template>

<style scoped>
.gantt { width: 100%; min-width: 0; }
.gantt-toolbar { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 18px; }
.gantt-toolbar h3 { font-size: 15px; margin: 0 0 6px; color: var(--color-text); }
.gantt-toolbar p, .info-note { color: var(--color-muted); font-size: 12px; line-height: 1.6; margin: 0; }
.gantt-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; }
.dependency-toggle { display: flex; align-items: center; gap: 7px; color: var(--color-muted); font-size: 12px; cursor: pointer; white-space: nowrap; }
.dependency-toggle input { accent-color: #4f8cff; }
.dependency-toggle:has(input:disabled) { opacity: .55; cursor: default; }
.scale-picker { display: flex; align-items: center; gap: 10px; color: var(--color-muted); font-size: 12px; white-space: nowrap; }
.scale-picker select { min-width: 122px; }
.gantt-scroll { width: 100%; max-width: 100%; overflow-x: auto; overflow-y: hidden; border: 1px solid var(--color-border); border-radius: 9px; }
.gantt-scroll:focus { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.gantt-inner { min-width: 100%; position: relative; }
.gantt-header, .gantt-row { display: flex; }
.gantt-header { height: 55px; background: #202732; position: sticky; top: 0; z-index: 6; }
.activity-heading, .activity-name { position: sticky; left: 0; flex: none; width: 310px; box-sizing: border-box; border-right: 1px solid var(--color-border); background: #252b34; z-index: 2; }
.activity-heading { display: flex; align-items: center; padding: 0 14px; font-size: 12px; font-weight: 600; z-index: 7; }
.ruler { display: flex; flex: none; }
.ruler-cell { display: flex; flex-direction: column; justify-content: center; align-items: center; flex: none; border-right: 1px solid #3a4554; color: #cbd5e1; font-size: 11px; line-height: 1.4; }
.ruler-cell small { color: var(--color-muted); font-size: 10px; }
.ruler-cell.weekend { background: #303540; }
.ruler-cell.month { border-left: 2px solid #7183a0; }
.gantt-row { border-top: 1px solid var(--color-border); }
.gantt-row.overdue .activity-name { border-left: 3px solid #e78c76; }
.gantt-row.late:not(.overdue) .activity-name { border-left: 3px solid #d1a2ea; }
.task-warning-icon { color: #f6a38a; font-weight: 800; }
.overdue-extension { position: absolute; top: 10px; height: 15px; background: repeating-linear-gradient(135deg, rgba(231,140,118,.48) 0 5px, transparent 5px 10px); outline: 1px dashed #e78c76; z-index: 1; pointer-events: auto; }
.legend-overdue { width: 16px; height: 9px; display: inline-block; border: 1px dashed #e78c76; background: rgba(231,140,118,.32); }
.legend-late { height: 12px; display: inline-block; border-left: 3px solid #d1a2ea; }
.activity-name { display: flex; align-items: center; gap: 8px; padding: 0 10px; font-size: 12px; z-index: 5; }
.activity-index { color: #8ca8cc; min-width: 20px; font-variant-numeric: tabular-nums; }
.activity-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.progress-number { color: var(--color-muted); font-size: 10px; flex: none; }
.track { flex: none; position: relative; background-color: #222832; }
.dependency-overlay { position: absolute; z-index: 4; pointer-events: none; overflow: visible; }
.dependency-line { fill: none; stroke-width: 1.7; opacity: .95; stroke-linecap: round; stroke-linejoin: round; }
.legend-dependency { display: inline-block; width: 15px; border-top: 2px solid; }
.task-bar { position: absolute; top: 7px; height: 22px; overflow: hidden; border-radius: 5px; background: #4f8cff; border: 1px solid #8cb3ff; min-width: 5px; }
.task-bar.active { background: #4c7ca8; border-color: #80bbec; }
.task-bar.completed { background: #417e6b; border-color: #5cc8a1; }
.task-bar.cancelled { background: #665964; border-color: #9d8491; opacity: .75; }
.task-bar.actual { top: 36px; height: 17px; background: #dfb86b; border-color: #f2d49e; z-index: 2; }
.actual-start-marker { position: absolute; top: 34px; height: 20px; border-left: 3px solid #dfb86b; z-index: 2; }
.actual-start-marker::after { content: ''; position: absolute; width: 8px; height: 8px; background: #dfb86b; transform: rotate(45deg); left: -5px; top: -5px; }
.legend-swatch.planned-legend { background: #4f8cff; }
.legend-swatch.real-legend { background: #dfb86b; }
.legend-start { height: 12px; border-left: 3px solid #dfb86b; display: inline-block; }
.task-progress { height: 100%; background: rgba(255,255,255,.33); }
.today-line { position: absolute; z-index: 1; top: 0; bottom: 0; border-left: 2px dashed #f4b860; pointer-events: none; }
.gantt-legend { display: flex; flex-wrap: wrap; gap: 9px 17px; margin-top: 14px; }
.gantt-legend span { display: flex; gap: 6px; align-items: center; font-size: 11px; color: var(--color-muted); }
.legend-swatch { display: inline-block; width: 12px; height: 9px; border-radius: 2px; background: #4f8cff; }
.legend-swatch.active { background: #4c7ca8; }.legend-swatch.completed { background: #417e6b; }.legend-swatch.cancelled { background: #665964; }
.legend-today { display: inline-block; height: 14px; border-left: 2px dashed #f4b860; }
.info-note { margin-top: 12px; }.empty-state { color: var(--color-muted); font-size: 13px; }
@media (max-width: 720px) { .gantt-toolbar { align-items: start; flex-direction: column; } .gantt-controls { align-items: flex-start; flex-direction: column; } }

.reprogram-button { background: transparent; border: 1px solid #425c80; border-radius: 5px; color: #a9c5ff; font-size: 10px; padding: 5px 6px; cursor: pointer; flex: none; }
.reprogram-button:hover, .reprogram-button:focus-visible { background: #303d51; outline: 1px solid #4f8cff; }
.interactive-bar { cursor: pointer; padding: 0; z-index: 3; }
.interactive-bar:hover, .interactive-bar:focus-visible { filter: brightness(1.18); outline: 2px solid #d6e6ff; outline-offset: 1px; }
.milestone-diamond { position:absolute; top:13px; transform:translateX(-50%); font-size:28px; color:#dfb86b; text-shadow:0 0 5px #171c23; line-height:1; z-index:3; }
.milestone-diamond.complete { color:#65d1ad; }
.milestone-real-date { position:absolute; top:40px; transform:translateX(-50%); font-size:17px; line-height:1; color:#65d1ad; }
.milestone-diamond-label, .milestone-diamond-legend { color:#dfb86b; font-size:15px; }
.milestone-status { font-size:10px; color:#dfb86b; white-space:nowrap; }
.milestone-status.complete { color:#65d1ad; }
</style>
