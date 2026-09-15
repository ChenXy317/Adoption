<template>
  <div class="msg" :class="message.role">
    <div v-if="withAvatar" class="avatar" aria-hidden="true">
      <span>{{ message.role === "assistant" ? "澄" : "我" }}</span>
    </div>
    <div class="bubble">
      <div class="content">{{ message.content }}</div>
      <div v-if="message.streaming" class="cursor">▍</div>
      <div v-if="changeText" class="changes">属性变化：{{ changeText }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  message: { type: Object, required: true },
});

const withAvatar = computed(
  () => props.message.role === "assistant" || props.message.role === "user"
);

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
.msg {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  animation: fadeInUp 0.35s var(--ease-spring) both;
}

.msg.assistant {
  justify-content: flex-start;
}

.msg.user {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.msg.system,
.msg.event {
  justify-content: center;
}

.avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 650;
  letter-spacing: 0.02em;
  user-select: none;
}

.msg.assistant .avatar {
  background: radial-gradient(circle at 30% 24%, #f0abfc, #8b5cf6 58%, #5b21b6);
  border: 1px solid rgba(240, 171, 252, 0.55);
  color: #ffffff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
  box-shadow: 0 0 20px -4px rgba(167, 139, 250, 0.9), inset 0 1px 0 rgba(255, 255, 255, 0.35);
  animation: breathe 6s ease-in-out infinite;
}

.msg.user .avatar {
  background: color-mix(in srgb, var(--panel-2) 80%, transparent);
  border: 1px solid var(--border);
  color: var(--text-dim);
  box-shadow: var(--shadow-panel);
}

.bubble {
  position: relative;
  max-width: min(78%, 640px);
  padding: 12px 16px;
  border-radius: 16px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-size: 14px;
}

.content {
  display: inline;
}

.msg.user .bubble {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.34), rgba(232, 121, 249, 0.22) 85%);
  border: 1px solid var(--accent-border);
  border-bottom-right-radius: 6px;
  backdrop-filter: blur(8px);
  box-shadow: 0 12px 32px -20px rgba(139, 92, 246, 1), inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

html[data-theme="light"] .msg.user .bubble {
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.16), rgba(192, 38, 211, 0.1) 85%);
}

.msg.assistant .bubble {
  background: color-mix(in srgb, var(--panel) 78%, transparent);
  border: 1px solid var(--border);
  border-bottom-left-radius: 6px;
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow-panel), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.msg.assistant .bubble::before {
  content: "";
  position: absolute;
  left: -1px;
  top: 12px;
  bottom: 12px;
  width: 2px;
  border-radius: 2px;
  background: linear-gradient(180deg, #a78bfa, #e879f9 55%, transparent);
  opacity: 0.85;
  pointer-events: none;
}

.msg.system .bubble,
.msg.event .bubble {
  max-width: 88%;
  padding: 8px 16px;
  border-radius: 999px;
  background: rgba(139, 92, 246, 0.09);
  border: 1px dashed var(--accent-border);
  color: var(--text-dim);
  font-size: 12px;
  text-align: center;
  backdrop-filter: blur(6px);
}

.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: var(--accent-hover);
  text-shadow: 0 0 12px rgba(167, 139, 250, 0.9);
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
  letter-spacing: 0.03em;
  text-shadow: 0 0 14px rgba(251, 191, 36, 0.35);
}
</style>
