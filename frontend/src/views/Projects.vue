<template>
  <div class="projects-page">
    <div class="header">
      <h2>项目</h2>
    </div>

    <!-- Loading state -->
    <van-loading v-if="loading && projects.length === 0" class="loading" />

    <!-- Empty state -->
    <van-empty v-else-if="!loading && projects.length === 0" description="暂无项目，点击右下角 + 添加" />

    <!-- Project list -->
    <van-cell-group v-else inset>
      <div
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        @touchstart="onTouchStart($event, project)"
        @touchend="onTouchEnd($event, project)"
        @touchmove="onTouchMove"
      >
        <van-cell
          :title="project.name"
          :label="project.path"
          @click="openEdit(project)"
        >
          <template #value>
            <van-tag :type="typeColor(project.type)" size="medium">
              {{ typeLabel(project.type) }}
            </van-tag>
          </template>
          <template #right-icon>
            <van-icon
              :name="expandedId === project.id ? 'arrow-up' : 'arrow-down'"
              size="16"
              color="#999"
              @click.stop="toggleExpand(project)"
              class="expand-toggle"
            />
          </template>
        </van-cell>

        <!-- Expanded git status panel -->
        <div v-if="expandedId === project.id" class="git-panel">
          <van-loading v-if="gitLoading[project.id]" size="small" class="git-loading" />
          <template v-else-if="gitStatus[project.id]">
            <div class="git-stats">
              <span v-if="gitStatus[project.id].modified?.length" class="stat modified">
                <van-icon name="edit" /> 修改 {{ gitStatus[project.id].modified.length }}
              </span>
              <span v-if="gitStatus[project.id].untracked?.length" class="stat untracked">
                <van-icon name="add-o" /> 未跟踪 {{ gitStatus[project.id].untracked.length }}
              </span>
              <span
                v-if="!gitStatus[project.id].modified?.length && !gitStatus[project.id].untracked?.length"
                class="stat clean"
              >
                <van-icon name="success" /> 干净
              </span>
            </div>
            <div
              class="git-file-list"
              v-if="gitStatus[project.id].modified?.length || gitStatus[project.id].untracked?.length"
            >
              <div v-for="f in gitStatus[project.id].modified" :key="'m-'+f" class="git-file modified-file">
                <van-icon name="edit" size="14" /> {{ f }}
              </div>
              <div v-for="f in gitStatus[project.id].untracked" :key="'u-'+f" class="git-file untracked-file">
                <van-icon name="add-o" size="14" /> {{ f }}
              </div>
            </div>
          </template>
          <div v-else-if="!gitLoading[project.id]" class="git-stats">
            <span class="stat" style="color:#999">点击展开时自动获取状态</span>
          </div>
          <div class="git-actions">
            <van-button
              size="small"
              icon="arrow-down"
              type="primary"
              :loading="actionLoading[project.id] === 'pull'"
              @click.stop="pullProject(project)"
            >
              Pull
            </van-button>
            <van-button
              size="small"
              icon="arrow-up"
              type="warning"
              :loading="actionLoading[project.id] === 'push'"
              @click.stop="pushProject(project)"
            >
              Push
            </van-button>
          </div>
        </div>
      </div>
    </van-cell-group>

    <!-- FAB add button -->
    <div class="fab" @click="openCreate">
      <van-icon name="plus" size="24" color="#fff" />
    </div>

    <!-- Form popup (create / edit) -->
    <van-popup
      v-model:show="showForm"
      position="bottom"
      round
      :style="{ height: '85%' }"
      teleport="body"
    >
      <div class="form-container">
        <h3>{{ isEdit ? '编辑项目' : '新建项目' }}</h3>

        <van-field
          v-model="form.name"
          label="名称"
          placeholder="项目名称"
          required
        />
        <van-field
          v-model="form.path"
          label="路径"
          placeholder="/path/to/project"
          required
        />
        <div v-if="!isEdit" class="quick-paths">
          <span class="quick-paths-label">📁 本地路径</span>
          <div class="quick-paths-grid">
            <van-button
              v-for="p in localPaths"
              :key="p"
              size="small"
              plain
              hairline
              class="quick-path-btn"
              @click="form.path = p"
            >{{ p.split('/').pop() }}</van-button>
          </div>
        </div>
        <van-field
          v-model="typeDisplay"
          label="类型"
          placeholder="选择项目类型"
          readonly
          clickable
          @click="showTypeSheet = true"
        />
        <van-field
          v-model="form.remote_url"
          label="远程地址"
          placeholder="git@github.com:user/repo.git"
        />
        <van-field
          v-model="form.branch"
          label="分支"
          placeholder="main"
        />

        <van-cell title="文档存储" center>
          <template #right-icon>
            <van-switch
              v-model="form.docs_storage"
              :active-value="'project'"
              :inactive-value="'manager'"
              size="24"
            />
          </template>
          <template #label>
            <span class="switch-tip">
              {{ form.docs_storage === 'project' ? '项目目录' : '管理器目录' }}
            </span>
          </template>
        </van-cell>

        <van-field
          v-model="form.docs_path"
          label="文档路径"
          placeholder="docs/"
        />
        <van-cell title="自动推送文档" center>
          <template #right-icon>
            <van-switch v-model="form.auto_push_docs" size="24" />
          </template>
        </van-cell>

        <div class="form-actions">
          <van-button round block type="primary" @click="submitForm" :loading="submitting">
            {{ isEdit ? '保存修改' : '创建项目' }}
          </van-button>
          <van-button round block plain @click="showForm = false" style="margin-top: 8px">
            取消
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- Type picker sheet -->
    <van-action-sheet
      v-model:show="showTypeSheet"
      :actions="typeActions"
      @select="onTypeSelect"
      cancel-text="取消"
    />

    <!-- Delete confirm dialog -->
    <van-dialog
      v-model:show="showDeleteConfirm"
      title="确认删除"
      :message="deleteTarget ? '确定要删除项目 「' + deleteTarget.name + '」吗？' : ''"
      show-cancel-button
      @confirm="doDelete"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import api from '../api.js'

// ── List state ─────────────────────────────────────
const projects = ref([])
const loading = ref(false)

// ── Expand / git state ────────────────────────────
const expandedId = ref(null)
const gitStatus = reactive({})
const gitLoading = reactive({})
const actionLoading = reactive({})

// ── Form state ─────────────────────────────────────
const showForm = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const form = reactive({
  name: '',
  path: '',
  type: 'code',
  remote_url: '',
  branch: 'main',
  docs_storage: 'manager',
  docs_path: 'docs/',
  auto_push_docs: false,
})

// ── Local paths quick select ───────────────────────
const localPaths = ref([])
async function fetchLocalPaths() {
  try {
    const { data } = await api.get('/local-paths')
    localPaths.value = data.paths || []
  } catch (e) {
    // Fallback: hardcoded common paths
    localPaths.value = [
      '/home/xiaolin/projects/stock-aggregator',
      '/home/xiaolin/projects/purchase-tracker',
      '/home/xiaolin/projects/push-manager',
      '/home/xiaolin/projects/aa-books',
      '/home/xiaolin/projects/remind',
      '/home/xiaolin/projects/fund-tracker',
      '/home/xiaolin/projects/nav-page',
      '/home/xiaolin/projects/moe-island',
    ]
  }
}

// ── Type picker ────────────────────────────────────
const showTypeSheet = ref(false)
const typeActions = [
  { name: 'Code 项目', value: 'code' },
  { name: 'Static 静态站点', value: 'static' },
  { name: 'Nav Page', value: 'nav_page' },
]
const typeDisplay = computed(() => {
  const a = typeActions.find(t => t.value === form.type)
  return a ? a.name : form.type
})
function onTypeSelect(action) {
  form.type = action.value
  showTypeSheet.value = false
}

function typeColor(type) {
  return { code: 'primary', static: 'success', nav_page: 'warning' }[type] || 'default'
}
function typeLabel(type) {
  return { code: 'Code', static: 'Static', nav_page: 'NavPage' }[type] || type
}

// ── Long-press (touch-based) ────────────────────────
const longPressTimer = ref(null)
const longPressTriggered = ref(false)
const LONG_PRESS_MS = 600

function onTouchStart(e, project) {
  longPressTriggered.value = false
  longPressTimer.value = setTimeout(() => {
    longPressTriggered.value = true
    confirmDelete(project)
  }, LONG_PRESS_MS)
}

function onTouchEnd() {
  clearTimeout(longPressTimer.value)
  longPressTimer.value = null
}

function onTouchMove() {
  // Cancel long-press on scroll
  clearTimeout(longPressTimer.value)
  longPressTimer.value = null
}

// ── Delete ─────────────────────────────────────────
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

function confirmDelete(project) {
  deleteTarget.value = project
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await api.delete(`/projects/${deleteTarget.value.id}`)
    showToast('项目已删除')
    if (expandedId.value === deleteTarget.value.id) {
      expandedId.value = null
    }
    await fetchProjects()
  } catch (e) {
    showToast('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

// ── Data fetching ──────────────────────────────────
async function fetchProjects() {
  loading.value = true
  try {
    const { data } = await api.get('/projects')
    projects.value = Array.isArray(data) ? data : (data.projects || [])
  } catch (e) {
    showToast('加载项目失败: ' + (e.response?.data?.error || e.message))
  } finally {
    loading.value = false
  }
}

// ── Form helpers ───────────────────────────────────
function resetForm() {
  form.name = ''
  form.path = ''
  form.type = 'code'
  form.remote_url = ''
  form.branch = 'main'
  form.docs_storage = 'manager'
  form.docs_path = 'docs/'
  form.auto_push_docs = false
  isEdit.value = false
  editId.value = null
}

function fillForm(project) {
  form.name = project.name || ''
  form.path = project.path || ''
  form.type = project.type || 'code'
  form.remote_url = project.remote_url || ''
  form.branch = project.branch || 'main'
  form.docs_storage = project.docs_storage || 'manager'
  form.docs_path = project.docs_path || 'docs/'
  form.auto_push_docs = project.auto_push_docs || false
  isEdit.value = true
  editId.value = project.id
}

function openCreate() {
  resetForm()
  fetchLocalPaths()
  showForm.value = true
}

function openEdit(project) {
  // Guard: don't open edit if long-press was just triggered
  if (longPressTriggered.value) return
  // Collapse git panel when editing
  if (expandedId.value === project.id) {
    expandedId.value = null
  }
  fillForm(project)
  showForm.value = true
}

async function submitForm() {
  if (!form.name.trim() || !form.path.trim()) {
    showToast('名称和路径为必填项')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      path: form.path.trim(),
      type: form.type,
      remote_url: form.remote_url.trim(),
      branch: form.branch.trim() || 'main',
      docs_storage: form.docs_storage,
      docs_path: form.docs_path.trim() || 'docs/',
      auto_push_docs: form.auto_push_docs,
    }
    if (isEdit.value) {
      await api.put(`/projects/${editId.value}`, payload)
      showToast('项目已更新')
    } else {
      await api.post('/projects', payload)
      showToast('项目已创建')
    }
    showForm.value = false
    await fetchProjects()
  } catch (e) {
    showToast('操作失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

// ── Git expand / status / push / pull ──────────────
async function toggleExpand(project) {
  if (expandedId.value === project.id) {
    expandedId.value = null
    return
  }
  expandedId.value = project.id
  // Fetch git status
  gitLoading[project.id] = true
  try {
    const { data } = await api.get(`/projects/${project.id}/status`)
    gitStatus[project.id] = data
  } catch (e) {
    showToast('获取状态失败: ' + (e.response?.data?.error || e.message))
    gitStatus[project.id] = null
  } finally {
    gitLoading[project.id] = false
  }
}

async function pushProject(project) {
  actionLoading[project.id] = 'push'
  try {
    const { data } = await api.post(`/projects/${project.id}/push`)
    showToast(data.message || 'Push 成功')
  } catch (e) {
    showToast('Push 失败: ' + (e.response?.data?.error || e.message))
  } finally {
    actionLoading[project.id] = null
  }
}

async function pullProject(project) {
  actionLoading[project.id] = 'pull'
  try {
    const { data } = await api.post(`/projects/${project.id}/pull`)
    showToast(data.message || 'Pull 成功')
  } catch (e) {
    showToast('Pull 失败: ' + (e.response?.data?.error || e.message))
  } finally {
    actionLoading[project.id] = null
  }
}

// ── Lifecycle ──────────────────────────────────────
onMounted(() => {
  fetchProjects()
})
</script>

<style scoped>
.projects-page {
  padding: 12px;
  padding-bottom: 80px;
}

.header {
  padding: 0 4px 12px;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

/* Project card */
.project-card {
  border-bottom: 1px solid var(--border-color);
}

.project-card:last-child {
  border-bottom: none;
}

.expand-toggle {
  padding: 4px;
  margin-left: 4px;
}

/* Git panel */
.git-panel {
  padding: 0 16px 12px;
  border-top: 1px solid var(--border-color);
  background: var(--van-background-2, #f7f8fa);
}

.git-loading {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

.git-stats {
  display: flex;
  gap: 12px;
  padding: 10px 0 6px;
  font-size: 13px;
  flex-wrap: wrap;
}

.stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.stat.modified { color: #f0ad4e; }
.stat.untracked { color: #5bc0de; }
.stat.clean { color: #5cb85c; }

.git-file-list {
  max-height: 120px;
  overflow-y: auto;
  margin-bottom: 8px;
}

.git-file {
  font-size: 12px;
  padding: 3px 0;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--van-text-color, #323233);
  font-family: monospace;
}

.modified-file { color: #f0ad4e; }
.untracked-file { color: #5bc0de; }

.git-actions {
  display: flex;
  gap: 8px;
  padding: 8px 0 4px;
}

/* FAB */
.fab {
  position: fixed;
  bottom: 80px;
  right: 24px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--accent, #aa3bff);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  cursor: pointer;
  z-index: 10;
  transition: transform 0.2s;
}

.fab:active {
  transform: scale(0.92);
}

/* ── Quick local paths ────────────────────────── */
.quick-paths {
  padding: 4px 16px 8px;
}
.quick-paths-label {
  font-size: 11px;
  color: var(--van-text-color-weak, #969799);
  margin-bottom: 6px;
  display: block;
}
.quick-paths-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.quick-path-btn {
  --van-button-small-height: 24px;
  --van-button-small-font-size: 10px;
  --van-button-small-padding: 0 8px;
}

/* Form popup */
.form-container {
  padding: 20px 12px 32px;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
}

.form-container h3 {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 600;
  text-align: center;
}

.switch-tip {
  font-size: 12px;
  color: var(--van-text-color-weak, #969799);
  margin-left: 4px;
}

.form-actions {
  padding: 16px 16px 0;
}
</style>
