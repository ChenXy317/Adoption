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
  status: { label: "状态", icon: "♡" },
  wallet: { label: "钱包", icon: "¥" },
  advance: { label: "推进", icon: "◷" },
  actions: { label: "行动", icon: "✧" },
  events: { label: "事件", icon: "✦" },
  scene: { label: "场景", icon: "◈" },
};

const hasScene = computed(() => !!game.current?.active_scene);

const navItems = computed(() => {
  const items = [
    { id: "status", label: DIR_META.status.label, icon: DIR_META.status.icon },
    { id: "wallet", label: DIR_META.wallet.label, icon: DIR_META.wallet.icon },
    { id: "advance", label: DIR_META.advance.label, icon: DIR_META.advance.icon },
    { id: "actions", label: DIR_META.actions.label, icon: DIR_META.actions.icon },
    { id: "events", label: DIR_META.events.label, icon: DIR_META.events.icon },
  ];
  if (hasScene.value) {
    items.push({ id: "scene", label: DIR_META.scene.label, icon: DIR_META.scene.icon });
  }
  return items;
});

const drawerTitle = computed(() => (openDir.value ? DIR_META[openDir.value]?.label || "" : ""));

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
  background: transparent;
}

.topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-soft) 74%, transparent);
  backdrop-filter: blur(18px) saturate(1.3);
  flex-shrink: 0;
  z-index: 20;
}

.topbar::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 4%,
    rgba(139, 92, 246, 0.7) 30%,
    rgba(232, 121, 249, 0.55) 62%,
    transparent 96%
  );
  pointer-events: none;
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
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  background: linear-gradient(90deg, #67e8f9, #a78bfa 52%, #f0abfc);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}

html[data-theme="light"] .time {
  background: linear-gradient(90deg, #0e7490, #6d28d9 52%, #a21caf);
  -webkit-background-clip: text;
  background-clip: text;
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
  background:
    radial-gradient(ellipse 80% 46% at 50% -4%, rgba(139, 92, 246, 0.1), transparent 72%),
    radial-gradient(ellipse 40% 30% at 96% 104%, rgba(232, 121, 249, 0.07), transparent 74%),
    color-mix(in srgb, var(--panel) 88%, transparent);
  backdrop-filter: blur(10px);
}

html[data-theme="light"] .chat {
  background:
    radial-gradient(ellipse 80% 46% at 50% -4%, rgba(124, 58, 237, 0.06), transparent 72%),
    radial-gradient(ellipse 40% 30% at 96% 104%, rgba(192, 38, 211, 0.05), transparent 74%),
    color-mix(in srgb, var(--panel) 92%, transparent);
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
  gap: 6px;
}

.meta {
  font-size: 12px;
  margin-bottom: 6px;
}

.phase,
.mood {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  background: linear-gradient(120deg, var(--accent-soft), rgba(232, 121, 249, 0.1));
  border: 1px solid var(--accent-border);
  color: var(--accent-hover);
  font-size: 12px;
  line-height: 1.45;
  box-shadow: var(--glow-soft);
  width: fit-content;
}

.mood {
  margin-bottom: 8px;
}

.phase:last-of-type {
  margin-bottom: 8px;
}

/* ── 移动端（≤768px）：顶栏压缩横滑 + 纵向布局 + 底部功能条 ── */
@media (max-width: 768px) {
  .game {
    height: 100vh;
    height: 100dvh;
  }

  .topbar {
    gap: 8px;
    padding: 8px 10px;
    padding-top: calc(8px + env(safe-area-inset-top, 0px));
  }

  .topbar-left {
    gap: 8px;
    flex: 1;
  }

  .save-title {
    font-size: 13px;
    max-width: 34vw;
  }

  .time {
    font-size: 11px;
  }

  /* 右侧操作横向滑动，不挤占纵向空间 */
  .topbar-right {
    flex-wrap: nowrap;
    justify-content: flex-start;
    gap: 6px;
    max-width: 52vw;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }

  .topbar-right::-webkit-scrollbar {
    display: none;
  }

  .topbar-right .btn {
    flex-shrink: 0;
    min-height: 36px;
    padding: 6px 10px;
  }

  .body {
    flex-direction: column;
    gap: 8px;
    padding: 8px 8px calc(8px + env(safe-area-inset-bottom, 0px));
  }

  .chat {
    flex: 1;
    min-height: 0;
    border-radius: var(--radius-sm);
  }

  /* 功能条沉底：抽屉在上、导航在下 */
  .side-shell {
    order: 2;
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    flex-shrink: 0;
  }
}
</style>
