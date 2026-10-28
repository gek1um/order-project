<script setup lang="ts">
import { RouterLink } from 'vue-router'

const futureSections = [
  {
    title: 'VISIÓN GENERAL',
    items: ['Dashboard ejecutivo', 'Dashboard operativo'],
  },
  {
    title: 'GESTIÓN',
    items: ['Programación', 'Carta Gantt'],
  },
  {
    title: 'CONTROL',
    items: ['Recursos y costos', 'Hitos', 'KPI por hitos', 'Gestión del cambio'],
  },
]
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-logo">OP</div>

      <div class="brand-text">
        <strong>order-project</strong>
        <small>Project Control</small>
      </div>
    </div>

    <nav class="sidebar-navigation">
      <div v-for="section in futureSections" :key="section.title" class="navigation-section">
        <p class="section-heading">
          {{ section.title }}
        </p>

        <template v-if="section.title === 'GESTIÓN'">
          <RouterLink to="/projects" class="navigation-link" active-class="active">
            <span class="navigation-symbol">▦</span>
            <span>Proyectos</span>
          </RouterLink>
        </template>

        <div
          v-for="item in section.items"
          :key="item"
          class="navigation-disabled"
          :title="`${item}: próximamente`"
        >
          <span class="navigation-symbol">○</span>
          <span>{{ item }}</span>
        </div>
      </div>
    </nav>

    <div class="sidebar-footer">
      <span class="online-dot"></span>
      Entorno de desarrollo local
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-border);
}

.sidebar-brand {
  min-height: var(--topbar-height);
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--color-border);
}

.brand-logo {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: #fff;
  background: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-text strong {
  font-size: 13px;
  letter-spacing: 0.2px;
}

.brand-text small {
  font-size: 10px;
  color: var(--color-muted);
}

.sidebar-navigation {
  flex: 1;
  padding: 16px 9px;
}

.navigation-section {
  margin-bottom: 22px;
}

.section-heading {
  margin: 12px 12px;
  color: #718198;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1.2px;
}

.navigation-link,
.navigation-disabled {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 37px;
  padding: 0 13px;
  border-radius: 7px;
  font-size: 12px;
}

.navigation-link {
  color: #b4c0d0;
}

.navigation-link:hover {
  background: #242d3a;
}

.navigation-link.active {
  background: #263951;
  color: #8db9ff;
  font-weight: 600;
}

.navigation-disabled {
  color: #6e7b8e;
  cursor: not-allowed;
}

.navigation-symbol {
  width: 18px;
  font-size: 17px;
  text-align: center;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 20px 16px;
  border-top: 1px solid var(--color-border);
  color: var(--color-muted);
  font-size: 10px;
}

.online-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-success);
}

@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    min-height: auto;
  }

  .sidebar-navigation {
    padding: 8px;
  }

  .navigation-section {
    margin-bottom: 8px;
  }

  .sidebar-footer {
    display: none;
  }
}
</style>
