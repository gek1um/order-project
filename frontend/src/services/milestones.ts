import api from './api'

export type MilestoneStatus = 'PENDING' | 'COMPLETED'

export interface Milestone {
  id: number
  project: number
  name: string
  due_date: string
  responsible: string
  acceptance_criteria: string
  evidence: string
  status: MilestoneStatus
  status_display: string
  completed_at: string | null
  tasks: number[]
  created_at: string
  updated_at: string
}

export type MilestonePayload = Pick<Milestone,
  'project' | 'name' | 'due_date' | 'responsible' | 'acceptance_criteria' |
  'evidence' | 'status' | 'completed_at' | 'tasks'
>

export const milestoneService = {
  async list(projectId: number): Promise<Milestone[]> {
    const response = await api.get<Milestone[]>('/milestones/', { params: { project: projectId } })
    return response.data
  },
  async create(data: MilestonePayload): Promise<Milestone> {
    const response = await api.post<Milestone>('/milestones/', data)
    return response.data
  },
  async update(id: number, data: Partial<MilestonePayload>): Promise<Milestone> {
    const response = await api.patch<Milestone>(`/milestones/${id}/`, data)
    return response.data
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/milestones/${id}/`)
  },
}
