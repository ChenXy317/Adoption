<template>
  <div class="page">
    <header class="topbar">
      <h1>养成</h1>
      <div class="row">
        <button class="btn" @click="catalogOpen = true">模型配置</button>
        <button class="btn" @click="defsOpen = true">定义管理</button>
        <button class="btn" @click="themeOpen = true">主题</button>
        <button class="btn" :disabled="importing" @click="triggerImport">
          {{ importing ? "导入中…" : "导入存档" }}
        </button>
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
      <div v-if="game.loading" class="dim">加载中…</div>
      <div v-else-if="!game.saves.length" class="empty card">
        <p>还没有存档。准备好开始这段关系了吗？</p>
        <p class="dim">所有存档共用同一位女主角，新存档从头开始。</p>
        <div class="row" style="justify-content: center">
          <button class="btn primary" @click="createOpen = true">开始</button>
        </div>
      </div>
      <template v-else>
        <div
          v-for="save in game.saves"
          :key="save.id"
          class="save-card card"
          @click="enter(save)"
        >
          <div class="row" style="justify-content: space-between">
            <strong class="save-name">{{ save.name }}</strong>
            <div class="row">
              <button class="btn small-btn" @click.stop="exportSave(save)">导出</button>
              <button class="btn danger small-btn" @click.stop="remove(save)">
                删除
              </button>
            </div>
          </div>
          <div class="dim">
            {{ save.character?.name || "未关联女主角" }}
            <span v-if="save.character?.relation">
              · {{ save.character.relation }}
            </span>
          </div>
          <div class="row" style="justify-content: space-between; margin-top: 10px">
            <span class="dim small">{{ save.virtual_time }}</span>
            <span class="dim small">{{ save.message_count }} 条消息</span>
          </div>
          <div v-if="!save.model_key" class="warn small">未选择模型</div>
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
  max-width: 1100px;
  margin: 0 auto;
  padding: 28px 24px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.topbar h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 2px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.save-card {
  padding: 16px;
  cursor: pointer;
  transition: 0.15s;
}

.save-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

.save-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty {
  grid-column: 1 / -1;
  padding: 48px;
  text-align: center;
}

.small {
  font-size: 12px;
}

.small-btn {
  padding: 3px 10px;
  font-size: 12px;
}

.warn {
  color: var(--warn);
  font-size: 12px;
  margin-top: 6px;
}
</style>
