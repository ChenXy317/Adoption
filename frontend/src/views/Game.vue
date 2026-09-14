<template>
  <div class="game">
    <header class="topbar">
      <div class="row">
        <button class="btn" @click="router.push('/')">← 返回</button>
        <strong>{{ game.current?.save?.name || "…" }}</strong>
      </div>
      <div class="row">
        <span class="time">{{ game.current?.virtual?.label || "" }}</span>
        <button class="btn" @click="memoryOpen = true">记忆</button>
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
            <template v-if="game.current?.tendency"> · {{ game.current.tendency }}</template>
          </div>
          <div class="phase" v-if="game.current?.mood_label">
            此刻心情：{{ game.current.mood_label }}
          </div>
          <StatusBars :attributes="game.current?.attributes || []" />
        </section>

        <WalletPanel :save-id="$route.params.id" @triggered="onSettled" />

        <AdvancePanel :save-id="$route.params.id" @advanced="onSettled" />

        <ActionPanel
          :save-id="$route.params.id"
          :items="game.current?.manual_events || []"
          @triggered="onSettled"
        />

        <EventPanel :events="game.current?.recent_events || []" />

        <SceneBanner
          :save-id="$route.params.id"
          :scene="game.current?.active_scene"
          @ended="onSettled"
        />
      </aside>
    </div>

    <ModelCatalogModal v-if="catalogOpen" @close="onCatalogClose" />
    <MemoryPanel v-if="memoryOpen" :save-id="$route.params.id" @close="memoryOpen = false" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import ActionPanel from "../components/ActionPanel.vue";
import AdvancePanel from "../components/AdvancePanel.vue";
import ChatInput from "../components/ChatInput.vue";
import ChatStream from "../components/ChatStream.vue";
import EventPanel from "../components/EventPanel.vue";
import MemoryPanel from "../components/MemoryPanel.vue";
import ModelCatalogModal from "../components/ModelCatalogModal.vue";
import SceneBanner from "../components/SceneBanner.vue";
import StatusBars from "../components/StatusBars.vue";
import WalletPanel from "../components/WalletPanel.vue";
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
const memoryOpen = ref(false);

const characterLine = computed(() => {
  const c = game.current?.character;
  if (!c) return "";
  return `${c.name} · ${c.age} 岁 · ${c.relation}`;
});

async function load(saveId) {
  try {
    await Promise.all([game.loadState(saveId), chat.loadMessages(saveId)]);
  } catch (e) {
    ui.toast("error", e.message);
    router.push("/");
  }
}

onMounted(() => {
  load(props.id);
});

watch(
  () => props.id,
  (id) => {
    if (id == null) return;
    chat.cancel();
    game.current = null;
    load(id);
  }
);

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
