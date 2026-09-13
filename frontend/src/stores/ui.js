import { defineStore } from "pinia";

let nextId = 1;

export const useUiStore = defineStore("ui", {
  state: () => ({
    toasts: [],
    catalogOpen: false,
  }),
  actions: {
    toast(type, text, timeout = 3600) {
      const id = nextId++;
      this.toasts.push({ id, type, text });
      setTimeout(() => this.dismiss(id), timeout);
    },
    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id);
    },
  },
});
