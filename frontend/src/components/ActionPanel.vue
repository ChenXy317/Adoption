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

const props = defineProps({
  saveId: { type: [Number, String], required: true },
  items: { type: Array, default: () => [] },
});
const emit = defineEmits(["triggered"]);

const game = useGameStore();
const ui = useUiStore();
const busyKey = ref("");

const REASON_TEXT = {
  locked: "条件未满足",
  cooldown: "冷却中",
  used: "已完成",
  disabled: "已停用",
  insufficient_money: "金钱不足",
};

function reasonText(reason) {
  return REASON_TEXT[reason] || "不可用";
}

function costText(cost = {}) {
  const parts = [];
  if (cost.money) parts.push(`¥${cost.money}`);
  if (cost.time_minutes) parts.push(`${cost.time_minutes} 分钟`);
  return parts.join(" · ") || "免费";
}

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
.action {
  margin-bottom: 8px;
}

.action-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
}

.small {
  font-size: 12px;
}

.action .btn {
  width: 100%;
}
</style>
