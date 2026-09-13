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
  gap: 10px;
}

.attr-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 3px;
}

.bar {
  height: 6px;
  background: var(--bg-soft);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #9aa6ff);
  border-radius: 3px;
  transition: width 0.4s;
}

.bar-fill.low {
  background: linear-gradient(90deg, var(--danger), #ff9aa8);
}
</style>
