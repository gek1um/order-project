import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './assets/styles/global.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

window.addEventListener('order-project:session-expired', () => {
  const auth = useAuthStore(pinia)
  auth.expire()
  if (router.currentRoute.value.name !== 'login') {
    void router.replace({ name: 'login', query: { next: router.currentRoute.value.fullPath, expired: '1' } })
  }
})

app.mount('#app')
