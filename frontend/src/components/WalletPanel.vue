<template>
  <section class="card panel">
    <h3>钱包</h3>
    <div class="money">¥ {{ money }}</div>

    <div v-if="!workActions.length" class="dim small">暂无打工入口。</div>
    <div v-for="item in workActions" :key="item.key" class="work">
      <div class="work-head">
        <span>{{ item.name }}</span>
        <span class="dim small">{{ costText(item.cost) }}</span>
      </div>
      <button
        class="btn small"
        :disabled="busyKey === item.key || !item.available"
        @click="run(item)"
      >
        {{ item.available ? "去打工" : reasonText(item.reason) }}
      </button>
    </div>

    <div class="flows-head dim small">最近收支</div>
    <div v-if="!flows.length" class="dim small">暂无收支记录。</div>
    <div v-for="flow in flows" :key="flow.id" class="flow">
      <span class="flow-name">{{ flow.name }}</span>
      <span class="dim small">{{ flow.virtual_label }}</span>
      <span class="flow-amount" :class="flow.amount > 0 ? 'in' : 'out'">
        {{ flow.amount > 0 ? "+" : "" }}{{ flow.amount }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";
import { costText, reasonText } from "../utils/actions";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
});
const emit = defineEmits(["triggered"]);

const game = useGameStore();
const ui = useUiStore();
const busyKey = ref("");

const money = computed(() => {
  const value = game.current?.money ?? 0;
  return Math.round(value * 100) / 100;
});
const workActions = computed(() => game.current?.work_actions || []);
const flows = computed(() => game.current?.wallet_flows || []);

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

.money {
  display: inline-block;
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 12px;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  background: var(--grad-warm);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  animation: breathe 5.5s ease-in-out infinite;
}

.money::after {
  content: "✦";
  margin-left: 8px;
  font-size: 13px;
  vertical-align: 6px;
  -webkit-text-fill-color: var(--warn);
  color: var(--warn);
  text-shadow: 0 0 12px rgba(251, 191, 36, 0.8);
  animation: dotPulse 2.4s ease-in-out infinite;
}

.work {
  margin-bottom: 10px;
}

.work-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 5px;
}

.work .btn {
  width: 100%;
}

.flows-head {
  margin: 12px 0 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border-soft);
  letter-spacing: 0.03em;
}

.flow {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 6px;
  align-items: baseline;
  font-size: 12px;
  padding: 5px 0;
  border-bottom: 1px solid var(--border-soft);
}

.flow:last-child {
  border-bottom: none;
}

.flow-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-amount {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.flow-amount.in {
  color: var(--ok);
}

.flow-amount.out {
  color: var(--danger);
}

.small {
  font-size: 12px;
}
</style>
