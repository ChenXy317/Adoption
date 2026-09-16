import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import { useUiStore } from "./stores/ui";
import "./styles/base.css";

/** 把真实可见区域写入 CSS 变量，避开移动端浏览器工具栏造成的 vh 偏差。 */
function syncVisualViewport() {
  const vp = window.visualViewport;
  const root = document.documentElement;
  const height = vp ? vp.height : window.innerHeight;
  const top = vp ? vp.offsetTop : 0;
  root.style.setProperty("--vvh", `${Math.round(height)}px`);
  root.style.setProperty("--vv-top", `${Math.round(top)}px`);
}

syncVisualViewport();
window.addEventListener("resize", syncVisualViewport);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", syncVisualViewport);
  window.visualViewport.addEventListener("scroll", syncVisualViewport);
}

const app = createApp(App);
app.use(createPinia());
app.use(router);
useUiStore().initTheme();
app.mount("#app");
