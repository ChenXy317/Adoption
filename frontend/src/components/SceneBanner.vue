<template>
  <section class="card panel">
    <h3>当前场景</h3>
    <template v-if="scene">
      <div class="scene-head">
        <span class="scene-name">{{ scene.name || scene.key }}</span>
        <span class="dim small">第 {{ (scene.turns || 0) + 1 }} 轮</span>
      </div>
      <div v-if="scene.goal" class="dim small goal">目标：{{ scene.goal }}</div>
      <button class="btn small end" :disabled="busy" @click="endScene">
        结束当前场景
      </button>
    </template>
    <div v-else class="dim small">暂无进行中的场景</div>
  </section>
</template>

<script setup>
import { ref } from "vue";

import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
  scene: { type: Object, default: null },
});
const emit = defineEmits(["ended"]);

const game = useGameStore();
const ui = useUiStore();
const busy = ref(false);

async function endScene() {
  if (busy.value) return;
  busy.value = true;
  try {
    const data = await game.endScene(props.saveId, {});
    emit("ended", data);
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

.scene-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  align-items: baseline;
}

.scene-name {
  color: var(--accent-hover);
  font-size: 13px;
  font-weight: 650;
  text-shadow: 0 0 16px rgba(167, 139, 250, 0.5);
}

.goal {
  line-height: 1.5;
  margin-bottom: 10px;
}

.end {
  width: 100%;
}

.small {
  font-size: 12px;
}
</style>
