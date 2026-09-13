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
  top: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 100;
}

.toast {
  background: var(--panel-2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 10px 14px;
  max-width: 360px;
  cursor: pointer;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
}

.toast.error {
  border-left-color: var(--danger);
}

.toast.ok {
  border-left-color: var(--ok);
}
</style>
