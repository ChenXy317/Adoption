<template>
  <div class="ambient" aria-hidden="true">
    <span class="meteor meteor-a"></span>
    <span class="meteor meteor-b"></span>
    <span class="spark spark-a"></span>
    <span class="spark spark-b"></span>
    <span class="spark spark-c"></span>
  </div>
  <router-view />
  <ToastHost />
</template>

<script setup>
import ToastHost from "./components/ToastHost.vue";
</script>

<style>
/* 全局氛围层：流星与漂浮光点，仅作装饰 */
.ambient {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.meteor {
  position: absolute;
  width: 170px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(226, 232, 255, 0.95));
  filter: drop-shadow(0 0 6px rgba(167, 139, 250, 0.95));
  opacity: 0;
  animation: meteor 14s linear infinite;
}

.meteor-a {
  top: 6%;
  right: 4%;
  animation-delay: 2.5s;
  animation-duration: 13s;
}

.meteor-b {
  top: 30%;
  right: 34%;
  animation-delay: 9s;
  animation-duration: 17s;
  width: 120px;
  height: 1.5px;
  opacity: 0;
}

.spark {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(232, 121, 249, 0.95), rgba(139, 92, 246, 0));
  filter: blur(0.5px);
  animation: floatY 7s ease-in-out infinite;
}

.spark-a {
  top: 22%;
  left: 8%;
  animation-delay: 0s;
}

.spark-b {
  top: 68%;
  right: 10%;
  width: 6px;
  height: 6px;
  animation-delay: 1.8s;
  animation-duration: 9s;
}

.spark-c {
  top: 46%;
  left: 46%;
  width: 3px;
  height: 3px;
  animation-delay: 3.4s;
  animation-duration: 6s;
}

html[data-theme="light"] .meteor {
  background: linear-gradient(90deg, rgba(124, 58, 237, 0), rgba(124, 58, 237, 0.7));
  filter: drop-shadow(0 0 5px rgba(124, 58, 237, 0.6));
}
</style>
