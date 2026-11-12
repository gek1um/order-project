import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppLayout from '../components/layout/AppLayout.vue'

import LoginView from '../views/LoginView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import ProjectDetailView from '../views/ProjectDetailView.vue'
import SchedulingView from '../views/SchedulingView.vue'
import GanttView from '../views/GanttView.vue'
import MilestonesView from '../views/MilestonesView.vue'
import MilestoneKpisView from '../views/MilestoneKpisView.vue'
import ResourcesView from '../views/ResourcesView.vue'
import ChangesView from '../views/ChangesView.vue'
import ProjectDashboardView from '../views/ProjectDashboardView.vue'
import ChangeDashboardView from '../views/ChangeDashboardView.vue'
import UsersView from '../views/UsersView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    {
      path: '/', component: AppLayout, meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/projects' },
        { path: 'projects', name: 'projects', component: ProjectsView },
        { path: 'projects/:id', name: 'project-detail', component: ProjectDetailView, props: true },
        { path: 'scheduling', name: 'scheduling', component: SchedulingView },
        { path: 'gantt', name: 'gantt', component: GanttView },
        { path: 'milestones', name: 'milestones', component: MilestonesView },
        { path: 'milestone-kpis', name: 'milestone-kpis', component: MilestoneKpisView },
        { path: 'resources', name: 'resources', component: ResourcesView },
        { path: 'changes', name: 'changes', component: ChangesView },
        { path: 'dashboard/project', name: 'dashboard-project', component: ProjectDashboardView },
        { path: 'dashboard/changes', name: 'dashboard-changes', component: ChangeDashboardView },
        { path: 'admin/users', name: 'admin-users', component: UsersView, meta: { adminOnly: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/projects' },
  ],
})

router.beforeEach(async to => {
  const auth = useAuthStore()
  try {
    await auth.initialize()
  } catch {
    // Evitar que una falla temporal del servidor conceda acceso a una ruta privada.
    if (to.name === 'login') return true
    return { name: 'login', query: { unavailable: '1' } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'projects' }
  }
  if (to.matched.some(record => record.meta.requiresAuth) && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.matched.some(record => record.meta.adminOnly) && !auth.isAdmin) {
    return { name: 'projects' }
  }
  return true
})

export default router
