<script setup lang="ts">
import { RouterView } from 'vue-router'

import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
</script>

<template>
  <div class="app-layout">
    <AppSidebar />

    <div class="app-main">
      <AppTopbar />

      <main class="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-background);
}

.app-main {
  flex: 1;
  min-width: 0;
}

.app-content {
  max-width: 1500px;
  margin: 0 auto;
  padding: 38px;
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .app-content {
    padding: 22px 16px;
  }
}
</style>
