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
          <div v-if="!save.model_key" class="warn">未选择模型</div>
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
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}

.topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.brand h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: 0.18em;
  color: var(--text);
}

.brand-sub {
  margin: 6px 0 0;
  font-size: 12px;
  letter-spacing: 0.06em;
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
  padding: 18px 18px 16px;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease,
    transform 0.18s ease;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 132px;
}

.save-card:hover {
  border-color: var(--accent-border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.18);
  transform: translateY(-2px);
}

html[data-theme="light"] .save-card:hover {
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
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
  padding: 56px 32px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-icon {
  font-size: 28px;
  color: var(--accent);
  opacity: 0.7;
  margin-bottom: 4px;
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.empty-desc {
  margin: 0 0 12px;
  max-width: 360px;
  font-size: 13px;
  line-height: 1.6;
}
</style>
