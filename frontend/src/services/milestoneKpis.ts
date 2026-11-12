import api from './api'

export type MilestoneKpiKind = 'VALUE' | 'PERCENTAGE'
export type MilestoneKpiDirection = 'AT_LEAST' | 'AT_MOST'
export type MilestoneKpiStatus = 'NOT_MEASURED' | 'MET' | 'NOT_MET'

export interface MilestoneKpi {
  id: number
  milestone: number
  name: string
  description: string
  responsible: string
  kind: MilestoneKpiKind
  kind_display: string
  direction: MilestoneKpiDirection
  direction_display: string
  unit: string
  target_value: string
  measured_value: string | null
  numerator: string | null
  denominator: string | null
  measured_at: string | null
  actual_value: string | null
  achievement_status: MilestoneKpiStatus
  created_at: string
  updated_at: string
}

export type MilestoneKpiPayload = Pick<MilestoneKpi,
  'milestone' | 'name' | 'description' | 'responsible' | 'kind' | 'direction' |
  'unit' | 'target_value' | 'measured_value' | 'numerator' | 'denominator' | 'measured_at'
>

export const milestoneKpiService = {
  async listByProject(projectId: number): Promise<MilestoneKpi[]> {
    const { data } = await api.get<MilestoneKpi[]>('/milestone-kpis/', { params: { project: projectId } })
    return data
  },
  async listByMilestone(milestoneId: number): Promise<MilestoneKpi[]> {
    const { data } = await api.get<MilestoneKpi[]>('/milestone-kpis/', { params: { milestone: milestoneId } })
    return data
  },
  async create(payload: MilestoneKpiPayload): Promise<MilestoneKpi> {
    const { data } = await api.post<MilestoneKpi>('/milestone-kpis/', payload)
    return data
  },
  async update(id: number, payload: Partial<MilestoneKpiPayload>): Promise<MilestoneKpi> {
    const { data } = await api.patch<MilestoneKpi>(`/milestone-kpis/${id}/`, payload)
    return data
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/milestone-kpis/${id}/`)
  },
}
