<template>
  <div class="game">
    <header class="topbar">
      <div class="topbar-left">
        <button class="btn ghost-back" @click="router.push('/')">← 返回</button>
        <div class="save-info">
          <strong class="save-title">{{ game.current?.save?.name || "…" }}</strong>
          <span class="time">{{ game.current?.virtual?.label || "" }}</span>
        </div>
      </div>
      <div class="topbar-right">
        <button class="btn" @click="memoryOpen = true">记忆</button>
        <button class="btn" @click="defsOpen = true">定义</button>
        <button class="btn" @click="themeOpen = true">主题</button>
        <button class="btn" @click="catalogOpen = true">模型配置</button>
      </div>
    </header>

    <div class="body">
      <main class="chat card">
        <ChatStream :save-id="$route.params.id" />
        <ChatInput :save-id="$route.params.id" />
      </main>

      <aside class="side">
        <section class="card panel">
          <h3>状态</h3>
          <div class="dim meta" v-if="characterLine">{{ characterLine }}</div>
          <div class="phase" v-if="game.current?.phase">
            关系阶段：{{ game.current.phase }}
            <template v-if="game.current?.tendency"> · {{ game.current.tendency }}</template>
          </div>
          <div class="mood" v-if="game.current?.mood_label">
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
    <DefsPanel v-if="defsOpen" @close="defsOpen = false" />
    <ThemeModal v-if="themeOpen" @close="themeOpen = false" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import ActionPanel from "../components/ActionPanel.vue";
import AdvancePanel from "../components/AdvancePanel.vue";
import ChatInput from "../components/ChatInput.vue";
import ChatStream from "../components/ChatStream.vue";
import DefsPanel from "../components/DefsPanel.vue";
import EventPanel from "../components/EventPanel.vue";
import MemoryPanel from "../components/MemoryPanel.vue";
import ModelCatalogModal from "../components/ModelCatalogModal.vue";
import SceneBanner from "../components/SceneBanner.vue";
import StatusBars from "../components/StatusBars.vue";
import ThemeModal from "../components/ThemeModal.vue";
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
const defsOpen = ref(false);
const themeOpen = ref(false);

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
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-soft);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.ghost-back {
  flex-shrink: 0;
}

.save-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.save-title {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time {
  color: var(--accent);
  font-size: 12px;
  letter-spacing: 0.02em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.body {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  min-height: 0;
  max-width: 1320px;
  width: 100%;
  margin: 0 auto;
}

.chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.side {
  width: 292px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-bottom: 8px;
}

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

.meta {
  font-size: 12px;
  margin-bottom: 6px;
}

.phase,
.mood {
  color: var(--accent);
  font-size: 12px;
  margin: 2px 0;
  line-height: 1.45;
}

.mood {
  margin-bottom: 10px;
}

.phase:last-of-type {
  margin-bottom: 10px;
}
</style>
