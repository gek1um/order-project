import api from './api'
import type { AuthUser, UserRole } from './auth'

export interface ProjectMembership {
  id: number
  user: number
  username: string
  project: number
  project_code: string
  project_name: string
  created_at: string
}

interface ResultsResponse<T> { results: T[] }

export const userAdministrationService = {
  async listUsers(): Promise<AuthUser[]> {
    const { data } = await api.get<ResultsResponse<AuthUser>>('/auth/users/')
    return data.results
  },
  async createUser(payload: {
    username: string
    password: string
    email?: string
    role: UserRole
  }): Promise<AuthUser> {
    const { data } = await api.post<{ user: AuthUser }>('/auth/users/', payload)
    return data.user
  },
  async changeRole(userId: number, role: UserRole): Promise<AuthUser> {
    const { data } = await api.patch<{ user: AuthUser }>(`/auth/users/${userId}/role/`, { role })
    return data.user
  },
  async listMemberships(userId?: number): Promise<ProjectMembership[]> {
    const { data } = await api.get<ResultsResponse<ProjectMembership>>('/auth/project-memberships/', {
      params: userId ? { user: userId } : undefined,
    })
    return data.results
  },
  async addMembership(userId: number, projectId: number): Promise<ProjectMembership> {
    const { data } = await api.post<{ membership: ProjectMembership }>('/auth/project-memberships/', {
      user: userId,
      project: projectId,
    })
    return data.membership
  },
  async removeMembership(membershipId: number): Promise<void> {
    await api.delete(`/auth/project-memberships/${membershipId}/`)
  },
}
