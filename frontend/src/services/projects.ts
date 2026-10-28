import api from './api'

export type ProjectStatus = 'PLANNED' | 'IN_PROGRESS' | 'ON_HOLD' | 'COMPLETED' | 'CANCELLED'

export interface Project {
  id: number
  code: string
  name: string
  description: string
  manager_name: string
  status: ProjectStatus
  status_display: string
  start_date: string
  end_date: string
  baseline_budget: string
  created_at: string
  updated_at: string
}

export interface CreateProjectPayload {
  code: string
  name: string
  description: string
  manager_name: string
  status: ProjectStatus
  start_date: string
  end_date: string
  baseline_budget: string
}

export interface ProjectFilters {
  status?: string
  search?: string
}

export const projectService = {
  async list(filters: ProjectFilters = {}): Promise<Project[]> {
    const response = await api.get<Project[]>('/projects/', {
      params: filters,
    })

    return response.data
  },

  async getById(id: number): Promise<Project> {
    const response = await api.get<Project>(`/projects/${id}/`)
    return response.data
  },

  async create(payload: CreateProjectPayload): Promise<Project> {
    const response = await api.post<Project>('/projects/', payload)

    return response.data
  },

  async update(id: number, payload: Partial<CreateProjectPayload>): Promise<Project> {
    const response = await api.patch<Project>(`/projects/${id}/`, payload)

    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/projects/${id}/`)
  },
}
