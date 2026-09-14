<template>
  <div class="game">
    <header class="topbar">
      <div class="row">
        <button class="btn" @click="router.push('/')">← 返回</button>
        <strong>{{ game.current?.save?.name || "…" }}</strong>
      </div>
      <div class="row">
        <span class="time">{{ game.current?.virtual?.label || "" }}</span>
        <button class="btn" @click="catalogOpen = true">模型配置</button>
      </div>
    </header>

    <div class="body">
      <main class="chat card">
        <ChatStream />
        <ChatInput :save-id="$route.params.id" />
      </main>

      <aside class="side">
        <section class="card panel">
          <h3>状态</h3>
          <div class="dim small" v-if="characterLine">{{ characterLine }}</div>
          <div class="phase" v-if="game.current?.phase">
            关系阶段：{{ game.current.phase }}
          </div>
          <StatusBars :attributes="game.current?.attributes || []" />
        </section>

        <section class="card panel">
          <h3>钱包</h3>
          <div class="money">¥ {{ money }}</div>
          <div class="dim small">打工 / 送礼 / 消费将在后续版本开放</div>
        </section>

        <AdvancePanel :save-id="$route.params.id" @advanced="onSettled" />

        <ActionPanel
          :save-id="$route.params.id"
          :items="game.current?.manual_events || []"
          @triggered="onSettled"
        />

        <EventPanel :events="game.current?.recent_events || []" />

        <section class="card panel">
          <h3>当前场景</h3>
          <div class="dim small">
            {{ game.current?.active_scene ? sceneLine : "暂无进行中的场景" }}
          </div>
        </section>
      </aside>
    </div>

    <ModelCatalogModal v-if="catalogOpen" @close="onCatalogClose" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import ActionPanel from "../components/ActionPanel.vue";
import AdvancePanel from "../components/AdvancePanel.vue";
import ChatInput from "../components/ChatInput.vue";
import ChatStream from "../components/ChatStream.vue";
import EventPanel from "../components/EventPanel.vue";
import ModelCatalogModal from "../components/ModelCatalogModal.vue";
import StatusBars from "../components/StatusBars.vue";
import { useChatStore } from "../stores/chat";
import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  id: { type: [String, Number], required: true },
});

const router = useRouter();
const game = useGameStore();
const chat = useChatStore();
const ui = useUiStore();
const catalogOpen = ref(false);

const characterLine = computed(() => {
  const c = game.current?.character;
  if (!c) return "";
  return `${c.name} · ${c.age} 岁 · ${c.relation}`;
});

const money = computed(() => {
  const value = game.current?.money ?? 0;
  return Math.round(value * 100) / 100;
});

const sceneLine = computed(() => {
  const scene = game.current?.active_scene;
  if (!scene) return "";
  return `${scene.name || scene.key} · 第 ${(scene.turns || 0) + 1} 轮`;
});

onMounted(async () => {
  try {
    await Promise.all([game.loadState(props.id), chat.loadMessages(props.id)]);
  } catch (e) {
    ui.toast("error", e.message);
    router.push("/");
  }
});

onBeforeUnmount(() => {
  chat.cancel();
});

async function refresh() {
  try {
    await game.loadState(props.id);
  } catch {
    /* 忽略刷新失败 */
  }
}

async function onSettled(data) {
  chat.pushMessages(data?.messages);
  await refresh();
}

async function onCatalogClose() {
  catalogOpen.value = false;
  await refresh();
}
</script>

<style scoped>
.game {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-soft);
}

.time {
  color: var(--accent);
  font-size: 13px;
}

.body {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  min-height: 0;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
}

.chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.side {
  width: 280px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}

.panel {
  padding: 14px;
}

.panel h3 {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-dim);
  font-weight: 600;
}

.money {
  font-size: 24px;
  font-weight: 700;
  color: var(--warn);
  margin-bottom: 6px;
}

.phase {
  color: var(--accent);
  font-size: 12px;
  margin: 4px 0 10px;
}

.small {
  font-size: 12px;
}
</style>
