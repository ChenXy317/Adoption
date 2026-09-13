<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <h2>新建存档</h2>
      <div class="field">
        <label>存档名</label>
        <input v-model="form.name" placeholder="例如：和她的日常" />
      </div>
      <div class="row">
        <div class="field" style="flex: 1">
          <label>角色名字</label>
          <input v-model="form.character.name" placeholder="小雅" />
        </div>
        <div class="field" style="width: 120px">
          <label>年龄（≥18）</label>
          <input v-model.number="form.character.age" type="number" min="18" />
        </div>
      </div>
      <div class="row">
        <div class="field" style="flex: 1">
          <label>与你的关系</label>
          <input v-model="form.character.relation" />
        </div>
        <div class="field" style="flex: 1">
          <label>性格模板</label>
          <select v-model="form.character.template_key">
            <option value="">（不使用模板）</option>
            <option v-for="t in templates" :key="t.key" :value="t.key">
              {{ t.name }}
            </option>
          </select>
        </div>
      </div>
      <p v-if="selectedTemplate" class="dim template-desc">
        {{ selectedTemplate.description }}
      </p>
      <div class="field">
        <label>对话模型</label>
        <select v-model="form.model_key">
          <option value="">（暂不选择，稍后在模型配置中选择）</option>
          <option v-for="m in catalog.models" :key="m.key" :value="m.key">
            {{ m.provider_name }} / {{ m.display_name }}
          </option>
        </select>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="row" style="justify-content: flex-end">
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn primary" :disabled="saving" @click="submit">
          {{ saving ? "创建中…" : "创建" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { apiGet } from "../api/client";
import { useCatalogStore } from "../stores/catalog";
import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const emit = defineEmits(["close", "created"]);
const game = useGameStore();
const catalog = useCatalogStore();
const ui = useUiStore();

const templates = ref([]);
const saving = ref(false);
const error = ref("");
const form = reactive({
  name: "",
  model_key: "",
  character: { name: "", age: 20, relation: "朋友", template_key: "" },
});

const selectedTemplate = computed(() =>
  templates.value.find((t) => t.key === form.character.template_key)
);

onMounted(async () => {
  try {
    if (!catalog.models.length) await catalog.loadModels();
    templates.value = await apiGet("/api/character-templates");
  } catch (e) {
    error.value = e.message;
  }
});

async function submit() {
  error.value = "";
  if (!form.name.trim()) {
    error.value = "请填写存档名";
    return;
  }
  if (!form.character.name.trim()) {
    error.value = "请填写角色名字";
    return;
  }
  if (!form.character.age || form.character.age < 18) {
    error.value = "角色必须年满 18 岁";
    return;
  }
  saving.value = true;
  try {
    const save = await game.createSave({
      name: form.name.trim(),
      model_key: form.model_key,
      character: {
        ...form.character,
        name: form.character.name.trim(),
        persona: selectedTemplate.value ? selectedTemplate.value.persona : {},
      },
    });
    ui.toast("ok", "存档已创建");
    emit("created", save);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.template-desc {
  margin: -6px 0 12px;
  font-size: 12px;
}

.error {
  color: var(--danger);
  margin: 0 0 10px;
}
</style>
