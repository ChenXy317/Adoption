<template>
  <section class="card panel">
    <h3>最近事件</h3>
    <div v-if="!events.length" class="dim small">还没有发生过事件。</div>
    <div v-for="event in events" :key="event.id" class="event">
      <div class="event-head">
        <span class="event-name">{{ event.name }}</span>
        <span class="dim small">{{ event.virtual_label }}</span>
      </div>
      <div class="dim small content">{{ event.content }}</div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  events: { type: Array, default: () => [] },
});
</script>

<style scoped>
.panel {
  padding: 12px 14px;
}

.panel h3 {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-dim);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.event {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
}

.event:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.event-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 3px;
}

.event-name {
  font-weight: 500;
}

.small {
  font-size: 12px;
}

.content {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
</style>
