import { defineStore } from "pinia";
import { reactive } from "vue";

import { apiGet } from "../api/client";
import { streamChat } from "../api/sse";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";

let localId = -1;
let activeController = null;

export const useChatStore = defineStore("chat", {
  state: () => ({
    messages: [],
    streaming: false,
    error: "",
    hasMore: false,
    loadingEarlier: false,
  }),
  actions: {
    async loadMessages(saveId) {
      const data = await apiGet(`/api/saves/${saveId}/messages?limit=200`);
      this.messages = data.messages;
      this.hasMore = Boolean(data.has_more);
    },
    async loadEarlier(saveId) {
      if (!this.hasMore || this.loadingEarlier) return 0;
      const first = this.messages.find((m) => m.id > 0);
      if (!first) return 0;
      this.loadingEarlier = true;
      try {
        const data = await apiGet(
          `/api/saves/${saveId}/messages?limit=200&before_id=${first.id}`
        );
        const known = new Set(this.messages.map((m) => m.id));
        const older = (data.messages || []).filter((m) => !known.has(m.id));
        this.messages.unshift(...older);
        this.hasMore = Boolean(data.has_more);
        return older.length;
      } finally {
        this.loadingEarlier = false;
      }
    },
    pushMessages(list) {
      for (const message of list || []) {
        if (!message || message.id == null) continue;
        if (this.messages.some((m) => m.id === message.id)) continue;
        this.messages.push(message);
      }
    },
    cancel() {
      if (activeController) activeController.abort();
    },
    _dropMessage(message) {
      const index = this.messages.indexOf(message);
      if (index >= 0) this.messages.splice(index, 1);
    },
    async send(saveId, text) {
      const content = text.trim();
      if (!content || this.streaming) return true;
      const game = useGameStore();
      const ui = useUiStore();
      this.error = "";
      this.messages.push({
        id: localId--,
        role: "user",
        content,
        meta: {},
      });
      const assistant = reactive({
        id: localId--,
        role: "assistant",
        content: "",
        meta: {},
        streaming: true,
      });
      this.messages.push(assistant);
      this.streaming = true;
      const controller = new AbortController();
      activeController = controller;
      let settled = false;
      let hadText = false;
      let eventTriggered = false;
      let sceneChanged = false;
      try {
        await streamChat(
          saveId,
          content,
          {
            chunk: (data) => {
              assistant.content += data.text;
            },
            state_update: (data) => {
              game.applyAttrs(data.attrs, data.phase, data);
            },
            event_triggered: (data) => {
              eventTriggered = true;
              this.pushMessages(data.messages);
            },
            scene_update: () => {
              sceneChanged = true;
            },
            time_update: (data) => {
              game.applyTime(data);
            },
            done: (data) => {
              settled = true;
              if (data.message_id == null) {
                this._dropMessage(assistant);
              } else {
                assistant.id = data.message_id;
                assistant.meta = data.meta || {};
                assistant.streaming = false;
              }
            },
            error: (data) => {
              this.error = data.message;
              ui.toast("error", data.message);
            },
          },
          controller.signal
        );
      } catch (e) {
        if (e.name !== "AbortError") {
          this.error = e.message;
          ui.toast("error", e.message);
        }
      } finally {
        if (activeController === controller) activeController = null;
        assistant.streaming = false;
        this.streaming = false;
        hadText = Boolean(assistant.content.trim());
        if (assistant.id < 0 && !hadText) this._dropMessage(assistant);
        if (settled || eventTriggered || sceneChanged || hadText) {
          game.loadState(saveId).catch(() => {});
        }
      }
      return settled || hadText;
    },
  },
});
