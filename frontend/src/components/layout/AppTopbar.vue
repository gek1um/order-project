<template>
  <header class="topbar">
    <div class="breadcrumb">
      <span class="breadcrumb-root">Gestión</span>
      <span class="breadcrumb-separator">/</span>
      <span class="breadcrumb-current">Proyectos</span>
    </div>

    <div class="environment">
      <span class="environment-dot"></span>
      Desarrollo local
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 38px;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 12px;
}

.breadcrumb-root,
.breadcrumb-separator {
  color: #8492a6;
}

.breadcrumb-current {
  color: #e5eaf1;
  font-weight: 600;
}

.environment {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-muted);
  font-size: 11px;
}

.environment-dot {
  height: 7px;
  width: 7px;
  border-radius: 50%;
  background: var(--color-success);
}

@media (max-width: 768px) {
  .topbar {
    height: 54px;
    padding: 0 18px;
  }
}
</style>
