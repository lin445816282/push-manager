<template>
  <div>
    <!-- Theme Toggle -->
    <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切到浅色' : '切到深色'">
      {{ isDark ? '🌙' : '☀️' }}
    </button>

    <router-view />
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">仪表盘</van-tabbar-item>
      <van-tabbar-item icon="orders-o" to="/projects">项目</van-tabbar-item>
      <van-tabbar-item icon="shield-o" to="/self">自保</van-tabbar-item>
      <van-tabbar-item icon="description-o" to="/logs">日志</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
const active = ref(0)

// ═══ Theme ════════════════════════════════════
const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
}

function applyTheme() {
  const theme = isDark.value ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('push-manager-theme', theme)
}

watch(isDark, applyTheme)

onMounted(() => {
  const saved = localStorage.getItem('push-manager-theme')
  if (saved === 'dark') {
    isDark.value = true
  } else {
    applyTheme() // ensure light is set
  }
})
</script>
