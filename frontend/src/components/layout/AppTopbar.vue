<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ref } from 'vue'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loggingOut = ref(false)
const logoutError = ref('')

async function signOut() {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await auth.logout()
    await router.replace({ name: 'login' })
  } catch {
    // El servidor puede estar temporalmente inaccesible. No asumir que cerró la sesión.
    logoutError.value = 'No se pudo confirmar el cierre de sesión.'
  } finally { loggingOut.value = false }
}

const breadcrumb = computed(() => {
  switch (route.name) {
    case 'admin-users':
      return { section: 'Administración', page: 'Usuarios y permisos' }
    case 'dashboard-changes':
      return { section: 'Visión general', page: 'Dashboard de Gestión del Cambio' }
    case 'dashboard-project':
      return { section: 'Visión general', page: 'Seguimiento del proyecto' }
    case 'changes':
      return { section: 'Control', page: 'Gestión de cambios' }
    case 'resources':
      return { section: 'Control', page: 'Recursos y costos' }
    case 'gantt':
      return { section: 'Gestión', page: 'Carta Gantt' }
    case 'milestones':
      return { section: 'Control', page: 'Hitos' }
    case 'milestone-kpis':
      return { section: 'Control', page: 'KPI por hitos' }
    case 'scheduling':
      return { section: 'Gestión', page: 'Programación' }
    case 'project-detail':
      return { section: 'Gestión / Proyectos', page: 'Detalle del proyecto' }
    default:
      return { section: 'Gestión', page: 'Proyectos' }
  }
})
</script>

<template>
  <header class="topbar">
    <div class="breadcrumb" aria-label="Ubicación actual">
      <span class="breadcrumb-root">{{ breadcrumb.section }}</span>
      <span class="breadcrumb-separator">/</span>
      <span class="breadcrumb-current">{{ breadcrumb.page }}</span>
    </div>

    <div class="account-controls">
      <span class="account-label">{{ auth.user?.username }} · {{ auth.isAdmin ? 'ADMIN' : 'PROJECT_USER' }}</span>
      <button class="logout-button" :disabled="loggingOut" @click="signOut">{{ loggingOut ? 'Saliendo…' : 'Cerrar sesión' }}</button>
      <span v-if="logoutError" class="logout-error" role="alert">{{ logoutError }}</span>
    </div>
  </header>
</template>

<style scoped>
.topbar { height: var(--topbar-height); display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 0 38px; background: var(--color-background); border-bottom: 1px solid var(--color-border); }
.breadcrumb { display: flex; align-items: center; gap: 11px; font-size: 12px; }
.breadcrumb-root, .breadcrumb-separator { color: #8492a6; }
.breadcrumb-current { color: #e5eaf1; font-weight: 600; }
.environment { display: flex; align-items: center; gap: 8px; color: var(--color-muted); font-size: 11px; }
.environment-dot { height: 7px; width: 7px; border-radius: 50%; background: var(--color-success); }
@media (max-width: 768px) { .topbar { height: 54px; padding: 0 18px; } }
.account-controls { display:flex; align-items:center; flex-wrap:wrap; justify-content:flex-end; gap:10px; }
.account-label { font-size:11px; color:var(--color-muted); }
.logout-button { background:var(--color-surface); border:1px solid var(--color-border); border-radius:7px; padding:8px 10px; color:var(--color-text); font-size:11px; }
.logout-button:hover { border-color:var(--color-primary); }
.logout-error { color:var(--color-danger); font-size:11px; }
@media (max-width: 768px) { .account-label { display:none; } }
</style>
