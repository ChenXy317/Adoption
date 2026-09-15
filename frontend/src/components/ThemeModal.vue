<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal theme-modal">
      <div class="row header">
        <h2>主题</h2>
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
      <div class="themes">
        <button
          v-for="item in THEMES"
          :key="item.key"
          class="theme-card"
          :class="{ active: ui.theme === item.key }"
          @click="ui.setTheme(item.key)"
        >
          <span class="swatch" :style="{ background: item.swatch }"></span>
          <span class="label">{{ item.label }}</span>
          <span v-if="ui.theme === item.key" class="dim small">使用中</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useUiStore } from "../stores/ui";

defineEmits(["close"]);

const ui = useUiStore();

const THEMES = [
  {
    key: "dark",
    label: "暗色（默认）",
    swatch: "linear-gradient(135deg, #05080f, #8b5cf6)",
  },
  {
    key: "light",
    label: "亮色",
    swatch: "linear-gradient(135deg, #f8fafc, #8b5cf6)",
  },
];
</script>

<style scoped>
.theme-modal {
  width: min(420px, 92vw);
}

.header {
  justify-content: space-between;
  margin-bottom: 4px;
}

.header h2 {
  margin: 0;
}

.themes {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.theme-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg-soft);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
  transition: border-color 0.18s ease, background 0.18s ease;
}

.theme-card:hover {
  border-color: var(--accent-border);
}

.theme-card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.swatch {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.label {
  font-weight: 500;
}

.small {
  font-size: 12px;
  margin-left: auto;
}
</style>
