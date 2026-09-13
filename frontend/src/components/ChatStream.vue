<template>
  <div ref="scrollEl" class="stream">
    <div v-if="!chat.messages.length" class="empty dim">
      还没有对话，说点什么吧。
    </div>
    <MessageBubble
      v-for="m in chat.messages"
      :key="m.id"
      :message="m"
    />
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";

import MessageBubble from "./MessageBubble.vue";
import { useChatStore } from "../stores/chat";

const chat = useChatStore();
const scrollEl = ref(null);

watch(
  () => chat.messages.map((m) => m.content.length).join(","),
  async () => {
    await nextTick();
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight;
    }
  }
);
</script>

<style scoped>
.stream {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
}

.empty {
  text-align: center;
  margin-top: 40px;
}
</style>
