import axios from 'axios'

// La API Django se sirve en /api/. Configurar VITE_API_BASE_URL como
// http://localhost:8000/api (usar el mismo hostname que en Vue).
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 15000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let csrfToken: string | null = null
let csrfPending: Promise<string> | null = null

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  if (!csrfPending) {
    csrfPending = api.get<{ csrfToken: string }>('/auth/csrf/').then(({ data }) => {
      csrfToken = data.csrfToken
      return data.csrfToken
    }).finally(() => { csrfPending = null })
  }
  return csrfPending
}

api.interceptors.request.use(async (config) => {
  const method = (config.method || 'get').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    config.headers.set('X-CSRFToken', await ensureCsrfToken())
  }
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url || ''
      // No finalizar la sesión global durante login o comprobación de sesión.
      if (!['/auth/login/', '/auth/me/', '/auth/logout/'].some(path => url.includes(path))) {
        window.dispatchEvent(new Event('order-project:session-expired'))
      }
    }
    return Promise.reject(error)
  },
)

export interface HealthResponse {
  status: string
  service: string
  database: string
  message: string
}

export const healthService = {
  async check(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>('/health/')
    return response.data
  },
}

export default api
