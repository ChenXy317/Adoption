<template>
  <section class="card panel">
    <h3>互动</h3>
    <div v-if="!items.length" class="dim small">暂无互动。</div>
    <div v-for="item in items" :key="item.key" class="action">
      <div class="action-head">
        <span>{{ item.name }}</span>
        <span class="dim small">{{ costText(item.cost) }}</span>
      </div>
      <button
        class="btn small"
        :disabled="busyKey === item.key || !item.available"
        @click="run(item)"
      >
        {{ item.available ? "进行" : reasonText(item.reason) }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";

import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";
import { costText, reasonText } from "../utils/actions";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
  items: { type: Array, default: () => [] },
});
const emit = defineEmits(["triggered"]);

const game = useGameStore();
const ui = useUiStore();
const busyKey = ref("");

async function run(item) {
  if (busyKey.value) return;
  busyKey.value = item.key;
  try {
    const data = await game.triggerManual(props.saveId, item.key);
    emit("triggered", data);
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busyKey.value = "";
  }
}
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

.action {
  margin-bottom: 10px;
}

.action:last-child {
  margin-bottom: 0;
}

.action-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 5px;
}

.small {
  font-size: 12px;
}

.action .btn {
  width: 100%;
}
</style>
