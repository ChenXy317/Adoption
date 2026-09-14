import { defineStore } from "pinia";

let nextId = 1;
const THEME_KEY = "new-idea-theme";
const VALID_THEMES = ["dark", "light"];

function storedTheme() {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return VALID_THEMES.includes(value) ? value : "dark";
  } catch {
    return "dark";
  }
}

function applyTheme(name) {
  const root = document.documentElement;
  if (name === "dark") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", name);
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    toasts: [],
    catalogOpen: false,
    theme: storedTheme(),
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
    initTheme() {
      applyTheme(this.theme);
    },
    setTheme(name) {
      const next = VALID_THEMES.includes(name) ? name : "dark";
      this.theme = next;
      applyTheme(next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* 存储不可用时仅当前会话生效 */
      }
    },
  },
});
