<template>
  <div class="input-area">
    <textarea
      v-model="text"
      rows="3"
      placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"
      :disabled="chat.streaming"
      @keydown.enter.exact.prevent="send"
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
  await chat.send(props.saveId, content);
}
</script>

<style scoped>
.input-area {
  display: flex;
  gap: 10px;
  padding: 12px 16px 16px;
  border-top: 1px solid var(--border);
}

textarea {
  flex: 1;
  resize: none;
}

.input-area .btn {
  align-self: flex-end;
  height: 40px;
}
</style>
