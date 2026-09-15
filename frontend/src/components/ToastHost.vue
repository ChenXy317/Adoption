<template>
  <div class="toast-host">
    <div
      v-for="t in ui.toasts"
      :key="t.id"
      class="toast"
      :class="t.type"
      @click="ui.dismiss(t.id)"
    >
      {{ t.text }}
    </div>
  </div>
</template>

<script setup>
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
</script>

<style scoped>
.toast-host {
  position: fixed;
  top: 18px;
  right: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 100;
}

.toast {
  position: relative;
  overflow: hidden;
  background: var(--glass-strong);
  backdrop-filter: blur(16px) saturate(1.25);
  border: 1px solid var(--glass-border);
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  padding: 11px 16px 12px 18px;
  max-width: 380px;
  cursor: pointer;
  box-shadow: var(--shadow-modal), 0 0 26px -12px rgba(139, 92, 246, 0.9);
  font-size: 13px;
  line-height: 1.5;
  animation: slideInRight 0.34s var(--ease-spring) both;
  transition: transform var(--ease-spring), opacity 0.15s ease;
}

/* 底部倒计时光条 */
.toast::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  background: var(--grad-primary);
  opacity: 0.65;
  transform-origin: left;
  animation: toastTimer 3.6s linear both;
}

@keyframes toastTimer {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}

.toast:hover {
  transform: translateX(-4px);
}

.toast.error {
  border-left-color: var(--danger);
  box-shadow: var(--shadow-modal), 0 0 26px -12px rgba(248, 113, 113, 0.95);
}

.toast.error::after {
  background: linear-gradient(90deg, #ef4444, #fb7185);
}

.toast.ok {
  border-left-color: var(--ok);
  box-shadow: var(--shadow-modal), 0 0 26px -12px rgba(52, 211, 153, 0.9);
}

.toast.ok::after {
  background: linear-gradient(90deg, #10b981, #34d399);
}
</style>
