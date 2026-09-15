<template>
  <section class="card panel">
    <h3>推进时间</h3>
    <div class="grid">
      <button class="btn small" :disabled="busy" @click="run({ minutes: 10 })">+10 分</button>
      <button class="btn small" :disabled="busy" @click="run({ minutes: 60 })">+1 时</button>
      <button class="btn small" :disabled="busy" @click="run({ minutes: 1440 })">+1 天</button>
    </div>
    <div class="jump">
      <select v-model="period" :disabled="busy">
        <option v-for="item in periods" :key="item.key" :value="item.key">
          {{ item.name }}
        </option>
      </select>
      <button class="btn small" :disabled="busy" @click="run({ period })">
        跳到该时段
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
});
const emit = defineEmits(["advanced"]);

const game = useGameStore();
const ui = useUiStore();
const busy = ref(false);
const period = ref("night");

const periods = [
  { key: "dawn", name: "清晨" },
  { key: "morning", name: "上午" },
  { key: "noon", name: "中午" },
  { key: "afternoon", name: "下午" },
  { key: "evening", name: "傍晚" },
  { key: "night", name: "晚上" },
  { key: "late_night", name: "深夜" },
];

async function run(payload) {
  if (busy.value) return;
  busy.value = true;
  try {
    const data = await game.advance(props.saveId, payload);
    emit("advanced", data);
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.panel {
  padding: 12px 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.jump {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.jump select {
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  font-size: 12px;
}

.small {
  font-size: 12px;
}
</style>
