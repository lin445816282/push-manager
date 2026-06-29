<template>
  <div class="docs-page">
    <!-- Mobile sidebar toggle -->
    <van-button
      class="sidebar-toggle"
      icon="bars"
      size="small"
      @click="showSidebar = !showSidebar"
    />

    <!-- Left Sidebar: Directory Tree -->
    <aside class="sidebar" :class="{ 'sidebar--open': showSidebar }">
      <div class="sidebar__header">
        <h3>📁 文档目录</h3>
        <van-icon name="cross" class="sidebar__close" @click="showSidebar = false" />
      </div>
      <div class="sidebar__tree">
        <div v-if="loadingTree" class="sidebar__loading">
          <van-loading size="20" /> 加载中...
        </div>
        <div v-else-if="treeError" class="sidebar__error">
          {{ treeError }}
          <van-button size="small" @click="fetchTree">重试</van-button>
        </div>
        <ul v-else class="tree">
          <li v-for="node in treeNodes" :key="node.path">
            <!-- Folder -->
            <div
              v-if="node.type === 'folder'"
              class="tree__folder"
              @click="toggleFolder(node.path)"
            >
              <van-icon :name="node.expanded ? 'arrow-down' : 'arrow'" size="12" />
              <span>{{ node.name }}</span>
            </div>
            <ul v-if="node.type === 'folder' && node.expanded" class="tree__children">
              <li
                v-for="child in node.children"
                :key="child.path"
                class="tree__file"
                :class="{ 'tree__file--active': currentPath === child.path }"
                @click="openFile(child.path)"
              >
                <van-icon name="description-o" size="14" />
                <span>{{ child.name }}</span>
              </li>
            </ul>
            <!-- Root-level file -->
            <div
              v-else-if="node.type === 'file'"
              class="tree__file"
              :class="{ 'tree__file--active': currentPath === node.path }"
              @click="openFile(node.path)"
            >
              <van-icon name="description-o" size="14" />
              <span>{{ node.name }}</span>
            </div>
          </li>
        </ul>
      </div>
    </aside>

    <!-- Overlay for mobile sidebar -->
    <div v-if="showSidebar" class="sidebar-overlay" @click="showSidebar = false" />

    <!-- Right Main Area -->
    <main class="main">
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="toolbar__left">
          <!-- Search -->
          <van-search
            v-model="searchQuery"
            placeholder="搜索文档..."
            shape="round"
            class="toolbar__search"
            @search="doSearch"
            @clear="searchResults = []"
          />
        </div>
        <div class="toolbar__actions">
          <van-button size="small" icon="add-o" @click="showNewDialog = true">新建</van-button>
          <van-button v-if="currentPath" size="small" icon="delete-o" type="danger" @click="confirmDelete" />
          <van-button v-if="currentPath" size="small" icon="clock-o" @click="fetchHistory" />
          <van-button size="small" icon="save-o" @click="saveFile" :disabled="!currentPath">保存</van-button>
        </div>
      </div>

      <!-- View mode toggle -->
      <div class="mode-bar">
        <van-radio-group v-model="viewMode" direction="horizontal">
          <van-radio name="edit">编辑</van-radio>
          <van-radio name="split">分屏</van-radio>
          <van-radio name="preview">预览</van-radio>
        </van-radio-group>
      </div>

      <!-- File info bar -->
      <div v-if="currentPath" class="file-info">
        <span class="file-info__name">{{ currentPath }}</span>
        <span v-if="saveStatus" class="file-info__status">{{ saveStatus }}</span>
      </div>

      <!-- Editor + Preview -->
      <div class="editor-area" :class="'editor-area--' + viewMode">
        <div v-show="viewMode !== 'preview'" class="editor-pane">
          <textarea
            v-model="content"
            class="editor-pane__textarea"
            placeholder="在此编辑 Markdown..."
            @keydown="handleKeydown"
            @paste="handlePaste"
          ></textarea>
        </div>
        <div
          v-show="viewMode !== 'edit'"
          class="preview-pane"
          v-html="renderedMarkdown"
        ></div>
      </div>

      <!-- Empty state -->
      <div v-if="!currentPath && !loadingFile" class="empty-state">
        <van-empty description="从左侧目录选择文件开始编辑" />
      </div>
      <div v-if="loadingFile" class="loading-state">
        <van-loading size="30" />
        <span>加载文档中...</span>
      </div>
    </main>

    <!-- New File Dialog -->
    <van-dialog
      v-model:show="showNewDialog"
      title="新建文档"
      show-cancel-button
      @confirm="createFile"
    >
      <div class="dialog-form">
        <van-field v-model="newFileName" label="文件名" placeholder="例如: readme.md" />
        <van-field v-model="newFolder" label="目录" placeholder="例如: docs/ (可选)" />
        <van-field
          v-model="newTemplate"
          label="模板"
          placeholder="选择一个模板"
          is-link
          readonly
          @click="showTemplatePicker = true"
        />
      </div>
    </van-dialog>

    <!-- Template Picker -->
    <van-popup v-model:show="showTemplatePicker" position="bottom" round>
      <van-picker
        :columns="templateOptions"
        @confirm="onPickTemplate"
        @cancel="showTemplatePicker = false"
      />
    </van-popup>

    <!-- Search Results -->
    <van-popup v-model:show="showSearchResults" position="bottom" round :style="{ height: '50%' }">
      <div class="search-results">
        <h4>搜索结果</h4>
        <div v-if="searchLoading" class="search-results__loading">
          <van-loading /> 搜索中...
        </div>
        <div v-else-if="searchResults.length === 0" class="search-results__empty">
          未找到匹配的文档
        </div>
        <van-cell
          v-for="r in searchResults"
          :key="r.path"
          :title="r.path"
          :label="r.snippet"
          @click="openSearchResult(r.path)"
        />
      </div>
    </van-popup>

    <!-- History Popup -->
    <van-popup v-model:show="showHistory" position="bottom" round :style="{ height: '50%' }">
      <div class="history-panel">
        <h4>版本历史</h4>
        <div v-if="historyLoading" class="history-panel__loading">
          <van-loading /> 加载中...
        </div>
        <div v-else-if="history.length === 0" class="history-panel__empty">
          暂无历史记录
        </div>
        <van-cell
          v-for="h in history"
          :key="h.commitId"
          :title="h.message"
          :label="`${h.author} · ${h.date}`"
        />
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { marked } from 'marked'
import api from '../api.js'

const route = useRoute()
const projectId = computed(() => route.params.id)

// ── Tree state ──────────────────────────────────────────────
const treeNodes = ref([])
const loadingTree = ref(false)
const treeError = ref('')
const showSidebar = ref(false)

// ── Editor state ────────────────────────────────────────────
const currentPath = ref('')
const content = ref('')
const loadingFile = ref(false)
const saveStatus = ref('')
const viewMode = ref('split') // edit | split | preview

// ── Search state ────────────────────────────────────────────
const searchQuery = ref('')
const searchResults = ref([])
const showSearchResults = ref(false)
const searchLoading = ref(false)

// ── New file state ──────────────────────────────────────────
const showNewDialog = ref(false)
const newFileName = ref('')
const newFolder = ref('')
const newTemplate = ref('blank')
const showTemplatePicker = ref(false)
const templateOptions = [
  { text: '空白文档', value: 'blank' },
  { text: '需求文档', value: 'requirements' },
  { text: '设计文档', value: 'design' },
  { text: '会议记录', value: 'meeting' },
]

// ── History state ───────────────────────────────────────────
const showHistory = ref(false)
const history = ref([])
const historyLoading = ref(false)

// ── Computed ────────────────────────────────────────────────
const renderedMarkdown = computed(() => {
  if (!content.value) return '<p style="color:#888;">预览区域</p>'
  try {
    return marked(content.value)
  } catch {
    return '<p style="color:#f44;">Markdown 解析错误</p>'
  }
})

// ── Tree helpers ────────────────────────────────────────────
function parseTree(flatList) {
  // flatList: [{path, type}] where type is 'file' or 'folder' (paths ending with /)
  const nodes = []
  const folderMap = {}

  // Sort: folders first, then alphabetical
  const sorted = [...flatList].sort((a, b) => {
    if (a.type === 'folder' && b.type !== 'folder') return -1
    if (a.type !== 'folder' && b.type === 'folder') return 1
    return a.path.localeCompare(b.path)
  })

  for (const item of sorted) {
    if (item.type === 'folder' || item.path.endsWith('/')) {
      const folder = {
        path: item.path.replace(/\/$/, ''),
        name: item.path.replace(/\/$/, '').split('/').pop() || item.path,
        type: 'folder',
        expanded: false,
        children: [],
      }
      folderMap[folder.path] = folder
      nodes.push(folder)
    } else {
      const parts = item.path.split('/')
      if (parts.length > 1) {
        const parentPath = parts.slice(0, -1).join('/')
        if (folderMap[parentPath]) {
          folderMap[parentPath].children.push({
            path: item.path,
            name: parts[parts.length - 1],
            type: 'file',
          })
        } else {
          // Create parent folder
          const folder = {
            path: parentPath,
            name: parts[parts.length - 2] || parentPath,
            type: 'folder',
            expanded: true,
            children: [{
              path: item.path,
              name: parts[parts.length - 1],
              type: 'file',
            }],
          }
          folderMap[parentPath] = folder
          nodes.push(folder)
        }
      } else {
        nodes.push({
          path: item.path,
          name: item.path,
          type: 'file',
        })
      }
    }
  }
  return nodes
}

// ── API calls ───────────────────────────────────────────────
async function fetchTree() {
  loadingTree.value = true
  treeError.value = ''
  try {
    const { data } = await api.get(`/projects/${projectId.value}/docs`)
    treeNodes.value = parseTree(data)
  } catch (e) {
    treeError.value = e.response?.data?.message || '加载目录失败'
  } finally {
    loadingTree.value = false
  }
}

async function openFile(path) {
  currentPath.value = path
  loadingFile.value = true
  saveStatus.value = ''
  try {
    const { data } = await api.get(`/projects/${projectId.value}/docs/${encodeURIComponent(path)}`)
    content.value = data.content || data
    showSidebar.value = false // close sidebar on mobile
  } catch (e) {
    showToast('加载失败: ' + (e.response?.data?.message || e.message))
  } finally {
    loadingFile.value = false
  }
}

async function saveFile() {
  if (!currentPath.value) return
  saveStatus.value = '保存中...'
  try {
    await api.put(
      `/projects/${projectId.value}/docs/${encodeURIComponent(currentPath.value)}`,
      { content: content.value }
    )
    saveStatus.value = '已保存 ✓'
    setTimeout(() => { saveStatus.value = '' }, 2000)
  } catch (e) {
    saveStatus.value = '保存失败 ✗'
    showToast('保存失败: ' + (e.response?.data?.message || e.message))
  }
}

async function createFile() {
  if (!newFileName.value.trim()) {
    showToast('请输入文件名')
    return
  }
  const name = newFileName.value.trim()
  const folder = newFolder.value.trim()
  const template = newTemplate.value
  try {
    await api.post(`/projects/${projectId.value}/docs`, null, {
      params: { name, folder, template },
    })
    showToast('创建成功')
    showNewDialog.value = false
    newFileName.value = ''
    newFolder.value = ''
    newTemplate.value = 'blank'
    fetchTree()
  } catch (e) {
    showToast('创建失败: ' + (e.response?.data?.message || e.message))
  }
}

async function confirmDelete() {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除 ${currentPath.value} 吗？`,
    })
    await api.delete(`/projects/${projectId.value}/docs/${encodeURIComponent(currentPath.value)}`)
    showToast('已删除')
    currentPath.value = ''
    content.value = ''
    fetchTree()
  } catch (e) {
    if (e !== 'cancel') {
      showToast('删除失败: ' + (e.response?.data?.message || e.message))
    }
  }
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searchLoading.value = true
  showSearchResults.value = true
  try {
    const { data } = await api.get('/docs/search', { params: { q: searchQuery.value } })
    searchResults.value = data.results || data
  } catch (e) {
    searchResults.value = []
    showToast('搜索失败')
  } finally {
    searchLoading.value = false
  }
}

function openSearchResult(path) {
  showSearchResults.value = false
  openFile(path)
}

async function fetchHistory() {
  if (!currentPath.value) return
  showHistory.value = true
  historyLoading.value = true
  try {
    const { data } = await api.get(
      `/projects/${projectId.value}/docs/${encodeURIComponent(currentPath.value)}/history`
    )
    history.value = data.commits || data
  } catch (e) {
    history.value = []
    showToast('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

// ── Helpers ─────────────────────────────────────────────────
function toggleFolder(path) {
  const node = treeNodes.value.find(n => n.path === path)
  if (node) node.expanded = !node.expanded
}

function onPickTemplate({ selectedOptions }) {
  newTemplate.value = selectedOptions[0]?.value || 'blank'
  showTemplatePicker.value = false
}

// Ctrl+S save shortcut
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    saveFile()
  }
}

// Image paste handler
async function handlePaste(e) {
  const items = e.clipboardData?.items
  if (!items || !currentPath.value) return

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const blob = item.getAsFile()
      if (!blob) continue

      // Insert placeholder
      const placeholder = '\n![上传中...]()\n'
      const textarea = e.target
      const start = textarea.selectionStart
      content.value = content.value.slice(0, start) + placeholder + content.value.slice(textarea.selectionEnd)

      // Upload
      try {
        const formData = new FormData()
        formData.append('file', blob, `paste.${blob.type.split('/')[1] || 'png'}`)
        const { data } = await api.post(
          `/projects/${projectId.value}/docs/upload-image`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        )
        // Replace placeholder with actual URL
        content.value = content.value.replace(placeholder, `\n![图片](${data.url})\n`)
        showToast('图片已上传')
      } catch (err) {
        content.value = content.value.replace(placeholder, '')
        showToast('图片上传失败')
      }
      break // Only handle first image
    }
  }
}

// ── Watch projectId ─────────────────────────────────────────
watch(projectId, () => {
  currentPath.value = ''
  content.value = ''
  fetchTree()
}, { immediate: false })

onMounted(() => {
  fetchTree()
})
</script>

<style scoped>
/* ── Layout ────────────────────────────────────────────────── */
.docs-page {
  display: flex;
  height: calc(100vh - 50px); /* account for tabbar */
  overflow: hidden;
  position: relative;
  background: #1a1a2e;
}

/* ── Sidebar Toggle (mobile) ──────────────────────────────── */
.sidebar-toggle {
  display: none;
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 100;
}

/* ── Sidebar ───────────────────────────────────────────────── */
.sidebar {
  width: 200px;
  min-width: 200px;
  background: #16162a;
  border-right: 1px solid #2a2a4a;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 50;
}

.sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid #2a2a4a;
  color: #e0e0e0;
}

.sidebar__header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.sidebar__close {
  display: none;
  cursor: pointer;
}

.sidebar__tree {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.sidebar__loading,
.sidebar__error {
  padding: 16px;
  color: #aaa;
  font-size: 12px;
  text-align: center;
}

.sidebar__error {
  color: #f66;
}

/* ── Tree ──────────────────────────────────────────────────── */
.tree {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tree__folder {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  cursor: pointer;
  color: #c0c0e0;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s;
}

.tree__folder:hover { background: #2a2a4a; }

.tree__children {
  list-style: none;
  margin: 0;
  padding-left: 8px;
}

.tree__file {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 20px;
  cursor: pointer;
  color: #aaa;
  font-size: 12px;
  transition: background 0.15s;
}

.tree__file:hover { background: #2a2a4a; color: #e0e0e0; }
.tree__file--active { background: #3a3a6a; color: #fff; }

/* ── Sidebar overlay ──────────────────────────────────────── */
.sidebar-overlay {
  display: none;
}

/* ── Main ──────────────────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ── Toolbar ───────────────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #1e1e32;
  border-bottom: 1px solid #2a2a4a;
  flex-wrap: wrap;
}

.toolbar__left { flex: 1; min-width: 0; }

.toolbar__search {
  padding: 0 !important;
  background: transparent !important;
}

.toolbar__search :deep(.van-search__content) {
  background: #2a2a4a;
  border-radius: 16px;
}

.toolbar__search :deep(.van-field__control) {
  color: #e0e0e0;
}

.toolbar__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* ── Mode bar ──────────────────────────────────────────────── */
.mode-bar {
  display: flex;
  justify-content: center;
  padding: 6px 12px;
  background: #1e1e32;
  border-bottom: 1px solid #2a2a4a;
}

.mode-bar :deep(.van-radio-group) { gap: 16px; }
.mode-bar :deep(.van-radio__label) { color: #aaa; font-size: 13px; }
.mode-bar :deep(.van-radio__icon--checked + .van-radio__label) { color: #8be9fd; }

/* ── File info ─────────────────────────────────────────────── */
.file-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 16px;
  background: #22223a;
  border-bottom: 1px solid #2a2a4a;
  font-size: 12px;
}

.file-info__name { color: #aaa; font-family: monospace; }
.file-info__status { color: #50fa7b; }

/* ── Editor area ───────────────────────────────────────────── */
.editor-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.editor-area--edit .editor-pane { flex: 1; }
.editor-area--edit .preview-pane { display: none; }
.editor-area--preview .editor-pane { display: none; }
.editor-area--preview .preview-pane { flex: 1; }
.editor-area--split .editor-pane { flex: 1; }
.editor-area--split .preview-pane { flex: 1; }

.editor-pane {
  display: flex;
  min-width: 0;
}

.editor-pane__textarea {
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  resize: none;
  padding: 16px 20px;
  font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  background: #1e1e2e;
  color: #e0e0f0;
  tab-size: 2;
}

.editor-pane__textarea::placeholder {
  color: #666;
}

.editor-pane__textarea:focus {
  background: #1c1c2c;
}

.preview-pane {
  overflow-y: auto;
  padding: 16px 20px;
  background: #1e1e2e;
  color: #d0d0e0;
  line-height: 1.7;
  font-size: 14px;
}

/* ── Markdown preview styles ──────────────────────────────── */
.preview-pane :deep(h1) { color: #8be9fd; margin-top: 0; border-bottom: 1px solid #3a3a5a; padding-bottom: 8px; }
.preview-pane :deep(h2) { color: #50fa7b; margin-top: 24px; }
.preview-pane :deep(h3) { color: #ffb86c; }
.preview-pane :deep(h4) { color: #bd93f9; }
.preview-pane :deep(code) {
  background: #2a2a4a;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
  color: #f1fa8c;
}
.preview-pane :deep(pre) {
  background: #16162a;
  padding: 14px 18px;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid #2a2a4a;
}
.preview-pane :deep(pre code) {
  background: transparent;
  padding: 0;
  color: #e0e0f0;
}
.preview-pane :deep(blockquote) {
  border-left: 3px solid #bd93f9;
  margin-left: 0;
  padding-left: 16px;
  color: #aaa;
}
.preview-pane :deep(a) { color: #8be9fd; }
.preview-pane :deep(table) { border-collapse: collapse; width: 100%; }
.preview-pane :deep(th), .preview-pane :deep(td) {
  border: 1px solid #3a3a5a;
  padding: 6px 12px;
  text-align: left;
}
.preview-pane :deep(th) { background: #2a2a4a; }
.preview-pane :deep(hr) { border: none; border-top: 1px solid #3a3a5a; }
.preview-pane :deep(ul), .preview-pane :deep(ol) { padding-left: 24px; }
.preview-pane :deep(img) { max-width: 100%; border-radius: 6px; }

/* ── Empty / Loading ──────────────────────────────────────── */
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
}
.empty-state :deep(.van-empty__description) { color: #666; }

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #aaa;
}

/* ── Dialog form ───────────────────────────────────────────── */
.dialog-form {
  padding: 16px;
}
.dialog-form :deep(.van-field) {
  background: #2a2a4a;
  margin-bottom: 8px;
  border-radius: 8px;
}
.dialog-form :deep(.van-field__control) { color: #e0e0e0; }
.dialog-form :deep(.van-field__label) { color: #aaa; }

/* ── Search results ────────────────────────────────────────── */
.search-results {
  padding: 12px;
  max-height: 100%;
  overflow-y: auto;
}
.search-results h4 {
  margin: 0 0 8px;
  color: #e0e0e0;
  font-size: 14px;
}
.search-results__loading,
.search-results__empty {
  text-align: center;
  padding: 24px;
  color: #888;
  font-size: 13px;
}

/* ── History panel ─────────────────────────────────────────── */
.history-panel {
  padding: 12px;
  max-height: 100%;
  overflow-y: auto;
}
.history-panel h4 {
  margin: 0 0 8px;
  color: #e0e0e0;
  font-size: 14px;
}
.history-panel__loading,
.history-panel__empty {
  text-align: center;
  padding: 24px;
  color: #888;
  font-size: 13px;
}

/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 768px) {
  .sidebar-toggle { display: block; }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 50px;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    z-index: 200;
  }

  .sidebar--open { transform: translateX(0); }
  .sidebar__close { display: block; }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 150;
  }

  .main { padding-left: 0; }

  .editor-area--split {
    flex-direction: column;
  }

  .editor-area--split .editor-pane { flex: none; height: 50%; }
  .editor-area--split .preview-pane { flex: none; height: 50%; }

  .toolbar { padding: 6px 8px; gap: 4px; }
  .toolbar__actions { gap: 3px; }

  .toolbar__actions :deep(.van-button) {
    padding: 0 8px;
    font-size: 11px;
  }
}
</style>
