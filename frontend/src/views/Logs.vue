<template>
  <div class="logs-page">
    <div class="header-bar">
      <h2>📋 操作日志</h2>
      <select v-model="filterPid" @change="loadLogs">
        <option :value="null">全部项目</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
    </div>

    <van-loading v-if="loading" class="center-loading" />

    <template v-else>
      <div v-if="logs.length === 0" class="empty">暂无日志</div>

      <div v-for="log in logs" :key="log.id" class="log-entry">
        <div class="log-action">
          <span class="log-icon">{{ actionIcon(log.action) }}</span>
          <span class="log-project">{{ log.project_name || '—' }}</span>
        </div>
        <div class="log-body">
          <div class="log-msg">{{ log.message }}</div>
          <div v-if="log.detail" class="log-detail">{{ log.detail }}</div>
        </div>
        <div class="log-meta">
          <span class="log-time">{{ fmtTime(log.created_at) }}</span>
          <span class="log-status" :class="log.status">{{ log.status === 'ok' ? '✓' : '✗' }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '../api.js'

const logs = ref([])
const projects = ref([])
const filterPid = ref(null)
const loading = ref(false)
let timer = null

function actionIcon(action) {
  const map = { push: '📤', pull: '📥', add: '➕', edit: '✏️', delete: '🗑️', doc_save: '💾', doc_create: '📝', doc_delete: '❌' }
  return map[action] || '📌'
}

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts.replace(' ', 'T'))
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return ts.slice(5, 16)
}

async function loadLogs() {
  loading.value = true
  try {
    const params = filterPid.value ? { project_id: filterPid.value } : {}
    const res = await api.get('/logs', { params })
    logs.value = res.data.logs || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const res = await api.get('/projects')
    projects.value = res.data.projects || []
  } catch (e) { console.error(e) }
}

onMounted(() => {
  loadProjects()
  loadLogs()
  timer = setInterval(loadLogs, 30000)
})

onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.logs-page { padding: 12px 8px 80px; background: #f5f7fa; min-height: 100vh; }
.header-bar { display: flex; justify-content: space-between; align-items: center; padding: 8px 8px 12px; }
.header-bar h2 { font-size: 18px; font-weight: 700; color: #0a1628; margin: 0; }
.header-bar select { font-size: 12px; border: 1px solid #ddd; border-radius: 8px; padding: 4px 8px; background: #fff; }
.center-loading { display: flex; justify-content: center; padding: 60px 0; }
.empty { text-align: center; color: #8899bb; padding: 60px 0; font-size: 14px; }

.log-entry {
  display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px;
  background: #fff; border-radius: 10px; margin-bottom: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,.03);
}
.log-action { display: flex; align-items: center; gap: 4px; flex-shrink: 0; min-width: 80px; }
.log-icon { font-size: 16px; }
.log-project { font-size: 11px; font-weight: 600; color: #1989fa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70px; }
.log-body { flex: 1; min-width: 0; }
.log-msg { font-size: 13px; color: #334155; }
.log-detail { font-size: 10px; color: #8899bb; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; }
.log-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
.log-time { font-size: 10px; color: #b0bec5; white-space: nowrap; }
.log-status { font-size: 12px; font-weight: 700; }
.log-status.ok { color: #07c160; }
.log-status.error { color: #ee0a24; }
</style>
