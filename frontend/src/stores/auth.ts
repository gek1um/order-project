import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from 'axios'
import { authService, type AuthUser } from '../services/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const initialized = ref(false)
  const busy = ref(false)
  let initPending: Promise<void> | null = null

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  async function initialize(): Promise<void> {
    if (initialized.value) return
    if (initPending) return initPending
    initPending = (async () => {
      try {
        user.value = await authService.getCurrentUser()
      } catch (err: unknown) {
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          user.value = null
        } else {
          // No transformar fallas de red o servidor en una sesión anónima.
          throw err
        }
      } finally {
        initialized.value = true
      }
    })()
    try { await initPending } finally { initPending = null }
  }

  async function login(username: string, password: string): Promise<void> {
    busy.value = true
    try {
      user.value = await authService.login(username, password)
      initialized.value = true
    } finally { busy.value = false }
  }

  async function logout(): Promise<void> {
    busy.value = true
    try {
      await authService.logout()
      user.value = null
      initialized.value = true
    } finally {
      busy.value = false
    }
  }

  function expire(): void {
    user.value = null
    initialized.value = true
  }

  return { user, initialized, busy, isAuthenticated, isAdmin, initialize, login, logout, expire }
})
