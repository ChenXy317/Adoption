<template>
  <div class="input-area">
    <textarea
      v-model="text"
      rows="3"
      placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"
      :disabled="chat.streaming"
      @keydown.enter.exact.prevent="onEnter"
    ></textarea>
    <button
      class="btn primary"
      :disabled="chat.streaming || !text.trim()"
      @click="send"
    >
      {{ chat.streaming ? "生成中…" : "发送" }}
    </button>
  </div>
</template>

<script setup>
import { ref } from "vue";

import { useChatStore } from "../stores/chat";

const props = defineProps({
  saveId: { type: [Number, String], required: true },
});

const chat = useChatStore();
const text = ref("");

async function send() {
  const content = text.value.trim();
  if (!content || chat.streaming) return;
  text.value = "";
  const ok = await chat.send(props.saveId, content);
  if (!ok && !text.value) text.value = content;
}

function onEnter(event) {
  if (event.isComposing) return;
  send();
}
</script>

<style scoped>
.input-area {
  display: flex;
  gap: 12px;
  padding: 14px 18px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-soft);
  border-radius: 0 0 var(--radius) var(--radius);
}

textarea {
  flex: 1;
  resize: none;
  min-height: 72px;
  padding: 10px 12px;
  line-height: 1.55;
  border-radius: var(--radius-xs);
}

.input-area .btn {
  align-self: flex-end;
  min-width: 72px;
  height: 40px;
  padding: 0 18px;
}
</style>
