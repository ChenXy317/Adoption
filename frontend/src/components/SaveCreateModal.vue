<template>
  <Teleport to="body">
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <h2>新建存档（新周目）</h2>
      <div class="card character-card">
        <div>{{ characterLine }}</div>
        <div class="dim small">所有存档共用同一位女主角。选择开场阶段后，关系从那个时刻开始。</div>
      </div>
      <div class="field">
        <label>开场阶段</label>
        <div class="opening-grid">
          <button
            v-for="item in openings"
            :key="item.key"
            type="button"
            class="opening-card"
            :class="{ active: form.opening_key === item.key }"
            @click="form.opening_key = item.key"
          >
            <strong>{{ item.name }}</strong>
            <span class="dim small meta">{{ item.time_label }} · {{ item.phase }}</span>
            <span class="dim small blurb">{{ item.blurb }}</span>
          </button>
        </div>
      </div>
      <div class="field">
        <label>存档名</label>
        <input v-model="form.name" placeholder="例如：和她的日常" />
      </div>
      <div class="field">
        <label>对话模型</label>
        <select v-model="form.model_key">
          <option value="">（暂不选择，进入存档后再选）</option>
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
  </Teleport>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { apiGet } from "../api/client";
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
const openings = ref([]);
const form = reactive({ name: "", model_key: "", opening_key: "rain_night" });

const characterLine = computed(() => {
  const ch = character.character;
  if (!ch) return "尚未创建女主角设定书";
  return `${ch.name} · ${ch.age} 岁${ch.relation ? ` · ${ch.relation}` : ""}`;
});

onMounted(async () => {
  try {
    const jobs = [];
    if (!catalog.models.length) jobs.push(catalog.loadModels());
    if (!character.loaded) jobs.push(character.load());
    jobs.push(
      apiGet("/api/openings").then((data) => {
        openings.value = Array.isArray(data) ? data : [];
        if (
          openings.value.length &&
          !openings.value.some((item) => item.key === form.opening_key)
        ) {
          form.opening_key = openings.value[0].key;
        }
      })
    );
    await Promise.all(jobs);
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
      opening_key: form.opening_key,
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
  position: relative;
  overflow: hidden;
  padding: 12px 14px;
  margin-bottom: 14px;
  background: linear-gradient(125deg, rgba(139, 92, 246, 0.14), rgba(232, 121, 249, 0.08)), var(--panel);
  border-color: var(--accent-border);
  box-shadow: var(--glow-soft);
}

.character-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 10%;
  bottom: 10%;
  width: 3px;
  border-radius: 3px;
  background: var(--grad-primary);
  box-shadow: 0 0 14px 1px rgba(139, 92, 246, 0.9);
}

.character-card > div:first-child {
  font-weight: 600;
}

.opening-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.opening-card {
  appearance: none;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--panel-2) 55%, transparent);
  color: var(--text);
  transition: border-color var(--ease), box-shadow var(--ease), background var(--ease);
}

.opening-card .meta {
  letter-spacing: 0.02em;
}

.opening-card .blurb {
  line-height: 1.5;
}

.opening-card:hover {
  border-color: var(--accent-border);
}

.opening-card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: var(--glow-soft);
}

.error {
  color: var(--danger);
  margin: 0 0 10px;
}

.small {
  font-size: 12px;
}

@media (max-width: 768px) {
  .opening-grid {
    grid-template-columns: 1fr;
  }

  .opening-card {
    min-height: 44px;
  }
}
</style>
