<template>
  <Teleport to="body">
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal defs-modal">
      <div class="row" style="justify-content: space-between">
        <h2 style="margin: 0">定义管理</h2>
        <div class="row">
          <button
            v-if="tab === 'events'"
            class="btn"
            :disabled="busy || !selected || !debugSaveId"
            @click="debugTrigger"
          >
            调试触发
          </button>
          <button class="btn" @click="$emit('close')">关闭</button>
        </div>
      </div>

      <div class="tabs">
        <button
          class="btn"
          :class="{ active: tab === 'events' }"
          @click="switchTab('events')"
        >
          事件书
        </button>
        <button
          class="btn"
          :class="{ active: tab === 'scenes' }"
          @click="switchTab('scenes')"
        >
          场景书
        </button>
        <button
          class="btn"
          :class="{ active: tab === 'character' }"
          @click="switchTab('character')"
        >
          角色书
        </button>
        <select
          v-if="tab === 'events'"
          v-model="debugSaveId"
          class="debug-save"
        >
          <option :value="null">调试触发目标存档…</option>
          <option v-for="s in saves" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <CharacterEditor v-if="tab === 'character'" />

      <div v-else class="defs-body">
        <aside class="def-list">
          <button class="btn" style="width: 100%" @click="startCreate">
            + 新建{{ tab === "events" ? "事件" : "场景" }}
          </button>
          <div
            v-for="item in items"
            :key="item.id"
            class="def-item"
            :class="{ active: selected && selected.id === item.id && !creating }"
            @click="select(item)"
          >
            <div class="row" style="justify-content: space-between">
              <span class="def-name">{{ item.name }}</span>
              <span v-if="!item.enabled" class="dim small">停用</span>
            </div>
            <div class="dim small">
              {{ item.key }} · {{ item.category
              }}<template v-if="item.from_seed"> · 内置</template>
              <span v-if="item.user_edited" class="edited-tag">· 已修改</span>
            </div>
          </div>
        </aside>

        <section class="def-detail">
          <div v-if="!selected && !creating" class="dim">
            选择左侧定义进行编辑，或新建一个。内置定义保存后会标记「已修改」，重启不再被种子覆盖，可随时恢复内置。
          </div>
          <template v-else>
            <div class="field">
              <label>key（创建后不可改）</label>
              <input
                v-model="draft.key"
                :disabled="!creating"
                placeholder="snake_case_key"
              />
            </div>
            <div v-for="field in fields" :key="field.key" class="field">
              <label v-if="field.type === 'bool'" class="row check">
                <input v-model="draft[field.key]" type="checkbox" />
                {{ field.label }}
              </label>
              <template v-else>
                <label>{{ field.label }}</label>
                <select
                  v-if="field.type === 'select'"
                  v-model="draft[field.key]"
                >
                  <option v-for="opt in field.options" :key="opt" :value="opt">
                    {{ opt }}
                  </option>
                </select>
                <input
                  v-else-if="field.type === 'text'"
                  v-model="draft[field.key]"
                  type="text"
                />
                <textarea
                  v-else-if="field.type === 'textarea'"
                  v-model="draft[field.key]"
                  rows="3"
                ></textarea>
                <textarea
                  v-else-if="field.type === 'json'"
                  v-model="json[field.key]"
                  rows="4"
                  spellcheck="false"
                ></textarea>
                <input
                  v-else
                  v-model.number="draft[field.key]"
                  type="number"
                />
              </template>
            </div>
            <div class="row" style="justify-content: flex-end; margin-top: 12px">
              <button
                v-if="!creating && selected?.from_seed && selected?.user_edited"
                class="btn"
                :disabled="busy"
                @click="resetSelected"
              >
                恢复内置
              </button>
              <button v-if="!creating" class="btn danger" @click="remove">
                删除
              </button>
              <button class="btn primary" :disabled="busy" @click="save">
                {{ creating ? "创建" : "保存" }}
              </button>
            </div>
          </template>
        </section>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { apiDelete, apiGet, apiPatch, apiPost } from "../api/client";
import CharacterEditor from "./CharacterEditor.vue";
import { useUiStore } from "../stores/ui";

defineEmits(["close"]);

const ui = useUiStore();
const tab = ref("events");
const items = ref([]);
const saves = ref([]);
const selected = ref(null);
const creating = ref(false);
const busy = ref(false);
const error = ref("");
const debugSaveId = ref(null);
const draft = reactive({});
const json = reactive({});

const JSON_KEYS = {
  events: ["trigger", "cost", "effects"],
  scenes: ["enter_trigger", "enter_cost", "exit", "effects", "next_scenes"],
};

const FIELDS = {
  events: [
    { key: "name", label: "名称", type: "text" },
    {
      key: "category",
      label: "分类",
      type: "select",
      options: ["random", "fixed", "manual", "work"],
    },
    { key: "prompt_template", label: "事件文本（AI 承接用）", type: "textarea" },
    { key: "trigger", label: "触发条件（JSON）", type: "json" },
    { key: "cost", label: "花费（JSON，手动事件用）", type: "json" },
    { key: "effects", label: "效果（JSON）", type: "json" },
    { key: "once", label: "仅触发一次", type: "bool" },
    { key: "cooldown_minutes", label: "冷却（虚拟分钟）", type: "number" },
    { key: "priority", label: "优先级", type: "number" },
    { key: "enabled", label: "启用", type: "bool" },
  ],
  scenes: [
    { key: "name", label: "名称", type: "text" },
    { key: "category", label: "分类（story / relationship）", type: "text" },
    { key: "scene_prompt", label: "场景设定", type: "textarea" },
    { key: "goal", label: "本幕目标", type: "textarea" },
    { key: "enter_trigger", label: "进入条件（JSON）", type: "json" },
    { key: "enter_cost", label: "进入花费（JSON）", type: "json" },
    { key: "exit", label: "结束条件（JSON）", type: "json" },
    { key: "effects", label: "结束效果（JSON）", type: "json" },
    { key: "next_scenes", label: "衔接场景 key（JSON 数组）", type: "json" },
    { key: "min_turns", label: "最少轮数", type: "number" },
    { key: "max_turns", label: "最多轮数（0 不限）", type: "number" },
    { key: "once", label: "仅完成一次", type: "bool" },
    { key: "cooldown_minutes", label: "冷却（虚拟分钟）", type: "number" },
    { key: "priority", label: "优先级", type: "number" },
    { key: "enabled", label: "启用", type: "bool" },
  ],
};

const fields = computed(() => FIELDS[tab.value]);

function apiPath() {
  return tab.value === "events" ? "/api/event-defs" : "/api/scene-defs";
}

function emptyJson(key) {
  return key === "next_scenes" ? "[]" : "{}";
}

function resetDraft() {
  for (const key of Object.keys(draft)) delete draft[key];
  for (const key of Object.keys(json)) delete json[key];
}

function fillJson(record) {
  for (const key of JSON_KEYS[tab.value]) {
    const value = record?.[key];
    json[key] = JSON.stringify(value ?? (key === "next_scenes" ? [] : {}), null, 2);
  }
}

function select(item) {
  creating.value = false;
  selected.value = item;
  error.value = "";
  resetDraft();
  Object.assign(draft, {
    key: item.key,
    name: item.name,
    category: item.category,
    once: item.once,
    cooldown_minutes: item.cooldown_minutes,
    priority: item.priority,
    enabled: item.enabled,
  });
  if (tab.value === "events") {
    Object.assign(draft, { prompt_template: item.prompt_template });
  } else {
    Object.assign(draft, {
      scene_prompt: item.scene_prompt,
      goal: item.goal,
      min_turns: item.min_turns,
      max_turns: item.max_turns,
    });
  }
  fillJson(item);
}

function startCreate() {
  creating.value = true;
  selected.value = null;
  error.value = "";
  resetDraft();
  if (tab.value === "events") {
    Object.assign(draft, {
      key: "",
      name: "",
      category: "fixed",
      prompt_template: "",
      once: false,
      cooldown_minutes: 0,
      priority: 0,
      enabled: true,
    });
  } else {
    Object.assign(draft, {
      key: "",
      name: "",
      category: "story",
      scene_prompt: "",
      goal: "",
      min_turns: 3,
      max_turns: 12,
      once: false,
      cooldown_minutes: 0,
      priority: 0,
      enabled: true,
    });
  }
  fillJson(null);
}

async function loadItems() {
  items.value = await apiGet(apiPath());
}

async function switchTab(next) {
  if (tab.value === next) return;
  tab.value = next;
  selected.value = null;
  creating.value = false;
  error.value = "";
  resetDraft();
  if (next === "character") return;
  try {
    await loadItems();
  } catch (e) {
    error.value = e.message;
  }
}

function collect() {
  const payload = { ...draft };
  if (creating.value && !String(payload.key || "").trim()) {
    throw new Error("请填写 key（小写字母开头，只含小写字母、数字、下划线）");
  }
  for (const key of JSON_KEYS[tab.value]) {
    const text = String(json[key] ?? "").trim() || emptyJson(key);
    try {
      payload[key] = JSON.parse(text);
    } catch {
      throw new Error(`${key} 不是有效的 JSON`);
    }
  }
  return payload;
}

async function save() {
  error.value = "";
  busy.value = true;
  try {
    const payload = collect();
    if (creating.value) {
      await apiPost(apiPath(), payload);
      ui.toast("ok", "已创建");
      creating.value = false;
      selected.value = null;
    } else {
      await apiPatch(`${apiPath()}/${selected.value.id}`, payload);
      ui.toast("ok", "已保存");
    }
    await loadItems();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function remove() {
  if (!selected.value) return;
  if (!window.confirm(`删除定义「${selected.value.name}」？`)) return;
  error.value = "";
  try {
    await apiDelete(`${apiPath()}/${selected.value.id}`);
    ui.toast("ok", "已删除");
    selected.value = null;
    resetDraft();
    await loadItems();
  } catch (e) {
    error.value = e.message;
  }
}

async function resetSelected() {
  if (!selected.value) return;
  if (
    !window.confirm(
      `把「${selected.value.name}」恢复为内置定义？当前的修改将被覆盖。`
    )
  ) {
    return;
  }
  error.value = "";
  busy.value = true;
  try {
    const data = await apiPost(`${apiPath()}/${selected.value.id}/reset`);
    ui.toast("ok", "已恢复内置内容");
    await loadItems();
    const fresh = items.value.find((item) => item.id === data.id);
    if (fresh) select(fresh);
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function debugTrigger() {
  if (!selected.value || !debugSaveId.value) return;
  error.value = "";
  busy.value = true;
  try {
    await apiPost(
      `/api/saves/${debugSaveId.value}/events/${encodeURIComponent(selected.value.key)}/trigger?debug=true`
    );
    ui.toast("ok", `已对所选存档调试触发「${selected.value.name}」`);
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    const [eventDefs, allSaves] = await Promise.all([
      apiGet("/api/event-defs"),
      apiGet("/api/saves"),
    ]);
    items.value = eventDefs;
    saves.value = allSaves;
  } catch (e) {
    error.value = e.message;
  }
});
</script>

<style scoped>
.defs-modal {
  width: min(920px, 94vw);
}

.tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 10px;
}

.tabs .btn.active {
  background: linear-gradient(125deg, var(--accent-soft), rgba(232, 121, 249, 0.12));
  border-color: var(--accent);
  color: var(--accent-hover);
  box-shadow: var(--glow-soft);
}

.debug-save {
  margin-left: auto;
  max-width: 220px;
}

.defs-body {
  display: flex;
  gap: 16px;
  min-height: 420px;
}

.def-list {
  width: 240px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-right: 1px solid var(--border);
  padding-right: 12px;
  max-height: 62vh;
  overflow-y: auto;
}

.def-item {
  padding: 7px 9px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background var(--ease), border-color var(--ease),
    transform var(--ease-spring), box-shadow var(--ease);
}

.def-item:hover {
  background: var(--bg-soft);
  transform: translateX(2px);
}

.def-item.active {
  background: linear-gradient(125deg, var(--accent-soft), rgba(232, 121, 249, 0.1));
  border-color: var(--accent);
  box-shadow: var(--glow-soft);
}

.def-name {
  font-size: 13px;
}

.edited-tag {
  color: var(--warn);
}

.def-detail {
  flex: 1;
  min-width: 0;
  max-height: 62vh;
  overflow-y: auto;
  padding-right: 4px;
}

.def-detail textarea {
  width: 100%;
  font-size: 12px;
  font-family: Consolas, "Courier New", monospace;
}

.check {
  cursor: pointer;
  color: var(--text);
  font-size: 13px;
}

.error {
  color: var(--danger);
  font-size: 12px;
  margin: 4px 0;
}

.small {
  font-size: 12px;
}

/* ── 移动端：全宽铺满可见区，内部随弹窗一起滚动 ── */
@media (max-width: 768px) {
  .defs-modal {
    width: 100%;
    max-width: none;
    overflow: hidden;
  }

  .tabs {
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .debug-save {
    margin-left: 0;
    max-width: none;
    flex: 1 1 100%;
  }

  .defs-body {
    flex: 1;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .def-list {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border);
    padding-right: 0;
    padding-bottom: 10px;
    max-height: 38%;
    overflow-y: auto;
    flex: 0 1 auto;
  }

  .def-detail {
    flex: 1;
    min-height: 0;
    max-height: none;
    overflow-y: auto;
    padding-right: 0;
  }
}
</style>
