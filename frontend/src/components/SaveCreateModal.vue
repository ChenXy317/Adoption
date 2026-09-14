<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <h2>新建存档（新周目）</h2>
      <div class="card character-card">
        <div>{{ characterLine }}</div>
        <div class="dim small">所有存档共用同一位女主角，新存档从头开始这段关系。</div>
      </div>
      <div class="field">
        <label>存档名</label>
        <input v-model="form.name" placeholder="例如：和她的日常" />
      </div>
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

import { useCatalogStore } from "../stores/catalog";
import { useCharacterStore } from "../stores/character";
import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const emit = defineEmits(["close", "created"]);
const game = useGameStore();
const catalog = useCatalogStore();
const character = useCharacterStore();
const ui = useUiStore();

const saving = ref(false);
const error = ref("");
const form = reactive({ name: "", model_key: "" });

const characterLine = computed(() => {
  const ch = character.character;
  if (!ch) return "尚未创建女主角设定书";
  return `${ch.name} · ${ch.age} 岁${ch.relation ? ` · ${ch.relation}` : ""}`;
});

onMounted(async () => {
  try {
    if (!catalog.models.length) await catalog.loadModels();
    if (!character.loaded) await character.load();
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
  saving.value = true;
  try {
    const save = await game.createSave({
      name: form.name.trim(),
      model_key: form.model_key,
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
.character-card {
  padding: 10px 12px;
  margin-bottom: 14px;
}

.error {
  color: var(--danger);
  margin: 0 0 10px;
}

.small {
  font-size: 12px;
}
</style>
