<template>
  <div class="self-page">
    <!-- Loading -->
    <van-loading v-if="loading" class="loading-center" type="spinner" size="32" color="#667eea" />

    <template v-else>
      <!-- ══════ 管理器状态卡片 ══════ -->
      <div class="status-card">
        <div class="status-header">
          <van-icon :name="selfStatus.is_git ? 'success' : 'warning-o'" :color="selfStatus.is_git ? '#22c55e' : '#f59e0b'" />
          <span class="status-title">管理器仓库状态</span>
        </div>
        <div class="status-body" v-if="selfStatus.is_git">
          <div class="status-row">
            <span class="status-label">当前分支</span>
            <van-tag type="primary" size="medium">{{ selfStatus.branch || 'unknown' }}</van-tag>
          </div>
          <div class="status-row">
            <span class="status-label">远程数</span>
            <span class="status-value">{{ selfStatus.remote_count }}</span>
          </div>
          <div class="status-row">
            <span class="status-label">变更文件</span>
            <span class="status-value" :class="{ 'has-changes': selfStatus.status && !selfStatus.status.clean }">
              {{ selfStatus.status && selfStatus.status.total_changes || 0 }} 个
            </span>
          </div>
          <div class="status-row" v-if="selfStatus.remotes.length">
            <span class="status-label">远程仓库</span>
          </div>
          <div class="remote-list" v-if="selfStatus.remotes.length">
            <div v-for="r in selfStatus.remotes" :key="r.name" class="remote-item">
              <span class="remote-name">{{ r.name }}</span>
              <span class="remote-url">{{ r.url }}</span>
            </div>
          </div>
        </div>
        <div v-else class="status-body">
          <p class="no-git-msg">{{ selfStatus.message }}</p>
        </div>
      </div>

      <!-- ══════ 一键推送管理器 ══════ -->
      <div class="batch-section">
        <van-button
          type="primary"
          block
          round
          :loading="pushLoading"
          loading-text="推送中..."
          @click="doSelfPush"
          :disabled="!selfStatus.is_git"
        >
          ⚡ 推送管理器到所有远程
        </van-button>
      </div>

      <!-- ══════ 多远程配置 ══════ -->
      <van-cell-group inset title="多远程配置">
        <div v-if="remotes.length === 0" class="empty-hint">
          <van-icon name="info-o" />
          <span>暂无远程仓库，添加后一键同步</span>
        </div>
        <van-cell
          v-for="r in remotes"
          :key="r.id"
          :title="r.name"
          :label="r.url"
        >
          <template #right-icon>
            <div class="remote-actions">
              <van-button
                size="mini"
                type="primary"
                round
                plain
                hairline
                @click.stop="syncRemote(r.id)"
                :loading="syncLoading[r.id]"
              >
                同步
              </van-button>
              <van-button
                size="mini"
                round
                plain
                hairline
                type="danger"
                @click.stop="confirmDelRemote(r)"
              >
                删
              </van-button>
            </div>
          </template>
        </van-cell>
        <div class="cell-footer">
          <van-button size="small" icon="plus" round plain hairline @click="showRemoteForm = true">
            添加远程
          </van-button>
        </div>
      </van-cell-group>

      <!-- ══════ 备份管理 ══════ -->
      <van-cell-group inset title="备份管理">
        <div class="cell-footer">
          <van-button
            size="small"
            type="success"
            icon="records-o"
            round
            plain
            hairline
            :loading="backupLoading"
            @click="doBackup"
          >
            立即备份
          </van-button>
        </div>
        <div v-if="backups.length === 0" class="empty-hint">
          <van-icon name="info-o" />
          <span>暂无备份记录</span>
        </div>
        <van-cell
          v-for="b in backups"
          :key="b.id"
          :title="b.name"
          :label="`${b.created_at || ''} · ${b.size_mb}MB · ${b.projects_count}项目`"
        >
          <template #right-icon>
            <div class="remote-actions">
              <van-button
                size="mini"
                type="warning"
                round
                plain
                hairline
                @click.stop="confirmRestore(b)"
              >
                恢复
              </van-button>
              <van-button
                size="mini"
                round
                plain
                hairline
                type="danger"
                @click.stop="confirmDelBackup(b)"
              >
                删
              </van-button>
            </div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- ══════ 设置 ══════ -->
      <van-cell-group inset title="设置">
        <van-field
          v-model="settings.backup_keep_days"
          label="备份保留天数"
          type="number"
          placeholder="30"
          @blur="saveSettings"
        />
        <van-field
          v-model="settings.auto_backup_hours"
          label="自动备份间隔(h)"
          type="number"
          placeholder="24"
          @blur="saveSettings"
        />
      </van-cell-group>
    </template>

    <!-- ── 添加远程弹窗 ── -->
    <van-popup v-model:show="showRemoteForm" position="bottom" round :style="{ height: '50%' }" teleport="body">
      <div class="form-container">
        <h3>添加远程仓库</h3>
        <van-field v-model="remoteForm.name" label="名称" placeholder="github / gitee" />
        <van-field v-model="remoteForm.url" label="地址" placeholder="git@github.com:user/repo.git" />
        <div class="form-actions">
          <van-button round block type="primary" @click="addRemote" :loading="remoteAdding">添加</van-button>
          <van-button round block plain @click="showRemoteForm = false" style="margin-top: 8px">取消</van-button>
        </div>
      </div>
    </van-popup>

    <!-- ── 恢复确认 ── -->
    <van-dialog
      v-model:show="showRestoreConfirm"
      title="⚠️ 确认恢复"
      :message="restoreTarget ? `将恢复到备份「${restoreTarget.name}」。当前数据将被替换，不可撤销！` : ''"
      show-cancel-button
      confirm-button-color="#f59e0b"
      @confirm="doRestore"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import api from '../api.js'

const loading = ref(true)
const pushLoading = ref(false)
const backupLoading = ref(false)
const remoteAdding = ref(false)
const syncLoading = reactive({})
const showRemoteForm = ref(false)
const showRestoreConfirm = ref(false)
const restoreTarget = ref(null)

const selfStatus = ref({ is_git: false, message: '加载中...', remotes: [], status: {} })
const remotes = ref([])
const backups = ref([])
const settings = reactive({ backup_keep_days: '30', auto_backup_hours: '24' })

const remoteForm = reactive({ name: '', url: '' })

// ═══ Load Data ══════════════════════════════════════
async function loadAll() {
  loading.value = true
  try {
    const [s, r, b, st] = await Promise.all([
      api.get('/self/status').catch(() => ({ data: { is_git: false } })),
      api.get('/remotes'),
      api.get('/self/backups'),
      api.get('/self/settings'),
    ])
    selfStatus.value = s.data
    remotes.value = r.data.remotes || []
    backups.value = b.data.backups || []
    const sets = st.data.settings || {}
    settings.backup_keep_days = sets.backup_keep_days || '30'
    settings.auto_backup_hours = sets.auto_backup_hours || '24'
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ═══ Self Push ══════════════════════════════════════
async function doSelfPush() {
  pushLoading.value = true
  try {
    const { data } = await api.post('/self/push')
    if (data.ok) {
      showSuccessToast(`已推送到 ${data.pushed_to?.length || 0} 个远程`)
    } else {
      showFailToast('部分推送失败')
    }
    await loadAll()
  } catch (e) {
    showFailToast('推送失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    pushLoading.value = false
  }
}

// ═══ Remotes ════════════════════════════════════════
async function addRemote() {
  if (!remoteForm.name.trim() || !remoteForm.url.trim()) {
    showToast('名称和地址必填')
    return
  }
  remoteAdding.value = true
  try {
    await api.post('/remotes', { name: remoteForm.name.trim(), url: remoteForm.url.trim() })
    showSuccessToast('远程已添加')
    showRemoteForm.value = false
    remoteForm.name = ''
    remoteForm.url = ''
    await loadAll()
  } catch (e) {
    showFailToast(e.response?.data?.detail || '添加失败')
  } finally {
    remoteAdding.value = false
  }
}

function confirmDelRemote(r) {
  if (!confirm(`删除远程「${r.name}」？`)) return
  api.delete(`/remotes/${r.id}`).then(() => {
    showSuccessToast('已删除')
    loadAll()
  }).catch(e => showFailToast('删除失败'))
}

async function syncRemote(rid) {
  syncLoading[rid] = true
  try {
    const { data } = await api.post(`/self/remote/${rid}/sync`)
    showSuccessToast(`${data.action}远程: ${data.name}`)
    await loadAll()
  } catch (e) {
    showFailToast('同步失败')
  } finally {
    syncLoading[rid] = false
  }
}

// ═══ Backups ════════════════════════════════════════
async function doBackup() {
  backupLoading.value = true
  try {
    const { data } = await api.post('/self/backup')
    showSuccessToast(`备份完成: ${data.size_mb}MB`)
    await loadAll()
  } catch (e) {
    showFailToast('备份失败')
  } finally {
    backupLoading.value = false
  }
}

function confirmRestore(b) {
  restoreTarget.value = b
  showRestoreConfirm.value = true
}

async function doRestore() {
  if (!restoreTarget.value) return
  try {
    const { data } = await api.post(`/self/restore/${restoreTarget.value.id}`)
    showSuccessToast(`已恢复: ${data.restored_projects}项目, ${data.restored_docs}文档`)
    await loadAll()
  } catch (e) {
    showFailToast('恢复失败')
  } finally {
    restoreTarget.value = null
  }
}

function confirmDelBackup(b) {
  if (!confirm(`删除备份「${b.name}」？`)) return
  api.delete(`/self/backups/${b.id}`).then(() => {
    showSuccessToast('已删除')
    loadAll()
  }).catch(e => showFailToast('删除失败'))
}

// ═══ Settings ═══════════════════════════════════════
async function saveSettings() {
  try {
    await api.put('/self/settings', {
      backup_keep_days: String(settings.backup_keep_days),
      auto_backup_hours: String(settings.auto_backup_hours),
    })
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadAll)
</script>

<style scoped>
.self-page {
  padding: 16px 16px 80px;
  min-height: 100vh;
  background: var(--bg-page);
}

.loading-center {
  display: flex;
  justify-content: center;
  padding: 40vh 0;
}

/* ── Status Card ───────────────────────── */
.status-card {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-light);
}
.status-title {
  font-size: 15px;
  font-weight: 600;
}
.status-body { font-size: 14px; }
.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-lighter);
}
.status-label { color: var(--text-muted); font-size: 13px; }
.status-value { color: var(--text-primary); font-weight: 500; }
.status-value.has-changes { color: var(--warn); font-weight: 600; }
.no-git-msg { color: var(--text-muted); text-align: center; padding: 10px 0; margin: 0; }

.remote-list { margin-top: 4px; }
.remote-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}
.remote-name { color: var(--accent); font-weight: 500; flex-shrink: 0; }
.remote-url { color: var(--text-muted); font-family: var(--monospace); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-left: 8px; }

/* ── Batch Button ──────────────────────── */
.batch-section { margin-bottom: 16px; }
.batch-section .van-button {
  --van-button-primary-background: var(--accent-gradient);
  --van-button-primary-border-color: transparent;
  font-weight: 600;
  height: 44px;
}

/* ── Cell Group Overrides ─────────────── */
:deep(.van-cell-group__title) {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 16px 4px;
}

.empty-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.cell-footer {
  display: flex;
  justify-content: center;
  padding: 12px;
}

.remote-actions {
  display: flex;
  gap: 6px;
}

/* ── Form Popup ───────────────────────── */
.form-container {
  padding: 20px 16px;
}
.form-container h3 {
  margin: 0 0 16px;
  font-size: 17px;
  text-align: center;
}
.form-actions { padding: 16px 0 0; }
</style>
