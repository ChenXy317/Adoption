import { defineStore } from "pinia";
import { reactive } from "vue";

import { apiGet } from "../api/client";
import { streamChat } from "../api/sse";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";

let localId = -1;
let activeController = null;
let messagesAbort = null;

export const useChatStore = defineStore("chat", {
  state: () => ({
    boundSaveId: null,
    messages: [],
    streaming: false,
    error: "",
    hasMore: false,
    loadingEarlier: false,
  }),
  actions: {
    _isCurrent(saveId) {
      return this.boundSaveId != null && Number(this.boundSaveId) === Number(saveId);
    },
    resetForSave(saveId) {
      this.cancel();
      messagesAbort?.abort();
      this.boundSaveId = saveId == null ? null : Number(saveId);
      this.messages = [];
      this.streaming = false;
      this.error = "";
      this.hasMore = false;
      this.loadingEarlier = false;
    },
    async loadMessages(saveId) {
      messagesAbort?.abort();
      const controller = new AbortController();
      messagesAbort = controller;
      try {
        const data = await apiGet(
          `/api/saves/${saveId}/messages?limit=200`,
          controller.signal
        );
        if (!this._isCurrent(saveId) || messagesAbort !== controller) return;
        this.messages = data.messages;
        this.hasMore = Boolean(data.has_more);
      } catch (e) {
        if (e.name === "AbortError") return;
        throw e;
      }
    },
    async loadEarlier(saveId) {
      if (!this.hasMore || this.loadingEarlier || !this._isCurrent(saveId)) return 0;
      const first = this.messages.find((m) => m.id > 0);
      if (!first) return 0;
      this.loadingEarlier = true;
      try {
        const data = await apiGet(
          `/api/saves/${saveId}/messages?limit=200&before_id=${first.id}`
        );
        if (!this._isCurrent(saveId)) return 0;
        const known = new Set(this.messages.map((m) => m.id));
        const older = (data.messages || []).filter((m) => !known.has(m.id));
        this.messages.unshift(...older);
        this.hasMore = Boolean(data.has_more);
        return older.length;
      } catch (e) {
        if (e.name !== "AbortError") {
          useUiStore().toast("error", e.message);
        }
        return 0;
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
      if (!this._isCurrent(saveId)) return false;
      const game = useGameStore();
      const ui = useUiStore();
      this.error = "";
      const userMsg = {
        id: localId--,
        role: "user",
        content,
        meta: {},
      };
      this.messages.push(userMsg);
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
              if (!this._isCurrent(saveId)) return;
              assistant.content += data.text;
            },
            state_update: (data) => {
              if (!this._isCurrent(saveId)) return;
              game.applyAttrs(data.attrs, data.phase, data);
            },
            event_triggered: (data) => {
              if (!this._isCurrent(saveId)) return;
              eventTriggered = true;
              this.pushMessages(data.messages);
            },
            scene_update: () => {
              if (!this._isCurrent(saveId)) return;
              sceneChanged = true;
            },
            time_update: (data) => {
              if (!this._isCurrent(saveId)) return;
              game.applyTime(data);
            },
            done: (data) => {
              if (!this._isCurrent(saveId)) return;
              settled = true;
              if (data.user_message_id != null) userMsg.id = data.user_message_id;
              if (data.message_id == null) {
                this._dropMessage(assistant);
              } else {
                assistant.id = data.message_id;
                assistant.meta = data.meta || {};
                assistant.streaming = false;
              }
            },
            error: (data) => {
              if (!this._isCurrent(saveId)) return;
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
        if (this._isCurrent(saveId)) this.streaming = false;
        hadText = Boolean(assistant.content.trim());
        if (assistant.id < 0 && !hadText) this._dropMessage(assistant);
        if (!settled && !hadText) this._dropMessage(userMsg);
        if (this._isCurrent(saveId) && (settled || eventTriggered || sceneChanged || hadText)) {
          game.loadState(saveId).catch(() => {});
        }
        if (this._isCurrent(saveId) && hadText && !settled) {
          this.loadMessages(saveId).catch(() => {});
        }
      }
      return settled || hadText;
    },
  },
});
