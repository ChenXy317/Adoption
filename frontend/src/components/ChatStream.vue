<template>
  <div ref="scrollEl" class="stream">
    <div v-if="chat.hasMore" class="load-earlier">
      <button
        class="btn small"
        :disabled="chat.loadingEarlier"
        @click="loadEarlier"
      >
        {{ chat.loadingEarlier ? "加载中…" : "加载更早的消息" }}
      </button>
    </div>
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

const props = defineProps({
  saveId: { type: [Number, String], required: true },
});

const chat = useChatStore();
const scrollEl = ref(null);

watch(
  () => {
    const last = chat.messages[chat.messages.length - 1];
    return last ? `${last.id}:${last.content.length}` : "";
  },
  async () => {
    await nextTick();
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight;
    }
  }
);

async function loadEarlier() {
  const el = scrollEl.value;
  if (!el) return;
  const beforeHeight = el.scrollHeight;
  const beforeTop = el.scrollTop;
  const count = await chat.loadEarlier(props.saveId);
  await nextTick();
  if (count > 0) {
    el.scrollTop = beforeTop + (el.scrollHeight - beforeHeight);
  }
}
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

.load-earlier {
  display: flex;
  justify-content: center;
}

.small {
  font-size: 12px;
}
</style>
