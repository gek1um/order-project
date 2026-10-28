import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
