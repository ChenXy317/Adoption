<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal memory-modal">
      <div class="row" style="justify-content: space-between">
        <h2 style="margin: 0">记忆</h2>
        <div class="row">
          <button class="btn" :disabled="busy" @click="summarize">
            {{ busy ? "处理中…" : "手动总结" }}
          </button>
          <button class="btn" @click="creating = !creating">+ 新增</button>
          <button class="btn" @click="$emit('close')">关闭</button>
        </div>
      </div>
      <div class="dim small meta">
        未总结消息 {{ unsummarized }} 条 · 最近总结：{{ jobLabel }}
      </div>
      <p v-if="notice" class="notice">{{ notice }}</p>

      <div v-if="creating" class="create">
        <div class="row">
          <select v-model="draft.kind">
            <option v-for="k in KINDS" :key="k.key" :value="k.key">{{ k.label }}</option>
          </select>
          <input
            v-model.number="draft.importance"
            type="number"
            min="1"
            max="10"
            style="width: 70px"
          />
          <input
            v-model="draft.content"
            placeholder="记忆内容"
            style="flex: 1"
            @keyup.enter="create"
          />
          <button class="btn primary" :disabled="busy || !draft.content.trim()" @click="create">
            添加
          </button>
        </div>
      </div>

      <div v-if="!items.length" class="dim small empty">
        还没有记忆。积累一些对话后会自动总结，或点「手动总结」。
      </div>
      <div
        v-for="item in items"
        :key="item.id"
        class="memory-item"
        :class="{ archived: item.status === 'archived' }"
      >
        <div class="row" style="justify-content: space-between">
          <div class="row">
            <span class="kind">{{ kindLabel(item.kind) }}</span>
            <span v-if="item.status === 'archived'" class="dim small">（已归档）</span>
          </div>
          <span class="dim small">
            {{ item.recall_count ? `召回 ${item.recall_count} 次 · ` : "" }}{{ createdLabel(item.created_at) }}
          </span>
        </div>
        <textarea
          v-model="item.content"
          rows="2"
          @change="patch(item, { content: item.content })"
        ></textarea>
        <div class="row actions">
          <select :value="item.kind" @change="patch(item, { kind: $event.target.value })">
            <option v-for="k in KINDS" :key="k.key" :value="k.key">{{ k.label }}</option>
          </select>
          <input
            type="number"
            min="1"
            max="10"
            style="width: 70px"
            :value="item.importance"
            @change="patch(item, { importance: Number($event.target.value) })"
          />
          <button class="btn small" @click="patch(item, { status: item.status === 'active' ? 'archived' : 'active' })">
            {{ item.status === "active" ? "归档" : "恢复" }}
          </button>
          <button class="btn danger small" @click="remove(item)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import { apiDelete, apiGet, apiPatch, apiPost } from "../api/client";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
});
defineEmits(["close"]);

const KINDS = [
  { key: "fact", label: "事实" },
  { key: "event", label: "事件" },
  { key: "relationship", label: "关系" },
  { key: "promise", label: "约定" },
];

const ui = useUiStore();
const items = ref([]);
const unsummarized = ref(0);
const job = ref(null);
const busy = ref(false);
const notice = ref("");
const creating = ref(false);
const draft = ref({ kind: "fact", content: "", importance: 5 });

const jobLabel = computed(() => {
  const value = job.value;
  if (!value) return "无";
  const map = {
    pending: "排队中",
    running: "进行中",
    done: "成功",
    failed: `失败（${value.error || "未知"}）`,
  };
  return map[value.status] || value.status;
});

const kindLabel = (key) => KINDS.find((k) => k.key === key)?.label || key;
const createdLabel = (value) => (value ? new Date(value).toLocaleString() : "");

async function load() {
  const data = await apiGet(`/api/saves/${props.saveId}/memories`);
  items.value = data.memories || [];
  unsummarized.value = data.unsummarized || 0;
  job.value = data.job || null;
}

async function summarize() {
  if (busy.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const data = await apiPost(`/api/saves/${props.saveId}/memories/summarize`);
    notice.value = data.message || "";
    await load();
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}

async function create() {
  const content = draft.value.content.trim();
  if (!content || busy.value) return;
  busy.value = true;
  try {
    await apiPost(`/api/saves/${props.saveId}/memories`, {
      kind: draft.value.kind,
      content,
      importance: draft.value.importance,
    });
    draft.value = { kind: "fact", content: "", importance: 5 };
    creating.value = false;
    await load();
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}

async function patch(item, payload) {
  try {
    await apiPatch(`/api/saves/${props.saveId}/memories/${item.id}`, payload);
    await load();
  } catch (e) {
    ui.toast("error", e.message);
  }
}

async function remove(item) {
  try {
    await apiDelete(`/api/saves/${props.saveId}/memories/${item.id}`);
    await load();
  } catch (e) {
    ui.toast("error", e.message);
  }
}

onMounted(load);
</script>

<style scoped>
.memory-modal {
  width: min(760px, 94vw);
}

.meta {
  margin: 10px 0 4px;
}

.notice {
  color: var(--accent);
  font-size: 12px;
  margin: 6px 0;
}

.empty {
  margin-top: 16px;
}

.create {
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 10px;
  margin: 10px 0;
}

.memory-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  margin-top: 10px;
  background: var(--bg-soft);
}

.memory-item.archived {
  opacity: 0.55;
}

.kind {
  color: var(--accent);
  font-size: 12px;
}

.memory-item textarea {
  width: 100%;
  margin: 8px 0;
  resize: vertical;
  font-size: 13px;
  line-height: 1.5;
}

.actions select {
  flex: 1;
}

.small {
  font-size: 12px;
}
</style>
