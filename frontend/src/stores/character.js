import { defineStore } from "pinia";

import { apiGet, apiPatch, apiPost } from "../api/client";

export const useCharacterStore = defineStore("character", {
  state: () => ({
    character: null,
    loaded: false,
  }),
  actions: {
    async load() {
      this.character = await apiGet("/api/character");
      this.loaded = true;
      return this.character;
    },
    async update(payload) {
      this.character = await apiPatch("/api/character", payload);
      this.loaded = true;
      return this.character;
    },
    async reset() {
      this.character = await apiPost("/api/character/reset");
      this.loaded = true;
      return this.character;
    },
  },
});
