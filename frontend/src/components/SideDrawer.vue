<template>
  <Teleport to="body">
    <div
      v-if="open && overlay"
      class="drawer-backdrop"
      @click="$emit('close')"
    ></div>
  </Teleport>

  <aside
    class="side-drawer"
    :class="{ open, overlay }"
    :aria-hidden="!open"
    role="dialog"
    :aria-label="title || '侧栏详情'"
  >
    <header class="drawer-head">
      <h2 class="drawer-title">{{ title }}</h2>
      <button
        type="button"
        class="btn ghost close-btn"
        aria-label="关闭"
        @click="$emit('close')"
      >
        ×
      </button>
    </header>
    <div class="drawer-body">
      <slot />
    </div>
  </aside>
</template>

<script setup>
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  /** when true, drawer overlays chat with backdrop (narrow viewports) */
  overlay: { type: Boolean, default: false },
});
defineEmits(["close"]);
</script>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(0, 0, 0, 0.35);
}

.side-drawer {
  width: 0;
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  pointer-events: none;
  transition:
    width 0.18s ease,
    max-width 0.18s ease,
    opacity 0.15s ease,
    transform 0.18s ease;
  background: var(--panel);
  border: 1px solid transparent;
  border-radius: var(--radius);
  box-shadow: none;
}

.side-drawer.open {
  width: min(360px, 42vw);
  max-width: 380px;
  opacity: 1;
  pointer-events: auto;
  border-color: var(--border);
  box-shadow: var(--shadow-panel);
}

.side-drawer.overlay {
  position: absolute;
  top: 0;
  bottom: 0;
  right: calc(100% + 8px);
  z-index: 45;
  transform: translateX(8px);
  /* out of flow — do not reserve flex width while closed */
  width: min(360px, calc(100vw - 72px));
  max-width: 380px;
  opacity: 0;
  pointer-events: none;
}

.side-drawer.overlay.open {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
  border-color: var(--border);
  box-shadow: var(--shadow-panel);
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
}

.drawer-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-dim);
  letter-spacing: 0.04em;
}

.close-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
  border-radius: var(--radius-xs);
}

.drawer-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 12px 14px;
}

/* Panels already have card chrome — flatten when nested in drawer */
.drawer-body :deep(.card.panel),
.drawer-body :deep(section.card) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  margin: 0;
}

.drawer-body :deep(.panel h3),
.drawer-body :deep(section.card h3) {
  display: none; /* avoid double title with drawer chrome */
}
</style>
