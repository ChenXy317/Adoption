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
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 4px;
  width: 52px;
  flex-shrink: 0;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-panel);
  overflow-y: auto;
  align-self: stretch;
}

.nav-item {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  border-radius: var(--radius-xs);
  padding: 10px 4px;
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--ease), color var(--ease);
}

.nav-item:hover {
  color: var(--text);
  background: var(--accent-soft);
}

.nav-item.active {
  color: var(--accent);
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1px var(--accent-border);
}

.nav-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  letter-spacing: 0.18em;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  user-select: none;
}
</style>
