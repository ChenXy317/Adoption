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
    .map((c) => `${c.name}${c.delta > 0 ? "+" : ""}${c.delta}`)
    .join("、");
});
</script>

<style scoped>
.bubble {
  max-width: 86%;
  padding: 10px 14px;
  border-radius: 12px;
  position: relative;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble.user {
  align-self: flex-end;
  background: var(--accent-soft);
  border: 1px solid rgba(124, 140, 255, 0.35);
}

.bubble.assistant {
  align-self: flex-start;
  background: var(--panel);
  border: 1px solid var(--border);
}

.bubble.system,
.bubble.event {
  align-self: center;
  background: transparent;
  border: 1px dashed var(--border);
  color: var(--text-dim);
  font-size: 12px;
  max-width: 92%;
}

.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: var(--accent);
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.changes {
  margin-top: 6px;
  font-size: 11px;
  color: var(--warn);
}
</style>
