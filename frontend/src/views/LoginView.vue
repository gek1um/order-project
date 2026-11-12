<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const unavailable = computed(() => route.query.unavailable === '1')
const expired = computed(() => route.query.expired === '1')

function safeNext(): string {
  const value = route.query.next
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/projects'
  return value
}

async function submit() {
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = 'Ingresa tu usuario y contraseña.'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    await router.replace(safeNext())
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      if (err.response?.status === 401) error.value = 'Usuario o contraseña incorrectos.'
      else if (err.response?.status === 403) error.value = 'No se pudo validar la protección CSRF. Comprueba el host y vuelve a intentarlo.'
      else error.value = 'No fue posible iniciar sesión. Comprueba que Django esté disponible.'
    } else error.value = 'Ocurrió un problema al iniciar sesión.'
  } finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <div class="login-card">
      <div class="brand"><span class="brand-logo">OP</span><div><strong>order-project</strong><small>Project Control</small></div></div>
      <div class="intro"><h1>Iniciar sesión</h1><p>Accede a tus proyectos y herramientas de seguimiento.</p></div>
      <p v-if="expired" class="notice" role="status">Tu sesión ha caducado. Inicia sesión nuevamente.</p>
      <p v-if="unavailable" class="notice" role="status">No se pudo comprobar la sesión. Verifica la conexión con Django.</p>
      <form @submit.prevent="submit">
        <label for="login-username">Usuario</label>
        <input id="login-username" v-model="username" autocomplete="username" placeholder="Tu usuario" :disabled="loading" required />
        <label for="login-password">Contraseña</label>
        <input id="login-password" v-model="password" autocomplete="current-password" type="password" placeholder="Tu contraseña" :disabled="loading" required />
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary-button submit" type="submit" :disabled="loading">{{ loading ? 'Verificando…' : 'Iniciar sesión' }}</button>
      </form>
      <p class="footer">Autenticación segura mediante sesiones de Django</p>
    </div>
  </main>
</template>

<style scoped>
.login-page { min-height:100vh; display:grid; place-items:center; padding:24px; background:var(--color-background); }
.login-card { width:100%; max-width:430px; background:var(--color-sidebar); border:1px solid var(--color-border); border-radius:16px; padding:32px; box-shadow:0 18px 60px rgba(0,0,0,.2); }
.brand { display:flex; align-items:center; gap:12px; margin-bottom:32px; }
.brand-logo { display:grid; place-items:center; width:40px; height:40px; border-radius:9px; background:var(--color-primary); font-size:13px; font-weight:800; }
.brand div { display:grid; gap:4px; }
.brand strong { font-size:16px; }
.brand small, .intro p, .footer { font-size:12px; color:var(--color-muted); }
.intro h1 { margin:0 0 10px; font-size:26px; }
.intro p { margin:0 0 26px; line-height:1.6; }
form { display:grid; gap:10px; }
label { font-size:12px; font-weight:600; }
input { width:100%; padding:12px 13px; border:1px solid var(--color-border); border-radius:8px; background:var(--color-surface); outline:none; }
input:focus { border-color:var(--color-primary); }
.submit { margin-top:13px; width:100%; }
.error { color:var(--color-danger); font-size:12px; line-height:1.5; margin:5px 0; }
.notice { padding:12px; background:var(--color-surface); border:1px solid var(--color-border); border-radius:8px; font-size:12px; line-height:1.5; }
.footer { text-align:center; margin:28px 0 0; }
</style>
