import { defineStore } from "pinia";
import { reactive } from "vue";

import { apiGet } from "../api/client";
import { streamChat } from "../api/sse";
import { useGameStore } from "./game";
import { useUiStore } from "./ui";

let localId = -1;

export const useChatStore = defineStore("chat", {
  state: () => ({
    messages: [],
    streaming: false,
    error: "",
  }),
  actions: {
    async loadMessages(saveId) {
      const data = await apiGet(`/api/saves/${saveId}/messages?limit=200`);
      this.messages = data.messages;
    },
    async send(saveId, text) {
      const content = text.trim();
      if (!content || this.streaming) return;
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
      try {
        await streamChat(saveId, content, {
          chunk: (data) => {
            assistant.content += data.text;
          },
          state_update: (data) => {
            game.applyAttrs(data.attrs);
          },
          time_update: (data) => {
            game.applyTime(data.virtual_label, data.game_minutes);
          },
          done: (data) => {
            assistant.id = data.message_id;
            assistant.meta = data.meta || {};
            assistant.streaming = false;
          },
          error: (data) => {
            this.error = data.message;
            ui.toast("error", data.message);
          },
        });
      } catch (e) {
        this.error = e.message;
        ui.toast("error", e.message);
      } finally {
        assistant.streaming = false;
        this.streaming = false;
      }
    },
  },
});
