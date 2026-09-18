<template>
  <div class="save-model" :class="{ missing: !currentKey, compact }" @click.stop>
    <label v-if="!compact">对话模型</label>
    <div class="picker">
      <select
        :value="currentKey"
        :disabled="busy || chat.streaming"
        @change="onChange"
      >
        <option value="">未选择模型</option>
        <option v-for="m in catalog.models" :key="m.key" :value="m.key">
          {{ m.provider_name }} / {{ m.display_name }}
        </option>
      </select>
      <button
        v-if="showCatalog"
        type="button"
        class="btn small-btn"
        @click="$emit('open-catalog')"
      >
        配置
      </button>
    </div>
    <p v-if="!compact && !currentKey" class="hint">选好模型后才能对话。</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import { useCatalogStore } from "../stores/catalog";
import { useChatStore } from "../stores/chat";
import { useGameStore } from "../stores/game";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
  modelKey: { type: String, default: "" },
  compact: { type: Boolean, default: false },
  showCatalog: { type: Boolean, default: true },
});
defineEmits(["open-catalog"]);

const catalog = useCatalogStore();
const game = useGameStore();
const chat = useChatStore();
const ui = useUiStore();
const busy = ref(false);

const currentKey = computed(() => props.modelKey || "");

onMounted(async () => {
  try {
    if (!catalog.models.length) await catalog.loadModels();
  } catch (e) {
    ui.toast("error", e.message);
  }
});

async function onChange(event) {
  const value = event.target.value;
  if (value === currentKey.value) return;
  busy.value = true;
  try {
    await game.updateSave(props.saveId, { model_key: value });
    ui.toast("ok", value ? "已为该存档选择模型" : "已清除该存档的模型");
  } catch (e) {
    event.target.value = currentKey.value;
    ui.toast("error", e.message);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.save-model {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.save-model.compact {
  min-width: 0;
}

.picker {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.picker select {
  flex: 1;
  min-width: 0;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--warn);
}

.save-model.missing select {
  border-color: var(--warn);
}
</style>
