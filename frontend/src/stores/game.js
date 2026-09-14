import { defineStore } from "pinia";

import { apiDelete, apiGet, apiPatch, apiPost } from "../api/client";

export const useGameStore = defineStore("game", {
  state: () => ({
    saves: [],
    current: null,
    loading: false,
  }),
  actions: {
    async loadSaves() {
      this.loading = true;
      try {
        this.saves = await apiGet("/api/saves");
      } finally {
        this.loading = false;
      }
    },
    async createSave(payload) {
      const save = await apiPost("/api/saves", payload);
      await this.loadSaves();
      return save;
    },
    async deleteSave(id) {
      await apiDelete(`/api/saves/${id}`);
      this.saves = this.saves.filter((s) => s.id !== id);
    },
    async renameSave(id, patch) {
      await apiPatch(`/api/saves/${id}`, patch);
      await this.loadSaves();
    },
    async loadState(id) {
      this.current = await apiGet(`/api/saves/${id}/state`);
    },
    async advance(id, payload) {
      return apiPost(`/api/saves/${id}/advance`, payload);
    },
    async triggerManual(id, key) {
      return apiPost(`/api/saves/${id}/events/${encodeURIComponent(key)}/trigger`);
    },
    applyAttrs(changes, phase = null) {
      if (!this.current) return;
      for (const change of changes || []) {
        const attr = this.current.attributes.find((a) => a.key === change.key);
        if (attr) attr.value = change.new;
      }
      const money = this.current.attributes.find((a) => a.key === "money");
      if (money) this.current.money = money.value;
      if (phase) this.current.phase = phase;
    },
    applyTime({ virtual, game_minutes } = {}) {
      if (!this.current) return;
      if (virtual) this.current.virtual = virtual;
      if (game_minutes != null) this.current.save.game_minutes = game_minutes;
    },
  },
});
