<template>
  <section class="card panel">
    <h3>最近事件</h3>
    <div v-if="!events.length" class="dim small">还没有发生过事件。</div>
    <div v-for="event in events" :key="event.id" class="event">
      <div class="event-head">
        <span>{{ event.name }}</span>
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
.event {
  margin-bottom: 10px;
}

.event-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 3px;
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
