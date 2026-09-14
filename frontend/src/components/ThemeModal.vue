<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal theme-modal">
      <div class="row" style="justify-content: space-between">
        <h2 style="margin: 0">主题</h2>
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
          <span>{{ item.label }}</span>
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
    swatch: "linear-gradient(135deg, #14161c, #7c8cff)",
  },
  {
    key: "light",
    label: "亮色",
    swatch: "linear-gradient(135deg, #f4f5f9, #4c5df0)",
  },
];
</script>

<style scoped>
.theme-modal {
  width: min(420px, 92vw);
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
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-soft);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
}

.theme-card.active {
  border-color: var(--accent);
}

.swatch {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.small {
  font-size: 12px;
  margin-left: auto;
}
</style>
