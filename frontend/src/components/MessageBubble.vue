<template>
  <div class="bubble" :class="message.role">
    <div class="content">{{ message.content }}</div>
    <div v-if="message.streaming" class="cursor">▍</div>
    <div v-if="changeText" class="changes">属性变化：{{ changeText }}</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  message: { type: Object, required: true },
});

const changeText = computed(() => {
  const attrs = props.message.meta?.attrs;
  if (!attrs || !attrs.length) return "";
  return attrs
    .map((c) => `${c.name}${formatDelta(c.delta)}`)
    .join("、");
});

function formatDelta(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? "");
  const rounded = Math.round(num * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}
</script>

<style scoped>
.bubble {
  max-width: 82%;
  padding: 12px 16px;
  border-radius: 14px;
  position: relative;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.65;
  font-size: 14px;
}

.bubble.user {
  align-self: flex-end;
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  border-bottom-right-radius: 6px;
}

.bubble.assistant {
  align-self: flex-start;
  background: var(--panel-2);
  border: 1px solid var(--border);
  border-bottom-left-radius: 6px;
}

.bubble.system,
.bubble.event {
  align-self: center;
  background: transparent;
  border: 1px dashed var(--border);
  color: var(--text-dim);
  font-size: 12px;
  max-width: 90%;
  padding: 8px 14px;
  border-radius: 10px;
  text-align: center;
}

.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: var(--accent);
  margin-left: 1px;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.changes {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--border-soft);
  font-size: 11px;
  color: var(--warn);
  letter-spacing: 0.02em;
}
</style>
