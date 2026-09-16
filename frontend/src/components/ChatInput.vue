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
  position: relative;
  display: flex;
  gap: 12px;
  padding: 14px 18px 16px;
  border-top: 1px solid transparent;
  background: color-mix(in srgb, var(--bg-soft) 76%, transparent);
  backdrop-filter: blur(14px) saturate(1.2);
  border-radius: 0 0 var(--radius) var(--radius);
}

.input-area::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(139, 92, 246, 0.5),
    rgba(232, 121, 249, 0.4),
    transparent
  );
  pointer-events: none;
}

textarea {
  flex: 1;
  resize: none;
  min-height: 72px;
  padding: 10px 12px;
  line-height: 1.55;
  border-radius: var(--radius-xs);
  background: color-mix(in srgb, var(--bg) 68%, transparent);
}

textarea:focus {
  box-shadow: 0 0 0 3px var(--accent-soft), 0 0 30px -8px var(--accent);
}

.input-area .btn {
  align-self: flex-end;
  min-width: 72px;
  height: 40px;
  padding: 0 18px;
}

/* ── 移动端：输入区粘底 + 安全区 + 大按钮 ── */
@media (max-width: 768px) {
  .input-area {
    position: sticky;
    bottom: 0;
    gap: 8px;
    padding: 10px 10px calc(10px + env(safe-area-inset-bottom, 0px));
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  }

  textarea {
    min-height: 44px;
    max-height: 32vh;
    max-height: 32dvh;
    padding: 10px;
    line-height: 1.5;
  }

  .input-area .btn {
    min-width: 64px;
    min-height: 44px;
    height: 44px;
    padding: 0 14px;
    flex-shrink: 0;
  }
}
</style>
