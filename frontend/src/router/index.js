import { createRouter, createWebHistory } from "vue-router";

import Home from "../views/Home.vue";
import Game from "../views/Game.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: Home },
    { path: "/game/:id", name: "game", component: Game, props: true },
  ],
});
