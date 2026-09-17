<template>
  <div class="character-editor">
    <div class="editor-head">
      <div class="head-left">
        <h3>
          角色书
          <span class="head-name">· {{ form.name || "未命名" }}</span>
        </h3>
        <span v-if="character.character?.user_edited" class="edited-badge">已修改</span>
      </div>
      <div class="row">
        <button class="btn" :disabled="busy || !character.character" @click="resetAll">恢复内置设定</button>
        <button class="btn primary" :disabled="busy || !character.character" @click="save">
          {{ busy ? "保存中…" : "保存" }}
        </button>
      </div>
    </div>
    <p class="dim note">
      修改对全部存档生效；保存后重启服务不会再被内置种子覆盖，可随时恢复内置设定。
    </p>

    <section class="block">
      <h4>基础</h4>
      <div class="row">
        <div class="field grow">
          <label>姓名</label>
          <input v-model="form.name" maxlength="64" />
        </div>
        <div class="field narrow">
          <label>年龄</label>
          <input v-model.number="form.age" type="number" min="18" max="99" />
        </div>
        <div class="field grow">
          <label>与你的关系</label>
          <input v-model="form.relation" maxlength="64" placeholder="例如：你收留的女孩" />
        </div>
      </div>
    </section>

    <section class="block">
      <h4>形象与性格</h4>
      <div class="field">
        <label>标签（每行一个）</label>
        <textarea v-model="tagsText" rows="3" placeholder="怯懦&#10;慢热&#10;黏人"></textarea>
      </div>
      <div class="field">
        <label>称呼方式</label>
        <textarea v-model="persona.address" rows="2"></textarea>
      </div>
      <div class="field">
        <label>外貌</label>
        <textarea v-model="persona.appearance" rows="4"></textarea>
      </div>
      <div class="field">
        <label>穿着</label>
        <textarea v-model="persona.outfit" rows="3"></textarea>
      </div>
      <div class="field">
        <label>性格</label>
        <textarea v-model="persona.personality" rows="4"></textarea>
      </div>
      <div class="field">
        <label>说话风格</label>
        <textarea v-model="persona.speaking_style" rows="3"></textarea>
      </div>
    </section>

    <section class="block">
      <h4>语言与喜好</h4>
      <div class="field">
        <label>口头禅</label>
        <textarea v-model="persona.catchphrases" rows="2"></textarea>
      </div>
      <div class="field">
        <label>喜欢</label>
        <textarea v-model="persona.likes" rows="3"></textarea>
      </div>
      <div class="field">
        <label>不喜欢</label>
        <textarea v-model="persona.dislikes" rows="3"></textarea>
      </div>
    </section>

    <section class="block">
      <h4>背景与秘密</h4>
      <div class="field">
        <label>背景故事</label>
        <textarea v-model="persona.background" rows="5"></textarea>
      </div>
      <div class="field">
        <label>关系史</label>
        <textarea v-model="persona.relationship_history" rows="4"></textarea>
      </div>
      <div class="field">
        <label>日常</label>
        <textarea v-model="persona.daily_life" rows="4"></textarea>
      </div>
      <div class="field">
        <label>秘密</label>
        <textarea v-model="persona.secrets" rows="4"></textarea>
      </div>
    </section>

    <section class="block">
      <h4>关系阶段语气</h4>
      <div v-for="(label, key) in STAGES" :key="key" class="field">
        <label>{{ label }}（{{ key }}）</label>
        <textarea v-model="stages[key]" rows="3"></textarea>
      </div>
    </section>

    <section class="block">
      <h4>性格倾向语气</h4>
      <div v-for="(label, key) in TENDENCIES" :key="key" class="field">
        <label>{{ label }}（{{ key }}）</label>
        <textarea v-model="tendencies[key]" rows="2"></textarea>
      </div>
    </section>

    <section class="block">
      <h4>示例台词（每行一条）</h4>
      <textarea v-model="linesText" rows="8"></textarea>
    </section>

    <section class="block">
      <h4>导演备注</h4>
      <p class="dim note">给模型的补充指引：身体语言、节奏、禁区与整体调性。</p>
      <textarea v-model="form.freeform" rows="8"></textarea>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { useCharacterStore } from "../stores/character";
import { useUiStore } from "../stores/ui";

const character = useCharacterStore();
const ui = useUiStore();

const STAGES = { stranger: "陌生", familiar: "熟悉", close: "亲近", attached: "依恋" };
const TENDENCIES = { wary: "戒备", clingy: "黏人", devoted: "信赖", steady: "安定" };
const TEXT_KEYS = [
  "address",
  "appearance",
  "outfit",
  "personality",
  "speaking_style",
  "catchphrases",
  "likes",
  "dislikes",
  "background",
  "relationship_history",
  "daily_life",
  "secrets",
];

const busy = ref(false);
const form = reactive({ name: "", age: 19, relation: "", freeform: "" });
const persona = reactive({});
const stages = reactive({});
const tendencies = reactive({});
const tagsText = ref("");
const linesText = ref("");
const extraPersona = ref({});

function loadFrom(data) {
  form.name = data?.name || "";
  form.age = data?.age ?? 19;
  form.relation = data?.relation || "";
  form.freeform = data?.freeform || "";
  const p = data?.persona && typeof data.persona === "object" ? data.persona : {};
  for (const key of TEXT_KEYS) {
    persona[key] = typeof p[key] === "string" ? p[key] : "";
  }
  const stageSource = p.stages && typeof p.stages === "object" ? p.stages : {};
  for (const key of Object.keys(STAGES)) {
    stages[key] = typeof stageSource[key] === "string" ? stageSource[key] : "";
  }
  const tendencySource = p.tendencies && typeof p.tendencies === "object" ? p.tendencies : {};
  for (const key of Object.keys(TENDENCIES)) {
    tendencies[key] = typeof tendencySource[key] === "string" ? tendencySource[key] : "";
  }
  tagsText.value = (Array.isArray(p.tags) ? p.tags : []).join("\n");
  linesText.value = (Array.isArray(p.sample_lines) ? p.sample_lines : []).join("\n");
  const known = new Set([...TEXT_KEYS, "tags", "sample_lines", "stages", "tendencies"]);
  const rest = {};
  for (const [key, value] of Object.entries(p)) {
    if (!known.has(key)) rest[key] = value;
  }
  extraPersona.value = rest;
}

function splitLines(text) {
  return String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function buildPersona() {
  const p = { ...extraPersona.value };
  p.tags = splitLines(tagsText.value);
  for (const key of TEXT_KEYS) {
    p[key] = String(persona[key] || "").trim();
  }
  p.sample_lines = splitLines(linesText.value);
  const oldStages = extraPersona.value.stages && typeof extraPersona.value.stages === "object"
    ? extraPersona.value.stages
    : {};
  const nextStages = { ...oldStages };
  for (const [key, value] of Object.entries(stages)) {
    const text = String(value || "").trim();
    if (text) nextStages[key] = text;
    else delete nextStages[key];
  }
  p.stages = nextStages;
  const oldTendencies = extraPersona.value.tendencies && typeof extraPersona.value.tendencies === "object"
    ? extraPersona.value.tendencies
    : {};
  const nextTendencies = { ...oldTendencies };
  for (const [key, value] of Object.entries(tendencies)) {
    const text = String(value || "").trim();
    if (text) nextTendencies[key] = text;
    else delete nextTendencies[key];
  }
  p.tendencies = nextTendencies;
  return p;
}

async function save() {
  if (busy.value || !character.character) return;
  if (!String(form.name || "").trim()) {
    ui.toast("error", "请填写角色姓名");
    return;
  }
  busy.value = true;
  try {
    await character.update({
      name: String(form.name).trim(),
      age: Number(form.age) || 19,
      relation: String(form.relation || "").trim(),
      persona: buildPersona(),
      freeform: String(form.freeform || ""),
    });
    loadFrom(character.character);
    ui.toast("ok", "角色书已保存");
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}

async function resetAll() {
  if (busy.value) return;
  if (!window.confirm("恢复为内置角色书？当前修改将被覆盖。")) return;
  busy.value = true;
  try {
    await character.reset();
    loadFrom(character.character);
    ui.toast("ok", "已恢复内置设定");
  } catch (e) {
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    if (!character.loaded) await character.load();
    loadFrom(character.character);
  } catch (e) {
    ui.toast("error", e.message);
  }
});
</script>

<style scoped>
.character-editor {
  animation: fadeInUp 0.25s var(--ease-spring) both;
}

.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.editor-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--accent-hover);
  letter-spacing: 0.06em;
  text-shadow: 0 0 16px rgba(167, 139, 250, 0.35);
}

.head-name {
  color: var(--text-dim);
  font-weight: 500;
}

.edited-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: var(--warn);
  border: 1px solid color-mix(in srgb, var(--warn) 45%, transparent);
  background: color-mix(in srgb, var(--warn) 12%, transparent);
}

.note {
  margin: 6px 0 12px;
  font-size: 12px;
  line-height: 1.6;
}

.block {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 12px 14px 4px;
  margin-bottom: 12px;
  background: color-mix(in srgb, var(--bg-soft) 55%, transparent);
}

.block h4 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-hover);
  letter-spacing: 0.06em;
}

.block :deep(textarea) {
  width: 100%;
  resize: vertical;
  font-size: 13px;
  line-height: 1.6;
}

.block .field {
  margin-bottom: 10px;
}

.grow {
  flex: 1;
}

.narrow {
  width: 90px;
}

@media (max-width: 768px) {
  .character-editor {
    flex: 1;
    min-height: 0;
    overflow: auto;
    -webkit-overflow-scrolling: touch;
  }

  .editor-head {
    align-items: flex-start;
  }

  .editor-head .row {
    width: 100%;
  }

  .editor-head .btn {
    flex: 1;
  }

  .narrow {
    width: 100%;
  }
}
</style>
