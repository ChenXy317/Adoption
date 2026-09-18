<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <h1>养成</h1>
        <p class="brand-sub dim">一段慢慢展开的关系</p>
      </div>
      <div class="topbar-actions">
        <div class="actions-secondary">
          <button class="btn" @click="catalogOpen = true">模型配置</button>
          <button class="btn" @click="defsOpen = true">定义管理</button>
          <button class="btn" @click="themeOpen = true">主题</button>
          <button class="btn" :disabled="importing" @click="triggerImport">
            {{ importing ? "导入中…" : "导入存档" }}
          </button>
        </div>
        <button class="btn primary" @click="createOpen = true">+ 新建存档</button>
      </div>
    </header>

    <input
      ref="fileInput"
      type="file"
      accept="application/json,.json"
      style="display: none"
      @change="onImportFile"
    />

    <main class="grid">
      <div v-if="game.loading" class="loading dim">加载中…</div>
      <div v-else-if="!game.saves.length" class="empty card">
        <div class="empty-icon" aria-hidden="true">◇</div>
        <p class="empty-title">还没有存档</p>
        <p class="dim empty-desc">准备好开始这段关系了吗？所有存档共用同一位女主角，新存档从头开始。</p>
        <button class="btn primary" @click="createOpen = true">开始</button>
      </div>
      <template v-else>
        <div
          v-for="save in game.saves"
          :key="save.id"
          class="save-card card"
          @click="enter(save)"
          @mousemove="spotlight"
        >
          <div class="save-top">
            <strong class="save-name">{{ save.name }}</strong>
            <div class="save-ops" @click.stop>
              <button class="btn small-btn" @click="exportSave(save)">导出</button>
              <button class="btn danger small-btn" @click="remove(save)">
                删除
              </button>
            </div>
          </div>
          <div class="save-char dim">
            {{ save.character?.name || "未关联女主角" }}
            <span v-if="save.character?.relation">
              · {{ save.character.relation }}
            </span>
          </div>
          <div class="save-meta">
            <span class="dim small">{{ save.virtual_time }}</span>
            <span class="dim small">{{ save.message_count }} 条消息</span>
          </div>
          <SaveModelSelect
            :save-id="save.id"
            :model-key="save.model_key || ''"
            compact
            @open-catalog="catalogOpen = true"
          />
        </div>
      </template>
    </main>

    <SaveCreateModal
      v-if="createOpen"
      @close="createOpen = false"
      @created="onCreated"
    />
    <ModelCatalogModal v-if="catalogOpen" @close="catalogOpen = false" />
    <DefsPanel v-if="defsOpen" @close="defsOpen = false" />
    <ThemeModal v-if="themeOpen" @close="themeOpen = false" />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { apiPost } from "../api/client";
import DefsPanel from "../components/DefsPanel.vue";
import ModelCatalogModal from "../components/ModelCatalogModal.vue";
import SaveCreateModal from "../components/SaveCreateModal.vue";
import SaveModelSelect from "../components/SaveModelSelect.vue";
import ThemeModal from "../components/ThemeModal.vue";
import { useCatalogStore } from "../stores/catalog";
import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const router = useRouter();
const game = useGameStore();
const catalog = useCatalogStore();
const ui = useUiStore();
const createOpen = ref(false);
const catalogOpen = ref(false);
const defsOpen = ref(false);
const themeOpen = ref(false);
const fileInput = ref(null);
const importing = ref(false);

onMounted(async () => {
  try {
    await Promise.all([game.loadSaves(), catalog.loadModels()]);
  } catch (e) {
    ui.toast("error", e.message);
  }
});

function enter(save) {
  router.push(`/game/${save.id}`);
}

/** 让卡片内的聚光跟随鼠标位置 */
function spotlight(event) {
  const el = event.currentTarget;
  const rect = el.getBoundingClientRect();
  el.style.setProperty("--mx", `${event.clientX - rect.left}px`);
  el.style.setProperty("--my", `${event.clientY - rect.top}px`);
}

function exportSave(save) {
  const link = document.createElement("a");
  link.href = `/api/saves/${save.id}/export`;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function triggerImport() {
  fileInput.value?.click();
}

async function onImportFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  importing.value = true;
  try {
    const text = await file.text();
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      throw new Error("备份文件不是有效的 JSON");
    }
    const save = await apiPost("/api/saves/import", payload);
    await game.loadSaves();
    ui.toast("ok", `已导入存档「${save.name}」`);
    router.push(`/game/${save.id}`);
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    importing.value = false;
  }
}

function onCreated(save) {
  createOpen.value = false;
  router.push(`/game/${save.id}`);
}

async function remove(save) {
  if (!window.confirm(`删除存档「${save.name}」？该操作不可恢复。`)) return;
  try {
    await game.deleteSave(save.id);
    ui.toast("ok", "已删除");
  } catch (e) {
    ui.toast("error", e.message);
  }
}
</script>

<style scoped>
.page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 44px 24px 64px;
  animation: fadeInUp 0.45s var(--ease-spring) both;
}

.topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.brand h1 {
  margin: 0;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 0.24em;
  background: linear-gradient(115deg, #c4b5fd 0%, #f0abfc 46%, #67e8f9 92%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  animation: breathe 5.5s ease-in-out infinite;
}

html[data-theme="light"] .brand h1 {
  background: linear-gradient(115deg, #5b21b6 0%, #c026d3 48%, #0e7490 95%);
  -webkit-background-clip: text;
  background-clip: text;
}

.brand-sub {
  margin: 8px 0 0;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--accent);
  opacity: 0.85;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.actions-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.loading {
  grid-column: 1 / -1;
  padding: 48px;
  text-align: center;
}

.save-card {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  padding: 18px 18px 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 148px;
  animation: fadeInUp 0.5s var(--ease-spring) both;
  transition: border-color var(--ease), box-shadow var(--ease-spring),
    transform var(--ease-spring);
}

.save-card:nth-child(1) {
  animation-delay: 0.02s;
}

.save-card:nth-child(2) {
  animation-delay: 0.07s;
}

.save-card:nth-child(3) {
  animation-delay: 0.12s;
}

.save-card:nth-child(4) {
  animation-delay: 0.17s;
}

.save-card:nth-child(5) {
  animation-delay: 0.22s;
}

.save-card:nth-child(6) {
  animation-delay: 0.27s;
}

/* 鼠标聚光：跟随 --mx/--my 变量 */
.save-card::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  background: radial-gradient(
    260px circle at var(--mx, 50%) var(--my, 0%),
    rgba(167, 139, 250, 0.22),
    rgba(232, 121, 249, 0.08) 42%,
    transparent 70%
  );
  opacity: 0;
  transition: opacity 0.28s ease;
  pointer-events: none;
}

.save-top,
.save-char,
.save-meta,
.warn {
  position: relative;
  z-index: 1;
}

.save-card:hover::after {
  opacity: 1;
}

.save-card:hover {
  border-color: var(--accent-border);
  box-shadow: 0 22px 48px -26px rgba(139, 92, 246, 0.75),
    0 0 0 1px rgba(139, 92, 246, 0.22), var(--shadow-panel);
  transform: translateY(-4px);
}

html[data-theme="light"] .save-card:hover {
  box-shadow: 0 18px 40px -24px rgba(109, 40, 217, 0.4),
    0 0 0 1px rgba(124, 58, 237, 0.2), var(--shadow-panel);
}

.save-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.save-name {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.save-ops {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.15s ease;
}

.save-card:hover .save-ops {
  opacity: 1;
}

.save-char {
  font-size: 13px;
  line-height: 1.4;
}

.save-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--border-soft);
}

.small {
  font-size: 12px;
}

.warn {
  color: var(--warn);
  font-size: 12px;
  margin-top: 2px;
}

.empty {
  grid-column: 1 / -1;
  position: relative;
  overflow: hidden;
  padding: 72px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: fadeInUp 0.5s var(--ease-spring) both;
}

.empty::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(closest-side, rgba(139, 92, 246, 0.16), transparent) 50% 24% / 60% 70% no-repeat,
    radial-gradient(closest-side, rgba(232, 121, 249, 0.1), transparent) 78% 84% / 40% 50% no-repeat;
  pointer-events: none;
}

.empty-icon {
  position: relative;
  font-size: 40px;
  color: var(--accent-hover);
  text-shadow: 0 0 28px rgba(167, 139, 250, 0.95), 0 0 60px rgba(232, 121, 249, 0.5);
  animation: floatY 4.5s ease-in-out infinite;
  margin-bottom: 8px;
}

.empty-title {
  position: relative;
  margin: 0;
  font-size: 17px;
  font-weight: 650;
  letter-spacing: 0.06em;
}

.empty-desc {
  position: relative;
  margin: 0 0 16px;
  max-width: 380px;
  font-size: 13px;
  line-height: 1.7;
}

/* ── 移动端：单列 + 操作常显（无 hover） + 安全区 ── */
@media (max-width: 768px) {
  .page {
    padding: calc(20px + env(safe-area-inset-top, 0px)) 14px
      calc(28px + env(safe-area-inset-bottom, 0px));
  }

  .topbar {
    gap: 14px;
    margin-bottom: 20px;
  }

  .brand h1 {
    font-size: 26px;
  }

  .topbar-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .actions-secondary {
    width: 100%;
  }

  .topbar-actions .btn.primary {
    width: 100%;
    flex: none;
    min-height: 44px;
  }

  .grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .save-card {
    min-height: 0;
  }

  /* 触屏无 hover，操作按钮默认可见 */
  .save-ops {
    opacity: 1;
  }

  .save-ops .btn {
    min-height: 40px;
    padding: 8px 14px;
  }

  .empty {
    padding: 48px 20px;
  }
}
</style>
