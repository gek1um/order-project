import api from './api'

// ==================================================
// TIPOS DE DATOS
// ==================================================

export type TaskStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'

export interface Task {
  id: number
  project: number
  project_code: string
  project_name: string

  name: string
  description: string
  status: TaskStatus
  status_display: string

  // Planificación
  start_date: string
  end_date: string
  estimated_duration_days: number | null

  // Ejecución real
  actual_start_date: string | null
  actual_end_date: string | null
  actual_duration_days: number | null
  progress_percent: string

  position: number

  created_at: string
  updated_at: string
}

// Se conserva el contrato de creación original
// para no romper ProjectDetailView.vue.
export interface TaskPayload {
  project: number
  name: string
  description: string
  status: TaskStatus
  start_date: string
  end_date: string
  position: number

  // Es opcional: las tareas antiguas todavía
  // pueden no tener duración registrada.
  estimated_duration_days?: number | null
}

// Campos que sí pueden actualizarse desde
// el CRUD convencional.
export interface TaskGeneralUpdatePayload {
  project?: number
  name?: string
  description?: string
  status?: TaskStatus
  position?: number

  actual_start_date?: string | null
  actual_end_date?: string | null
  actual_duration_days?: number | null
  progress_percent?: string

  // Compatibilidad con formularios que envían
  // fechas existentes sin modificarlas.
  // Django rechazará cualquier cambio efectivo.
  start_date?: string
  end_date?: string
  estimated_duration_days?: number | null
}

export interface TaskFilters {
  project?: number
  status?: TaskStatus
  search?: string
  ordering?: string
}

// ==================================================
// SERVICIO REST
// ==================================================

export const taskService = {
  async list(filters: TaskFilters = {}): Promise<Task[]> {
    const response = await api.get<Task[]>('/tasks/', {
      params: filters,
    })

    return response.data
  },

  async getById(id: number): Promise<Task> {
    const response = await api.get<Task>(`/tasks/${id}/`)

    return response.data
  },

  async create(payload: TaskPayload): Promise<Task> {
    const response = await api.post<Task>('/tasks/', payload)

    return response.data
  },

  async update(id: number, payload: TaskGeneralUpdatePayload): Promise<Task> {
    const response = await api.patch<Task>(`/tasks/${id}/`, payload)

    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/tasks/${id}/`)
  },
}
