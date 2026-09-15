<template>
  <nav class="side-nav" aria-label="侧栏方向">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="nav-item"
      :class="{ active: active === item.id }"
      :aria-pressed="active === item.id"
      :title="item.label"
      @click="$emit('select', item.id)"
    >
      <span class="nav-icon" aria-hidden="true">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  active: { type: String, default: null },
});
defineEmits(["select"]);
</script>

<style scoped>
.side-nav {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 5px;
  width: 56px;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--bg-soft) 72%, transparent);
  backdrop-filter: blur(16px) saturate(1.25);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-panel), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  overflow-y: auto;
  align-self: stretch;
}

.nav-item {
  position: relative;
  appearance: none;
  border: none;
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  border-radius: var(--radius-xs);
  padding: 10px 4px;
  min-height: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  transition: background var(--ease), color var(--ease), box-shadow var(--ease-spring),
    transform var(--ease-spring);
}

.nav-item:hover {
  color: var(--text);
  background: var(--accent-soft);
  transform: translateY(-1px);
}

.nav-item.active {
  color: var(--accent-hover);
  background: linear-gradient(165deg, var(--accent-soft), rgba(232, 121, 249, 0.1));
  box-shadow: inset 0 0 0 1px var(--accent-border), var(--glow-soft);
}

/* 激活方向的光条标记 */
.nav-item.active::before {
  content: "";
  position: absolute;
  left: -5px;
  top: 20%;
  bottom: 20%;
  width: 3px;
  border-radius: 3px;
  background: var(--grad-primary);
  box-shadow: 0 0 12px 1px rgba(139, 92, 246, 0.95);
}

.nav-icon {
  font-size: 15px;
  line-height: 1;
  opacity: 0.85;
  transition: transform var(--ease-spring), text-shadow var(--ease), opacity var(--ease);
}

.nav-item:hover .nav-icon {
  opacity: 1;
}

.nav-item.active .nav-icon {
  opacity: 1;
  transform: scale(1.18);
  text-shadow: 0 0 14px rgba(167, 139, 250, 0.95);
}

.nav-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 0.18em;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  user-select: none;
}
</style>
