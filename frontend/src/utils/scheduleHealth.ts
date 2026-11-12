import type { ScheduleTask } from '../services/scheduling'

/** Indicadores informativos. No modifican fechas ni reemplazan las reglas de Django. */
const MS_PER_DAY = 86_400_000

export function localTodayISO(now: Date = new Date()): string {
  const year = String(now.getFullYear())
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function utcDay(date: string): number {
  const [year, month, day] = date.split('-').map(Number)
  return Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1)
}

export function calendarDaysBetween(from: string, to: string): number {
  return Math.round((utcDay(to) - utcDay(from)) / MS_PER_DAY)
}

export function isOverdue(task: ScheduleTask, today: string): boolean {
  return task.status !== 'COMPLETED'
    && task.status !== 'CANCELLED'
    && !task.actual_end_date
    && task.end_date < today
}

export function overdueDays(task: ScheduleTask, today: string): number {
  return isOverdue(task, today) ? calendarDaysBetween(task.end_date, today) : 0
}

export function isFinishedLate(task: ScheduleTask): boolean {
  return Boolean(task.actual_end_date && task.actual_end_date > task.end_date)
}

export function isFinishedOnTime(task: ScheduleTask): boolean {
  return Boolean(task.actual_end_date && task.actual_end_date <= task.end_date)
}

export function numericProgress(task: ScheduleTask): number {
  const value = Number(task.progress_percent)
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0
}

export function progressSummary(tasks: ScheduleTask[], today: string) {
  const considered = tasks.filter(task => task.status !== 'CANCELLED')
  const averageProgress = considered.length
    ? considered.reduce((sum, task) => sum + numericProgress(task), 0) / considered.length
    : 0
  return {
    overdue: tasks.filter(task => isOverdue(task, today)).length,
    finishedLate: tasks.filter(isFinishedLate).length,
    finishedOnTime: tasks.filter(isFinishedOnTime).length,
    averageProgress: Math.round(averageProgress),
  }
}
