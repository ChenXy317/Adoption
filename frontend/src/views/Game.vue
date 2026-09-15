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

      <div class="side-shell" :class="{ 'drawer-open': !!openDir }">
        <SideDrawer
          :open="!!openDir"
          :title="drawerTitle"
          :overlay="useOverlay"
          @close="openDir = null"
        >
          <!-- 状态 -->
          <section v-show="openDir === 'status'" class="status-block">
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

          <WalletPanel
            v-show="openDir === 'wallet'"
            :save-id="$route.params.id"
            @triggered="onSettled"
          />

          <AdvancePanel
            v-show="openDir === 'advance'"
            :save-id="$route.params.id"
            @advanced="onSettled"
          />

          <ActionPanel
            v-show="openDir === 'actions'"
            :save-id="$route.params.id"
            :items="game.current?.manual_events || []"
            @triggered="onSettled"
          />

          <EventPanel
            v-show="openDir === 'events'"
            :events="game.current?.recent_events || []"
          />

          <SceneBanner
            v-show="openDir === 'scene'"
            :save-id="$route.params.id"
            :scene="game.current?.active_scene"
            @ended="onSettled"
          />
        </SideDrawer>

        <SideNav
          :items="navItems"
          :active="openDir"
          @select="toggleDir"
        />
      </div>
    </div>

    <ModelCatalogModal v-if="catalogOpen" @close="onCatalogClose" />
    <MemoryPanel v-if="memoryOpen" :save-id="$route.params.id" @close="memoryOpen = false" />
    <DefsPanel v-if="defsOpen" @close="defsOpen = false" />
    <ThemeModal v-if="themeOpen" @close="themeOpen = false" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from "vue";
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
import SideDrawer from "../components/SideDrawer.vue";
import SideNav from "../components/SideNav.vue";
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

/** currently open direction id, or null */
const openDir = ref(null);
const useOverlay = ref(false);

const DIR_META = {
  status: "状态",
  wallet: "钱包",
  advance: "推进",
  actions: "行动",
  events: "事件",
  scene: "场景",
};

const hasScene = computed(() => !!game.current?.active_scene);

const navItems = computed(() => {
  const items = [
    { id: "status", label: DIR_META.status },
    { id: "wallet", label: DIR_META.wallet },
    { id: "advance", label: DIR_META.advance },
    { id: "actions", label: DIR_META.actions },
    { id: "events", label: DIR_META.events },
  ];
  if (hasScene.value) {
    items.push({ id: "scene", label: DIR_META.scene });
  }
  return items;
});

const drawerTitle = computed(() => (openDir.value ? DIR_META[openDir.value] || "" : ""));

const characterLine = computed(() => {
  const c = game.current?.character;
  if (!c) return "";
  return `${c.name} · ${c.age} 岁${c.relation ? ` · ${c.relation}` : ""}`;
});

function toggleDir(id) {
  openDir.value = openDir.value === id ? null : id;
}

function syncOverlay() {
  useOverlay.value = window.matchMedia("(max-width: 960px)").matches;
}

function onKeydown(e) {
  if (e.key === "Escape" && openDir.value) {
    openDir.value = null;
  }
}

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
  syncOverlay();
  window.addEventListener("resize", syncOverlay);
  window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  chat.cancel();
});

onUnmounted(() => {
  window.removeEventListener("resize", syncOverlay);
  window.removeEventListener("keydown", onKeydown);
});

watch(
  () => props.id,
  (id) => {
    if (id == null) return;
    chat.cancel();
    game.current = null;
    openDir.value = null;
    load(id);
  }
);

watch(hasScene, (ok) => {
  if (!ok && openDir.value === "scene") {
    openDir.value = null;
  }
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
  gap: 12px;
  padding: 16px 20px;
  min-height: 0;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  position: relative;
}

.chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.side-shell {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 8px;
  flex-shrink: 0;
  min-height: 0;
  position: relative;
}

.status-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
