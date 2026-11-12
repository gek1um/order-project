import api from './api'

import type { TaskStatus } from './tasks'

import type { ProjectStatus } from './projects'

// ==================================================
// TIPOS DE DEPENDENCIAS
// ==================================================

export type DependencyType = 'FS' | 'SS' | 'FF' | 'SF'

export interface TaskDependency {
  id: number

  project_id: number
  project_code: string

  predecessor: number
  predecessor_name: string

  successor: number
  successor_name: string

  dependency_type: DependencyType
  dependency_type_display: string

  lag_days: number

  created_at: string
  updated_at: string
}

export interface DependencyPayload {
  predecessor: number
  successor: number
  dependency_type: DependencyType
  lag_days: number
}

export interface DependencyFilters {
  project?: number
  task?: number
  predecessor?: number
  successor?: number
}

// ==================================================
// REPROGRAMACIÓN
// ==================================================

export interface ReschedulePayload {
  start_date: string
  duration_days: number
}

export interface ScheduleChange {
  task_id: number
  name: string

  old_start_date: string
  old_end_date: string

  new_start_date: string
  new_end_date: string

  estimated_duration_days: number
  is_origin: boolean
}

export interface ScheduleResult {
  project_id: number
  origin_task_id: number

  committed: boolean

  affected_tasks: number
  updated_tasks: number

  changes: ScheduleChange[]
}

// ==================================================
// CRONOGRAMA COMPLETO
// ==================================================

export interface ScheduleProject {
  id: number
  code: string
  name: string
  status: ProjectStatus

  start_date: string
  end_date: string
}

export interface ScheduleCalendarException {
  date: string
  is_working: boolean
}

export interface ScheduleCalendar {
  source: 'default' | 'configured'
  calendar_id: number | null

  working_weekdays: number[]
  exceptions: ScheduleCalendarException[]
}

export interface ScheduleTask {
  id: number
  name: string
  description: string

  status: TaskStatus

  start_date: string
  end_date: string

  actual_start_date: string | null
  actual_end_date: string | null

  estimated_duration_days: number | null
  actual_duration_days: number | null

  progress_percent: string
  position: number
}

export interface ScheduleDependency {
  id: number

  predecessor_id: number
  successor_id: number

  dependency_type: DependencyType
  lag_days: number
}

export interface ProjectSchedule {
  project: ScheduleProject
  calendar: ScheduleCalendar

  tasks_count: number
  dependencies_count: number

  tasks: ScheduleTask[]
  dependencies: ScheduleDependency[]
}

// ==================================================
// SERVICIO DE PLANIFICACIÓN
// ==================================================

export const schedulingService = {
  /**
   * Obtiene el cronograma completo del proyecto.
   *
   * Incluye:
   * - Proyecto
   * - Calendario
   * - Actividades
   * - Dependencias
   */
  async getProjectSchedule(projectId: number): Promise<ProjectSchedule> {
    const response = await api.get<ProjectSchedule>(`/scheduling/projects/${projectId}/schedule/`)

    return response.data
  },

  /**
   * Simula una reprogramación.
   *
   * No guarda cambios en PostgreSQL.
   */
  async preview(taskId: number, payload: ReschedulePayload): Promise<ScheduleResult> {
    const response = await api.post<ScheduleResult>(`/scheduling/tasks/${taskId}/preview/`, payload)

    return response.data
  },

  /**
   * Confirma la reprogramación.
   *
   * Django calcula y guarda los cambios
   * mediante SchedulePropagationService.
   */
  async reschedule(taskId: number, payload: ReschedulePayload): Promise<ScheduleResult> {
    const response = await api.post<ScheduleResult>(
      `/scheduling/tasks/${taskId}/reschedule/`,
      payload,
    )

    return response.data
  },
}

// ==================================================
// SERVICIO DE DEPENDENCIAS
// ==================================================

export const dependencyService = {
  async list(filters: DependencyFilters = {}): Promise<TaskDependency[]> {
    const response = await api.get<TaskDependency[]>('/scheduling/dependencies/', {
      params: filters,
    })

    return response.data
  },

  async getById(id: number): Promise<TaskDependency> {
    const response = await api.get<TaskDependency>(`/scheduling/dependencies/${id}/`)

    return response.data
  },

  async create(payload: DependencyPayload): Promise<TaskDependency> {
    const response = await api.post<TaskDependency>('/scheduling/dependencies/', payload)

    return response.data
  },

  async update(id: number, payload: Partial<DependencyPayload>): Promise<TaskDependency> {
    const response = await api.patch<TaskDependency>(`/scheduling/dependencies/${id}/`, payload)

    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/scheduling/dependencies/${id}/`)
  },
}
