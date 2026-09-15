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

.event {
  position: relative;
  margin-bottom: 10px;
  padding: 2px 0 8px 14px;
  border-bottom: 1px solid var(--border-soft);
  transition: transform var(--ease-spring);
}

.event:hover {
  transform: translateX(2px);
}

.event::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--grad-cool);
  box-shadow: 0 0 10px 1px rgba(34, 211, 238, 0.8);
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
