<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal catalog-modal">
      <div class="row" style="justify-content: space-between">
        <h2 style="margin: 0">模型配置</h2>
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
      <div class="catalog-body">
        <aside class="providers">
          <button class="btn" style="width: 100%" @click="startCreate">
            + 新建供应商
          </button>
          <div
            v-for="p in catalog.providers"
            :key="p.id"
            class="provider-item"
            :class="{ active: selectedId === p.id && mode === 'edit' }"
            @click="selectProvider(p)"
          >
            <div class="row" style="justify-content: space-between">
              <span>{{ p.display_name }}</span>
              <span v-if="!p.key_ready" class="warn small">密钥缺失</span>
            </div>
            <div class="dim small">{{ p.slug }} · {{ p.models.length }} 个模型</div>
          </div>
        </aside>

        <section class="detail">
          <template v-if="mode === 'create'">
            <h3>新建供应商</h3>
            <div class="row">
              <div class="field" style="flex: 1">
                <label>供应商 ID（创建后不可改）</label>
                <input v-model="createForm.slug" placeholder="deepseek" />
              </div>
              <div class="field" style="flex: 1">
                <label>显示名称</label>
                <input v-model="createForm.display_name" placeholder="DeepSeek" />
              </div>
            </div>
            <div class="field">
              <label>基础 URL</label>
              <input
                v-model="createForm.base_url"
                placeholder="https://api.deepseek.com/v1"
              />
            </div>
            <div class="field">
              <label class="row" style="cursor: pointer">
                <input v-model="createForm.use_env_key" type="checkbox" />
                从环境变量读取密钥
              </label>
              <input
                v-if="createForm.use_env_key"
                v-model="createForm.api_key_env"
                placeholder="DEEPSEEK_API_KEY"
              />
              <input
                v-else
                v-model="createForm.api_key"
                type="password"
                placeholder="API Key（留空则使用占位 key，适合本地无鉴权端点）"
              />
            </div>
            <div class="field">
              <label>初始模型</label>
              <div
                v-for="(m, i) in createForm.models"
                :key="i"
                class="row"
                style="margin-bottom: 6px"
              >
                <input v-model="m.model_id" placeholder="model-id" style="flex: 1" />
                <input
                  v-model="m.display_name"
                  placeholder="显示名（可选）"
                  style="flex: 1"
                />
                <button class="btn danger" @click="createForm.models.splice(i, 1)">
                  移除
                </button>
              </div>
              <button class="btn" @click="createForm.models.push({ model_id: '', display_name: '' })">
                + 添加模型
              </button>
            </div>
            <p v-if="error" class="error">{{ error }}</p>
            <div class="row" style="justify-content: flex-end">
              <button class="btn" @click="mode = 'none'">取消</button>
              <button class="btn primary" :disabled="busy" @click="saveCreate">
                保存
              </button>
            </div>
          </template>

          <template v-else-if="mode === 'edit'">
            <h3>{{ editForm.display_name }}</h3>
            <div class="row">
              <div class="field" style="flex: 1">
                <label>显示名称</label>
                <input v-model="editForm.display_name" />
              </div>
              <div class="field" style="flex: 1">
                <label>基础 URL</label>
                <input v-model="editForm.base_url" />
              </div>
            </div>
            <div class="field">
              <label class="row" style="cursor: pointer">
                <input v-model="editForm.use_env_key" type="checkbox" />
                从环境变量读取密钥
              </label>
              <div class="row">
                <input
                  v-if="editForm.use_env_key"
                  v-model="editForm.api_key_env"
                  placeholder="环境变量名"
                  style="flex: 1"
                />
                <input
                  v-else
                  v-model="editForm.api_key"
                  type="password"
                  placeholder="API Key（留空保持原值）"
                  style="flex: 1"
                />
              </div>
              <div
                v-if="!editForm.use_env_key && provider?.has_api_key"
                class="row"
                style="margin-top: 6px"
              >
                <button class="btn" @click="clearStoredKey">清除已存密钥</button>
              </div>
            </div>

            <h3>模型</h3>
            <div v-for="m in provider?.models || []" :key="m.id" class="model-row">
              <div class="row" style="flex: 1; min-width: 220px">
                <span class="key dim">{{ provider?.slug }}:</span>
                <input v-model="modelIds[m.id]" placeholder="model-id" style="flex: 1" />
              </div>
              <input v-model="modelNames[m.id]" placeholder="显示名" style="width: 140px" />
              <button class="btn" @click="saveModel(m)">保存</button>
              <button class="btn" :disabled="testing === m.id" @click="test(m)">
                {{ testing === m.id ? "测试中…" : "测试" }}
              </button>
              <button class="btn danger" @click="removeModel(m)">删除</button>
              <div v-if="results[m.id]" class="test-result" :class="results[m.id].ok ? 'ok' : 'fail'">
                {{ results[m.id].text }}
              </div>
            </div>
            <div class="row" style="margin-top: 8px">
              <input v-model="newModelId" placeholder="新 model-id" style="flex: 1" />
              <input v-model="newModelName" placeholder="显示名（可选）" style="flex: 1" />
              <button class="btn" :disabled="!newModelId.trim()" @click="addModel">
                添加
              </button>
            </div>

            <p v-if="error" class="error">{{ error }}</p>
            <div class="row" style="justify-content: flex-end; margin-top: 14px">
              <button class="btn danger" @click="removeProvider">删除供应商</button>
              <button class="btn primary" :disabled="busy" @click="saveEdit">
                保存修改
              </button>
            </div>
          </template>

          <div v-else class="dim">选择左侧供应商进行编辑，或新建一个。</div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { useCatalogStore } from "../stores/catalog";
import { useUiStore } from "../stores/ui";

defineEmits(["close"]);
const catalog = useCatalogStore();
const ui = useUiStore();

const mode = ref("none");
const selectedId = ref(null);
const busy = ref(false);
const error = ref("");
const newModelId = ref("");
const newModelName = ref("");
const testing = ref(null);
const results = reactive({});
const modelNames = reactive({});
const modelIds = reactive({});

const createForm = reactive({
  slug: "",
  display_name: "",
  base_url: "",
  api_key: "",
  use_env_key: false,
  api_key_env: "",
  models: [{ model_id: "", display_name: "" }],
});
const editForm = reactive({
  display_name: "",
  base_url: "",
  api_key: "",
  use_env_key: false,
  api_key_env: "",
});

const provider = computed(() =>
  catalog.providers.find((p) => p.id === selectedId.value)
);

onMounted(async () => {
  try {
    await catalog.loadAll();
  } catch (e) {
    error.value = e.message;
  }
});

function startCreate() {
  mode.value = "create";
  error.value = "";
}

function selectProvider(p) {
  mode.value = "edit";
  selectedId.value = p.id;
  error.value = "";
  for (const key of Object.keys(modelNames)) delete modelNames[key];
  for (const key of Object.keys(modelIds)) delete modelIds[key];
  for (const m of p.models) {
    modelNames[m.id] = m.display_name;
    modelIds[m.id] = m.model_id;
    results[m.id] = null;
  }
  Object.assign(editForm, {
    display_name: p.display_name,
    base_url: p.base_url,
    api_key: "",
    use_env_key: p.use_env_key,
    api_key_env: p.api_key_env,
  });
}

async function saveCreate() {
  error.value = "";
  busy.value = true;
  try {
    await catalog.createProvider({
      ...createForm,
      models: createForm.models.filter((m) => m.model_id.trim()),
    });
    ui.toast("ok", "供应商已创建");
    mode.value = "none";
    Object.assign(createForm, {
      slug: "",
      display_name: "",
      base_url: "",
      api_key: "",
      use_env_key: false,
      api_key_env: "",
      models: [{ model_id: "", display_name: "" }],
    });
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function saveEdit() {
  error.value = "";
  busy.value = true;
  try {
    const patch = {
      display_name: editForm.display_name,
      base_url: editForm.base_url,
      use_env_key: editForm.use_env_key,
      api_key_env: editForm.api_key_env,
    };
    if (editForm.api_key) patch.api_key = editForm.api_key;
    await catalog.updateProvider(selectedId.value, patch);
    ui.toast("ok", "已保存");
    editForm.api_key = "";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function addModel() {
  error.value = "";
  try {
    await catalog.addModel(selectedId.value, {
      model_id: newModelId.value.trim(),
      display_name: newModelName.value.trim(),
    });
    newModelId.value = "";
    newModelName.value = "";
    selectProvider(provider.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function saveModel(m) {
  error.value = "";
  const modelId = (modelIds[m.id] ?? "").trim();
  if (!modelId) {
    error.value = "model-id 不能为空";
    return;
  }
  const patch = { display_name: (modelNames[m.id] ?? "").trim() };
  if (modelId !== m.model_id) patch.model_id = modelId;
  try {
    await catalog.updateModel(selectedId.value, m.id, patch);
    ui.toast("ok", "已保存");
    selectProvider(provider.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function clearStoredKey() {
  if (!window.confirm("清除该供应商已保存的 API Key？")) return;
  error.value = "";
  try {
    await catalog.updateProvider(selectedId.value, { api_key: "" });
    ui.toast("ok", "已清除已存密钥");
    editForm.api_key = "";
  } catch (e) {
    error.value = e.message;
  }
}

async function removeModel(m) {
  if (!window.confirm(`删除模型「${m.model_id}」？`)) return;
  error.value = "";
  try {
    await catalog.deleteModel(selectedId.value, m.id);
  } catch (e) {
    error.value = e.message;
  }
}

async function removeProvider() {
  if (!provider.value) return;
  if (!window.confirm(`删除供应商「${provider.value.display_name}」及其全部模型？`)) return;
  error.value = "";
  try {
    await catalog.deleteProvider(selectedId.value);
    mode.value = "none";
    selectedId.value = null;
    ui.toast("ok", "供应商已删除");
  } catch (e) {
    error.value = e.message;
  }
}

async function test(m) {
  testing.value = m.id;
  results[m.id] = null;
  try {
    const res = await catalog.testModel(selectedId.value, m.id);
    results[m.id] = res.ok
      ? { ok: true, text: `连通正常 · ${res.latency_ms}ms · ${res.preview || ""}` }
      : { ok: false, text: res.error || "测试失败" };
  } catch (e) {
    results[m.id] = { ok: false, text: e.message };
  } finally {
    testing.value = null;
  }
}
</script>

<style scoped>
.catalog-modal {
  width: min(860px, 94vw);
}

.catalog-body {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  min-height: 380px;
}

.providers {
  width: 220px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-right: 1px solid var(--border);
  padding-right: 14px;
}

.provider-item {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background var(--ease), border-color var(--ease),
    transform var(--ease-spring), box-shadow var(--ease);
}

.provider-item:hover {
  background: var(--bg-soft);
  transform: translateX(2px);
}

.provider-item.active {
  background: linear-gradient(125deg, var(--accent-soft), rgba(232, 121, 249, 0.1));
  border-color: var(--accent);
  box-shadow: var(--glow-soft);
}

.detail {
  flex: 1;
  min-width: 0;
}

.detail h3 {
  margin: 8px 0 12px;
  font-size: 14px;
  color: var(--accent-hover);
  text-shadow: 0 0 16px rgba(167, 139, 250, 0.35);
}

.model-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 6px 8px;
  border-radius: 8px;
  border-bottom: 1px dashed var(--border);
  transition: background var(--ease);
}

.model-row:hover {
  background: rgba(139, 92, 246, 0.05);
}

.key {
  font-size: 12px;
}

.test-result {
  width: 100%;
  font-size: 12px;
}

.test-result.ok {
  color: var(--ok);
}

.test-result.fail {
  color: var(--danger);
}

.error {
  color: var(--danger);
}

.small {
  font-size: 12px;
}

.warn {
  color: var(--warn);
}
</style>
