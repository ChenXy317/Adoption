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

.money {
  font-size: 22px;
  font-weight: 700;
  color: var(--warn);
  margin-bottom: 10px;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
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
