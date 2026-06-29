# GitHub 推送管理器 V2.1 — 需求文档

> 代码 + 文档统一托管 · 多项目 Git 管理 · 静态站点部署 · 自保护

---

## 一、项目概述

统一管理多个项目的 Git 操作，支持代码推送/拉取、静态站点部署、Markdown 文档编辑、以及管理器自身的备份保护。

- **技术栈**: FastAPI + Vue3 + Vant4 + SQLite
- **端口**: 8007
- **入口**: ct256.cn/push/ (通过 stock-aggregator:8000 反向代理)

---

## 二、功能模块

### F01 仪表盘
- 总项目数 / 有变更数 / 今日推送数 三栏统计
- 一键全推送所有项目
- 项目状态卡片（类型标签、路径、Git 状态圆点）
- 单项目快捷：文档入口、Pull、Push

### F02 项目管理
- 添加/编辑/删除项目
- 自动识别项目类型：code / static / nav_page
- 表单弹窗（名称、路径、类型、远程地址、分支）
- 文档存储模式：manager（统一目录）/ project（项目内）
- 长按删除确认

### F03 Git 操作
- `git status --porcelain` 实时状态检测
- 展开查看变更文件列表（修改/未跟踪）
- 单项目 Pull / Push
- 批量推送 API
- `--force-with-lease` 安全推送

### F04 操作日志
- 时间线展示所有操作记录
- 按项目筛选
- 30 秒自动刷新
- 记录动作：add / edit / delete / push / pull / backup / restore

### F05 文档管理
- 目录树（文件夹 + 文件）
- Markdown 编辑器 + 实时预览（marked.js）
- 三种视图：编辑 / 分屏 / 预览
- 4 种模板：空白 / 需求 / 设计 / 会议
- 全文搜索（跨项目）
- Git 版本历史
- **图片粘贴上传**：Ctrl+V 粘贴截图 → 自动上传 → Markdown 插入

### F06 管理器自保护 🆕
- 自身 Git 仓库状态检测
- 一键推送管理器到所有配置远程
- 多远程仓库配置 + Git remote 同步
- tar.gz 快照备份（项目配置 + 文档）
- 备份列表 / 恢复 / 删除
- 设置：备份保留天数 / 自动备份间隔

### F07 暗色主题 🆕
- 右上角 ☀️/🌙 一键切换
- CSS 变量全局控制（--bg-page / --bg-card / --text-primary）
- Vant 组件同步适配
- localStorage 记忆偏好

### F08 导航集成
- ct256.cn 导航页入口
- SPA Hash 路由（4 个 Tab：仪表盘/项目/自保/日志）
- 聚合器反向代理 `/push/* → :8007`

---

## 三、API 端点

```
GET/POST/PUT/DELETE  /api/projects                    项目管理
GET                  /api/projects/{id}/status         Git 状态
POST                 /api/projects/{id}/push           推送
POST                 /api/projects/{id}/pull           拉取
POST                 /api/projects/batch-push          批量推送
GET                  /api/logs                         操作日志

GET/POST/PUT/DELETE  /api/projects/{id}/docs           文档管理
POST                 /api/projects/{id}/docs/upload-image  图片上传 🆕
GET                  /api/docs/search                  文档搜索
GET                  /api/projects/{id}/docs/{path}/history  版本历史

GET/POST/DELETE      /api/remotes                      远程仓库配置
GET                  /api/self/status                  自身状态
POST                 /api/self/push                    自身推送
POST                 /api/self/remote/{id}/sync        同步远程
GET/POST/DELETE      /api/self/backups                 备份管理
POST                 /api/self/restore/{id}            恢复备份
GET/PUT              /api/self/settings                设置
```

---

## 四、数据模型

### projects
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| name | TEXT | 项目名称 |
| path | TEXT UNIQUE | 本地路径 |
| type | TEXT | code/static/nav_page |
| remote_url | TEXT | Git 远程地址 |
| branch | TEXT | 分支名 |
| docs_storage | TEXT | manager/project |
| docs_path | TEXT | 文档目录 |
| auto_push_docs | INTEGER | 是否自动推送文档 |

### push_logs
| 字段 | 说明 |
|------|------|
| project_id | 关联项目 |
| action | add/edit/delete/push/pull/backup/restore |
| status | ok/error |
| detail | 详细输出 |

### remotes / backups / settings
支持管理器自身的远程仓库配置、备份管理和键值设置。

---

## 五、部署架构

```
Cloudflare Tunnel (ct256.cn)
    ↓
stock-aggregator:8000
    ├── /push/* → push-manager:8007  (反向代理)
    ├── /fund/* → fund-tracker:8006
    ├── /purchase/* → purchase-tracker:8003
    ├── /remind/* → remind:8002
    └── /nav       → 导航页
```

---

## 六、待迭代

- [ ] 定时自动备份（cron 集成）
- [ ] 恢复向导（步骤式 UI）
- [ ] 远程地址自动推送配置
- [ ] 多项目文档关联
- [ ] 静态站点自动部署
