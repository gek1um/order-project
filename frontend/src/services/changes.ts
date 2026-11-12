import api from './api'

export type ChangeKind = 'SCOPE' | 'TIME' | 'COST' | 'RESOURCE' | 'TECHNOLOGY' | 'ORGANIZATION'
export type ChangePriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ChangeStatus = 'OPEN' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'IMPLEMENTING' | 'CLOSED'

export interface ChangeEvent {
  id: number
  action: string
  from_status: string
  to_status: ChangeStatus
  actor: string
  detail: string
  created_at: string
}
export interface ChangeApplication {
  id: number
  kind: 'SCHEDULE' | 'COST'
  actor: string
  task: number | null
  before: Record<string, unknown>
  after: Record<string, unknown>
  detail: string
  created_at: string
}
export interface ChangeRequest {
  id: number
  project: number
  title: string
  requester: string
  requested_at: string
  description: string
  justification: string
  kind: ChangeKind
  priority: ChangePriority
  risk: string
  impact_scope: string
  impact_resources: string
  estimated_delay_days: number
  estimated_cost: string
  actual_cost: string | null
  responsible: string
  committed_date: string | null
  actual_completion_date: string | null
  result: string
  status: ChangeStatus
  status_display: string
  decided_by: string
  decided_at: string | null
  decision_reason: string
  events: ChangeEvent[]
  applications: ChangeApplication[]
  created_at: string
  updated_at: string
}
export type ChangePayload = Pick<ChangeRequest,
  'project' | 'title' | 'requester' | 'requested_at' | 'description' |
  'justification' | 'kind' | 'priority' | 'risk' | 'impact_scope' |
  'impact_resources' | 'estimated_delay_days' | 'estimated_cost' | 'responsible' | 'committed_date'
>
export interface KpiMetric {
  value: number | null
  unit: string
  numerator?: number
  denominator?: number
  observations?: number
  excluded_missing_or_invalid_date?: number
  excluded_without_dates?: number
}
export interface ChangeKpis {
  project_id: number
  period: { requested_from: string | null; requested_to: string | null }
  counts: { total: number; decided: number; approved: number; rejected: number; closed: number }
  kpis: {
    approval_rate: KpiMetric
    average_decision_days: KpiMetric
    on_time_closure_rate: KpiMetric
  }
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
export interface ChangeScheduleResult {
  project_id: number
  origin_task_id: number
  committed: boolean
  affected_tasks: number
  updated_tasks: number
  changes: ScheduleChange[]
}
export interface ChangeScheduleResponse {
  schedule: ChangeScheduleResult
  change_request: ChangeRequest
}
export interface SchedulePayload {
  actor: string
  task_id: number
  start_date: string
  duration_days: number
  detail?: string
}

export const changeService = {
  async list(project: number): Promise<ChangeRequest[]> {
    return (await api.get<ChangeRequest[]>('/change-requests/', { params: { project } })).data
  },
  async get(id: number): Promise<ChangeRequest> {
    return (await api.get<ChangeRequest>(`/change-requests/${id}/`)).data
  },
  async create(payload: ChangePayload): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>('/change-requests/', payload)).data
  },
  async update(id: number, payload: ChangePayload): Promise<ChangeRequest> {
    return (await api.patch<ChangeRequest>(`/change-requests/${id}/`, payload)).data
  },
  async submit(id: number, actor: string): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>(`/change-requests/${id}/submit/`, { actor })).data
  },
  async decide(id: number, decision: 'approve' | 'reject', actor: string, reason: string): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>(`/change-requests/${id}/${decision}/`, { actor, reason })).data
  },
  async start(id: number, actor: string, committedDate: string): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>(`/change-requests/${id}/start-implementation/`, {
      actor, ...(committedDate ? { committed_date: committedDate } : {}),
    })).data
  },
  async preview(id: number, payload: SchedulePayload): Promise<ChangeScheduleResult> {
    return (await api.post<ChangeScheduleResult>(`/change-requests/${id}/preview-schedule/`, payload)).data
  },
  async apply(id: number, payload: SchedulePayload): Promise<ChangeScheduleResponse> {
    return (await api.post<ChangeScheduleResponse>(`/change-requests/${id}/apply-schedule/`, payload)).data
  },
  async recordCost(id: number, actor: string, actual_cost: string, detail: string): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>(`/change-requests/${id}/record-actual-cost/`, { actor, actual_cost, detail })).data
  },
  async close(id: number, actor: string, actual_completion_date: string, result: string): Promise<ChangeRequest> {
    return (await api.post<ChangeRequest>(`/change-requests/${id}/close/`, { actor, actual_completion_date, result })).data
  },
  async kpis(project: number, from?: string, to?: string): Promise<ChangeKpis> {
    return (await api.get<ChangeKpis>(`/change-kpis/projects/${project}/`, {
      params: { ...(from ? { from } : {}), ...(to ? { to } : {}) },
    })).data
  },
}
