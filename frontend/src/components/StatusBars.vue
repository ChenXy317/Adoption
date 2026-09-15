<template>
  <div class="status-bars">
    <div v-for="attr in stats" :key="attr.key" class="attr-row">
      <div class="attr-head">
        <span>{{ attr.name }}</span>
        <span class="dim">{{ round(attr.value) }}</span>
      </div>
      <div class="bar">
        <div
          class="bar-fill"
          :class="{ low: percent(attr) < 25 }"
          :style="{ width: percent(attr) + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  attributes: { type: Array, default: () => [] },
});

const stats = computed(() =>
  props.attributes.filter((a) => a.category !== "resource")
);

function percent(attr) {
  const span = attr.max - attr.min || 1;
  return Math.max(0, Math.min(100, ((attr.value - attr.min) / span) * 100));
}

function round(v) {
  return Math.round(v * 10) / 10;
}
</script>

<style scoped>
.status-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.attr-row {
  transition: transform var(--ease-spring);
}

.attr-row:hover {
  transform: translateX(2px);
}

.attr-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 5px;
  letter-spacing: 0.02em;
}

.attr-head .dim {
  font-variant-numeric: tabular-nums;
  color: var(--accent-hover);
  text-shadow: 0 0 12px rgba(167, 139, 250, 0.4);
}

.bar {
  position: relative;
  height: 7px;
  background: color-mix(in srgb, var(--bg-soft) 90%, transparent);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
}

.bar-fill {
  position: relative;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #6366f1, var(--accent), #e879f9);
  background-size: 220% 100%;
  box-shadow: 0 0 12px -2px rgba(139, 92, 246, 0.95);
  transition: width 0.5s var(--ease-spring);
  animation: barFlow 3.4s linear infinite;
}

/* 进度条上的流光扫过 */
.bar-fill::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 22%, rgba(255, 255, 255, 0.55) 50%, transparent 78%);
  transform: translateX(-100%);
  animation: barShine 3.2s ease-in-out infinite;
}

@keyframes barFlow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 220% 50%;
  }
}

@keyframes barShine {
  0%,
  55% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.bar-fill.low {
  background: linear-gradient(90deg, #ef4444, #fb7185);
  box-shadow: 0 0 12px -2px rgba(248, 113, 113, 0.95);
  animation: lowPulse 1.4s ease-in-out infinite;
}

@keyframes lowPulse {
  0%,
  100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.35);
  }
}

html[data-theme="light"] .bar-fill:not(.low) {
  background: linear-gradient(90deg, #6366f1, #7c3aed, #c026d3);
  background-size: 220% 100%;
}
</style>
