import { defineStore } from "pinia";

import { apiGet } from "../api/client";

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
  },
});
