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
    <div v-if="!chat.messages.length" class="empty">
      <div class="empty-orb" aria-hidden="true">✦</div>
      <p class="empty-text dim">还没有对话，说点什么吧。</p>
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
  gap: 16px;
  padding: 22px 24px;
  background: transparent;
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 22px,
    #000 calc(100% - 4px),
    transparent 100%
  );
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    #000 22px,
    #000 calc(100% - 4px),
    transparent 100%
  );
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 64px;
}

.empty-orb {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  font-size: 22px;
  color: var(--accent-hover);
  background: radial-gradient(circle at 32% 28%, rgba(240, 171, 252, 0.35), rgba(139, 92, 246, 0.12) 62%);
  border: 1px solid var(--accent-border);
  box-shadow: 0 0 34px -6px rgba(167, 139, 250, 0.8);
  text-shadow: 0 0 18px rgba(240, 171, 252, 0.95);
  animation: floatY 4.5s ease-in-out infinite;
}

.empty-text {
  margin: 0;
  font-size: 13px;
  letter-spacing: 0.05em;
}

.load-earlier {
  display: flex;
  justify-content: center;
  margin-bottom: 4px;
}

.small {
  font-size: 12px;
}

/* ── 移动端：减小留白，消息更紧凑 ── */
@media (max-width: 768px) {
  .stream {
    gap: 12px;
    padding: 14px 12px;
    /* 顶部渐隐区收窄，首屏多显示一行 */
    -webkit-mask-image: linear-gradient(
      to bottom,
      transparent 0,
      #000 12px,
      #000 calc(100% - 4px),
      transparent 100%
    );
    mask-image: linear-gradient(
      to bottom,
      transparent 0,
      #000 12px,
      #000 calc(100% - 4px),
      transparent 100%
    );
  }

  .empty {
    margin-top: 40px;
  }
}
</style>
