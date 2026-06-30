<template>
  <div class="dashboard">
    <!-- Loading -->
    <div v-if="loading" class="loading-wrap">
      <van-loading type="spinner" size="32" color="#667eea" />
      <p class="loading-text">加载中...</p>
    </div>

    <template v-else>
      <!-- Stats Row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value">{{ fmt(totalProjects) }}</div>
          <div class="stat-label">总项目数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value stat-warn">{{ fmt(changedCount) }}</div>
          <div class="stat-label">有变更</div>
        </div>
        <div class="stat-card">
          <div class="stat-value stat-primary">{{ fmt(todayPushes) }}</div>
          <div class="stat-label">今日推送</div>
        </div>
      </div>

      <!-- Batch Push -->
      <div class="batch-section">
        <van-button
          type="primary"
          block
          round
          :loading="batchLoading"
          loading-text="全量推送中..."
          @click="batchPushAll"
          class="batch-btn"
        >
          ⚡ 一键全推送
        </van-button>
      </div>

      <!-- Project List -->
      <div class="section-title">
        <span>项目列表</span>
        <van-button
          size="small"
          icon="replay"
          round
          plain
          hairline
          @click="loadProjects"
          class="refresh-btn"
        />
      </div>

      <div v-if="projects.length === 0" class="empty-state">
        <van-empty description="暂无项目" />
      </div>

      <van-cell-group v-else inset>
        <van-cell
          v-for="p in projects"
          :key="p.id"
          :border="true"
          class="project-cell"
        >
          <template #title>
            <div class="cell-title-row">
              <van-tag
                :type="typeTagColor(p.type)"
                size="medium"
                class="type-tag"
              >
                {{ p.type }}
              </van-tag>
              <span class="project-name">{{ p.name }}</span>
            </div>
          </template>

          <template #label>
            <div class="cell-body">
              <div class="cell-meta">
                <span class="project-path" :title="p.path">{{ truncate(p.path, 40) }}</span>
                <span
                  class="git-dot"
                  :style="{ color: getStatusColor(p) }"
                  :title="getStatusTitle(p)"
                >●</span>
              </div>
              <div class="url-row">
                <span class="url-label">🌐</span>
                <a v-if="p.deploy_url" :href="p.deploy_url" target="_blank" class="url-link">{{ p.deploy_url }}</a>
                <span v-else class="url-link url-empty">未配置</span>
                <van-button v-if="p.deploy_url" size="small" type="primary" class="copy-btn" @click.stop="copyUrl(p.deploy_url)">📋 复制</van-button>
              </div>
              <div class="url-row">
                <span class="url-label">🐙</span>
                <a v-if="p.remote_url" :href="githubUrl(p.remote_url)" target="_blank" class="url-link">{{ p.remote_url }}</a>
                <span v-else class="url-link url-empty">未配置</span>
                <van-button v-if="p.remote_url" size="small" type="primary" class="copy-btn" @click.stop="copyUrl(p.remote_url)">📋 复制</van-button>
              </div>
              <div class="cell-actions">
                <van-button
                  size="mini"
                  icon="description-o"
                  round
                  plain
                  hairline
                  type="default"
                  @click.stop="goDocs(p.id)"
                >文档</van-button>
                <van-button
                  size="mini"
                  icon="down"
                  round
                  plain
                  hairline
                  type="primary"
                  :loading="p._pulling"
                  @click.stop="doPull(p.id)"
                >拉取</van-button>
                <van-button
                  size="mini"
                  icon="arrow-up"
                  round
                  plain
                  hairline
                  type="danger"
                  :loading="p._pushing"
                  @click.stop="doPush(p.id)"
                >推送</van-button>
              </div>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import api from '../api.js'

const router = useRouter()

// ── State ──────────────────────────────────
const loading = ref(true)
const batchLoading = ref(false)
const projects = ref([])
const logs = ref([])

// ── Computed ───────────────────────────────
const totalProjects = computed(() => projects.value.length)

const changedCount = computed(() =>
  projects.value.filter(p => p.status && !p.status.clean).length
)

const todayPushes = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return logs.value.filter(l => l.action === 'push' && l.created_at?.startsWith(today)).length
})

// ── Helpers ────────────────────────────────
const fmt = (n) => (n ?? 0).toLocaleString()

const truncate = (str, len) => {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

const githubUrl = (remote) => {
  if (!remote) return ''
  // git@github.com:user/repo.git → https://github.com/user/repo
  // https://github.com/user/repo.git → https://github.com/user/repo
  const m = remote.match(/github\.com[:/](.+?)(?:\.git)?$/)
  return m ? 'https://github.com/' + m[1] : remote
}

const typeTagColor = (type) => {
  const map = { code: 'primary', docs: 'success', static: 'warning', nav_page: 'danger' }
  return map[type] || 'default'
}

const getStatusColor = (p) => {
  if (!p.is_git || !p.exists) return '#999'
  if (p.status && !p.status.clean) return '#f59e0b'
  return '#22c55e'
}

const getStatusTitle = (p) => {
  if (!p.is_git || !p.exists) return '非 Git 仓库'
  if (p.status && !p.status.clean) return `${p.status.total_changes} 个变更`
  return '干净'
}

// ── Data Loading ───────────────────────────
async function loadProjects() {
  loading.value = true
  try {
    const [projRes, logRes] = await Promise.all([
      api.get('/projects'),
      api.get('/logs', { params: { limit: 200 } }),
    ])
    projects.value = (projRes.data.projects || []).map(p => ({
      ...p,
      _pushing: false,
      _pulling: false,
    }))
    logs.value = logRes.data.logs || []
  } catch (e) {
    showFailToast('加载失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ── Actions ────────────────────────────────
function goDocs(pid) {
  router.push(`/docs/${pid}`)
}

async function doPull(pid) {
  const proj = projects.value.find(p => p.id === pid)
  if (!proj) return
  proj._pulling = true
  try {
    const res = await api.post(`/projects/${pid}/pull`)
    if (res.data.ok) {
      showSuccessToast('拉取成功')
    } else {
      showFailToast(res.data.output || '拉取失败')
    }
  } catch (e) {
    showFailToast('拉取出错')
  } finally {
    proj._pulling = false
  }
}

async function doPush(pid) {
  const proj = projects.value.find(p => p.id === pid)
  if (!proj) return
  proj._pushing = true
  try {
    const res = await api.post(`/projects/${pid}/push`, null, {
      params: { message: 'update' },
    })
    if (res.data.ok) {
      showSuccessToast('推送成功')
      // Refresh to update status
      await loadProjects()
    } else {
      showFailToast('推送失败')
    }
  } catch (e) {
    showFailToast('推送出错')
  } finally {
    proj._pushing = false
  }
}

async function batchPushAll() {
  if (projects.value.length === 0) {
    showToast('没有项目可推送')
    return
  }
  batchLoading.value = true
  try {
    const res = await api.post('/projects/batch-push', null, {
      params: { message: '一键全推送' },
    })
    if (res.data.ok) {
      showSuccessToast(`已推送 ${Object.keys(res.data.results || {}).length} 个项目`)
      await loadProjects()
    } else {
      showFailToast('批量推送失败')
    }
  } catch (e) {
    showFailToast('推送出错')
  } finally {
    batchLoading.value = false
  }
}

// ── Copy URL ───────────────────────────────
async function copyUrl(url) {
  try {
    await navigator.clipboard.writeText(url)
    showSuccessToast('已复制到剪贴板')
  } catch {
    // Fallback for non-HTTPS or older browsers
    const ta = document.createElement('textarea')
    ta.value = url
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    showSuccessToast('已复制')
  }
}

// ── Init ───────────────────────────────────
onMounted(loadProjects)
</script>

<style scoped>
.dashboard {
  padding: 16px 16px 80px;
  min-height: 100vh;
  background: var(--bg-page);
}

/* ── Loading ─────────────────────────────── */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: 40vh;
  gap: 12px;
}
.loading-text {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0;
}

/* ── Stats Row ───────────────────────────── */
.stats-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.stat-card {
  flex: 1;
  min-width: 0;
  background: var(--bg-card);
  border-radius: 12px;
  padding: 12px 8px;
  text-align: center;
  box-shadow: var(--shadow);
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.stat-value.stat-warn {
  color: var(--warn);
}
.stat-value.stat-primary {
  color: var(--accent);
}
.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* ── Batch Button ────────────────────────── */
.batch-section {
  margin-bottom: 20px;
}
.batch-btn {
  --van-button-primary-background: var(--accent-gradient);
  --van-button-primary-border-color: transparent;
  font-size: 16px;
  font-weight: 600;
  height: 48px;
  letter-spacing: 1px;
}

/* ── Section Title ───────────────────────── */
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
  padding: 0 4px;
}
.refresh-btn {
  --van-button-small-height: 26px;
  --van-button-small-font-size: 12px;
}

/* ── Project Cell ────────────────────────── */
.project-cell {
  --van-cell-padding: 12px 16px;
  --van-cell-label-margin-top: 6px;
}
.cell-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.type-tag {
  flex-shrink: 0;
  font-size: 10px !important;
  --van-tag-medium-padding: 2px 6px;
}
.project-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cell-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.project-path {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--monospace);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}
.git-dot {
  font-size: 14px;
  flex-shrink: 0;
  transition: color 0.2s;
}
.cell-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.cell-actions .van-button {
  --van-button-mini-height: 28px;
  --van-button-mini-font-size: 11px;
  --van-button-mini-padding: 0 12px;
}

/* ── URL Row (deploy & github) ──────────── */
.url-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  background: var(--bg-page);
  border-radius: 6px;
  min-width: 0;
}
.url-label {
  font-size: 13px;
  flex-shrink: 0;
}
.url-link {
  flex: 1;
  min-width: 0;
  max-width: 75%;
  font-size: 11px;
  color: var(--text-muted);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--monospace);
}
.url-link[href] {
  color: var(--accent);
}
.url-link[href]:active {
  opacity: 0.7;
}
.url-empty {
  color: var(--text-muted);
  font-style: italic;
  opacity: 0.5;
}
.copy-btn {
  flex-shrink: 0;
  --van-button-small-height: 28px;
  --van-button-small-font-size: 12px;
  --van-button-small-padding: 0 10px;
}

/* ── Empty State ─────────────────────────── */
.empty-state {
  padding: 40px 0;
}

/* ── Override van-cell-group inset ───────── */
:deep(.van-cell-group--inset) {
  margin: 0;
}
</style>
