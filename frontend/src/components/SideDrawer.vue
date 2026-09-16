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
  position: relative;
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
    width 0.22s var(--ease-spring),
    max-width 0.22s var(--ease-spring),
    opacity 0.18s ease,
    transform 0.22s var(--ease-spring);
  background: color-mix(in srgb, var(--panel) 88%, transparent);
  backdrop-filter: blur(18px) saturate(1.25);
  border: 1px solid transparent;
  border-radius: var(--radius);
  box-shadow: none;
}

/* 抽屉内的侧向渐变光带 */
.side-drawer::after {
  content: "";
  position: absolute;
  left: 0;
  top: 8%;
  bottom: 8%;
  width: 1px;
  border-radius: 1px;
  background: linear-gradient(
    180deg,
    transparent,
    rgba(139, 92, 246, 0.65) 30%,
    rgba(232, 121, 249, 0.55) 70%,
    transparent
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.side-drawer.open {
  width: min(360px, 42vw);
  max-width: 380px;
  opacity: 1;
  pointer-events: auto;
  border-color: var(--glass-border);
  box-shadow: var(--shadow-panel), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.side-drawer.open::after {
  opacity: 1;
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
  background: linear-gradient(180deg, rgba(139, 92, 246, 0.07), transparent);
}

.drawer-title {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
  color: var(--accent-hover);
  letter-spacing: 0.14em;
  text-shadow: 0 0 16px rgba(167, 139, 250, 0.45);
}

.close-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
  border-radius: var(--radius-xs);
  transition: transform var(--ease-spring), background var(--ease), color var(--ease);
}

.close-btn:hover:not(:disabled) {
  transform: rotate(90deg);
  color: var(--accent-hover);
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

/* ── 移动端：抽屉改为底部弹窗，盖在底部导航之上 ── */
@media (max-width: 768px) {
  .side-drawer.open {
    width: 100%;
    max-width: none;
  }
  .side-drawer.overlay {
    position: fixed;
    top: auto;
    left: 8px;
    right: 8px;
    bottom: calc(84px + env(safe-area-inset-bottom, 0px));
    width: auto;
    max-width: none;
    max-height: 62dvh;
    transform: translateY(12px);
    border-radius: var(--radius-sm);
  }

  .side-drawer.overlay.open {
    transform: translateY(0);
  }

  .side-drawer::after {
    display: none;
  }

  .drawer-body {
    padding: 10px 10px calc(12px + env(safe-area-inset-bottom, 0px));
  }

  /* 抽屉内的横向行允许换行，避免小屏溢出 */
  .drawer-body :deep(.row) {
    flex-wrap: wrap;
  }

  .close-btn {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }
}
</style>
