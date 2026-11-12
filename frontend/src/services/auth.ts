import api, { ensureCsrfToken, setCsrfToken } from './api'

export type UserRole = 'ADMIN' | 'PROJECT_USER'

export interface AuthUser {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  role: UserRole
  is_staff: boolean
  is_superuser: boolean
}

interface AuthResponse { user: AuthUser; csrfToken?: string }

export const authService = {
  async getCurrentUser(): Promise<AuthUser> {
    const { data } = await api.get<AuthResponse>('/auth/me/')
    return data.user
  },
  async login(username: string, password: string): Promise<AuthUser> {
    await ensureCsrfToken()
    const { data } = await api.post<AuthResponse>('/auth/login/', { username, password })
    // Django rota CSRF al iniciar sesión; el token anterior deja de servir.
    setCsrfToken(data.csrfToken || null)
    return data.user
  },
  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout/', {})
    } finally {
      setCsrfToken(null)
    }
  },
}
