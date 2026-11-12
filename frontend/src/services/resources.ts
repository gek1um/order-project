import api from './api'

export type ResourceKind = 'PROFESSIONAL' | 'PROFESSIONAL_TYPE' | 'LICENSE' | 'MATERIAL' | 'EQUIPMENT' | 'OTHER'

export interface Resource {
  id: number
  project: number
  project_code: string
  kind: ResourceKind
  kind_display: string
  name: string
  description: string
  specialty: string
  unit: string
  hours_per_week: string | null
  weeks: string | null
  hourly_rate: string | null
  quantity: string
  unit_cost: string | null
  periods: number
  estimated_catalog_cost: string | null
  created_at: string
  updated_at: string
}
export interface ResourcePayload {
  project: number
  kind: ResourceKind
  name: string
  description: string
  specialty: string
  unit: string
  quantity: string
  periods: number
  hours_per_week: string | null
  weeks: string | null
  hourly_rate: string | null
  unit_cost: string | null
}

export interface TaskResourceAssignment {
  id: number
  project: number
  task: number
  task_name: string
  resource: number
  resource_name: string
  resource_kind: ResourceKind
  planned_units: string
  actual_units: string
  planned_unit_cost: string
  actual_unit_cost: string
  planned_cost: string
  actual_cost: string
  notes: string
  created_at: string
  updated_at: string
}
export interface AssignmentPayload {
  task: number
  resource: number
  planned_units: string
  actual_units: string
  planned_unit_cost?: string
  actual_unit_cost?: string
  notes: string
}
export interface ProjectCostSummary {
  project: number
  baseline_budget: string
  planned_resource_cost: string
  actual_resource_cost: string
  planned_budget_variance: string
  actual_budget_variance: string
  actual_minus_planned: string
  assignment_count: number
}
export interface WeeklyAvailabilityRow {
  resource_id: number
  resource_name: string
  resource_kind: ResourceKind
  week_start: string
  week_end: string
  capacity_hours: string
  planned_hours: string
  available_hours: string
  overallocation_hours: string
  overallocated: boolean
  assignment_ids: number[]
}
export interface WeeklyAvailability {
  project: number
  range_start: string
  range_end: string
  calendar_source: string
  allocation_method: string
  note: string
  resource_count: number
  week_count: number
  overallocated_weeks: number
  weeks: WeeklyAvailabilityRow[]
  warnings: { code: string; task_id: number; resource_id: number; detail: string }[]
}

export const resourceService = {
  async list(project: number): Promise<Resource[]> {
    const response = await api.get<Resource[]>('/resources/', { params: { project } })
    return response.data
  },
  async create(payload: ResourcePayload): Promise<Resource> {
    const response = await api.post<Resource>('/resources/', payload)
    return response.data
  },
  async update(id: number, payload: ResourcePayload): Promise<Resource> {
    const response = await api.patch<Resource>(`/resources/${id}/`, payload)
    return response.data
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/resources/${id}/`)
  },
}
export const assignmentService = {
  async list(project: number): Promise<TaskResourceAssignment[]> {
    const response = await api.get<TaskResourceAssignment[]>('/resource-assignments/', { params: { project } })
    return response.data
  },
  async create(payload: AssignmentPayload): Promise<TaskResourceAssignment> {
    const response = await api.post<TaskResourceAssignment>('/resource-assignments/', payload)
    return response.data
  },
  async update(id: number, payload: AssignmentPayload): Promise<TaskResourceAssignment> {
    const response = await api.patch<TaskResourceAssignment>(`/resource-assignments/${id}/`, payload)
    return response.data
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/resource-assignments/${id}/`)
  },
  async projectCosts(id: number): Promise<ProjectCostSummary> {
    const response = await api.get<ProjectCostSummary>(`/resource-costs/projects/${id}/`)
    return response.data
  },
  async availability(id: number): Promise<WeeklyAvailability> {
    const response = await api.get<WeeklyAvailability>(`/resource-availability/projects/${id}/`)
    return response.data
  },
}
