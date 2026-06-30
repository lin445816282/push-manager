"""
GitHub 推送管理器 V2.1 — 代码 + 文档统一托管
"""
import os, sqlite3, json, subprocess, re, uuid, shutil, shlex
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("push-manager")

app = FastAPI(title="GitHub Push Manager", version="2.1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "manager.db")
DOCS_ROOT = os.path.join(BASE_DIR, "..", "projects_docs")
os.makedirs(DOCS_ROOT, exist_ok=True)


# ═══════════════════════════════════════════
# Database
# ═══════════════════════════════════════════
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            type TEXT DEFAULT 'code',
            remote_url TEXT DEFAULT '',
            branch TEXT DEFAULT 'main',
            docs_storage TEXT DEFAULT 'manager',
            docs_path TEXT DEFAULT 'docs',
            auto_push_docs INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS push_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            action TEXT NOT NULL,
            message TEXT DEFAULT '',
            status TEXT DEFAULT 'ok',
            detail TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS remotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            projects_count INTEGER DEFAULT 0,
            docs_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # Insert default settings if not exist
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('backup_keep_days', '30')")
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_backup_hours', '24')")
    db.commit()
    db.close()


init_db()


# ═══════════════════════════════════════════
# Models
# ═══════════════════════════════════════════
class ProjectIn(BaseModel):
    name: str
    path: str
    type: str = "code"
    remote_url: str = ""
    deploy_url: str = ""
    branch: str = "main"
    docs_storage: str = "manager"
    docs_path: str = "docs"
    auto_push_docs: bool = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    type: Optional[str] = None
    remote_url: Optional[str] = None
    deploy_url: Optional[str] = None
    branch: Optional[str] = None
    docs_storage: Optional[str] = None
    docs_path: Optional[str] = None
    auto_push_docs: Optional[bool] = None


class RemoteIn(BaseModel):
    name: str
    url: str


class DocSave(BaseModel):
    content: str


# ═══════════════════════════════════════════
# Git Helpers
# ═══════════════════════════════════════════
def _git(cmd: str, cwd: str, timeout: int = 30) -> tuple:
    """Run git command, return (output, error, exit_code)"""
    try:
        r = subprocess.run(
            ["git"] + shlex.split(cmd),
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except FileNotFoundError:
        return "", "git not found", -1


def _log_action(project_id: int, action: str, message: str, status: str = "ok", detail: str = ""):
    db = get_db()
    db.execute(
        "INSERT INTO push_logs (project_id, action, message, status, detail) VALUES (?,?,?,?,?)",
        (project_id, action, message, status, detail)
    )
    db.commit()
    db.close()


def _detect_type(path: str) -> str:
    """Auto-detect project type"""
    p = Path(path)
    if not p.exists():
        return "unknown"
    if (p / "package.json").exists() or (p / "requirements.txt").exists():
        return "code"
    if (p / "index.html").exists() and not (p / ".git").exists():
        return "static"
    if (p / "nav.html").exists() or all(f.suffix == ".html" for f in p.glob("*.html") if f.is_file()):
        return "nav_page"
    if (p / ".git").exists():
        return "code"
    return "static"


def check_git_status(path: str) -> dict:
    """Get detailed git status for a project"""
    out, err, code = _git("status --porcelain", path)
    if code != 0:
        return {"error": err or "not a git repo", "clean": False, "files": []}
    files = out.split("\n") if out else []
    modified = [f[3:] for f in files if f.startswith(" M") or f.startswith("M ")]
    untracked = [f[3:] for f in files if f.startswith("??")]
    staged = [f[3:] for f in files if f.startswith("M ") or f.startswith("A ")]
    return {
        "clean": len(files) == 0,
        "total_changes": len(files),
        "modified": modified,
        "untracked": untracked,
        "staged": staged,
    }


# ═══════════════════════════════════════════
# API: Projects
# ═══════════════════════════════════════════
@app.get("/api/projects")
def list_projects():
    db = get_db()
    rows = db.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    db.close()
    projects = []
    for r in rows:
        p = dict(r)
        path = p["path"]
        p["exists"] = os.path.isdir(path)
        p["is_git"] = os.path.isdir(os.path.join(path, ".git")) if p["exists"] else False
        if p["exists"] and p["is_git"]:
            status = check_git_status(path)
            p["status"] = status
        else:
            p["status"] = {"clean": True, "total_changes": 0, "modified": [], "untracked": []}
        projects.append(p)
    return {"projects": projects, "count": len(projects)}


@app.post("/api/projects")
def add_project(p: ProjectIn):
    path = os.path.abspath(os.path.expanduser(p.path))
    if not os.path.isdir(path):
        raise HTTPException(400, f"目录不存在: {path}")

    ptype = p.type if p.type != "auto" else _detect_type(path)

    db = get_db()
    existing = db.execute("SELECT id FROM projects WHERE path=?", (path,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(409, "项目已存在")

    db.execute(
        """INSERT INTO projects (name, path, type, remote_url, deploy_url, branch, docs_storage, docs_path, auto_push_docs)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (p.name, path, ptype, p.remote_url, p.deploy_url, p.branch, p.docs_storage, p.docs_path, int(p.auto_push_docs))
    )
    db.commit()
    pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    # Create docs directory if manager mode
    if p.docs_storage == "manager":
        doc_dir = os.path.join(DOCS_ROOT, p.name)
        os.makedirs(doc_dir, exist_ok=True)

    _log_action(pid, "add", f"添加项目: {p.name}")
    return {"id": pid, "ok": True}


@app.put("/api/projects/{pid}")
def update_project(pid: int, p: ProjectUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "项目不存在")

    updates = {}
    for k in ["name", "path", "type", "remote_url", "deploy_url", "branch", "docs_storage", "docs_path"]:
        v = getattr(p, k, None)
        if v is not None:
            updates[k] = v
    if p.auto_push_docs is not None:
        updates["auto_push_docs"] = int(p.auto_push_docs)

    if updates:
        updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values())
        db.execute(f"UPDATE projects SET {sets} WHERE id=?", vals + [pid])
        db.commit()

    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    _log_action(pid, "edit", f"编辑项目: {p.name or existing['name']}")
    return dict(row)


@app.delete("/api/projects/{pid}")
def delete_project(pid: int):
    db = get_db()
    existing = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(404, "项目不存在")
    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    db.close()
    _log_action(pid, "delete", f"删除项目: {existing['name']}")
    return {"ok": True}


# ═══════════════════════════════════════════
# API: Git Operations
# ═══════════════════════════════════════════
@app.get("/api/projects/{pid}/status")
def project_status(pid: int):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)
    return check_git_status(p["path"])


@app.post("/api/projects/{pid}/pull")
def pull_project(pid: int):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    out, err, code = _git(f"pull origin {p['branch']}", p["path"])
    status = "ok" if code == 0 else "error"
    detail = out if code == 0 else err
    _log_action(pid, "pull", f"从 {p['branch']} 拉取", status, detail[:500])
    return {"ok": code == 0, "output": detail}


@app.post("/api/projects/{pid}/push")
def push_project(pid: int, message: str = Query("update"), push_docs: bool = Query(True)):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    cwd = p["path"]
    results = []

    # 1. Stage all changes in project
    _git("add -A", cwd)
    out, err, code = _git(f"commit -m {shlex.quote(message)}", cwd)
    if code == 0:
        results.append({"step": "commit", "ok": True, "output": out[:200]})
    elif "nothing to commit" in (out + err):
        results.append({"step": "commit", "ok": True, "output": "nothing to commit"})
    else:
        results.append({"step": "commit", "ok": False, "output": err[:200]})

    # 2. Push docs if manager mode + requested
    if push_docs and p["docs_storage"] == "manager" and p["auto_push_docs"]:
        doc_dir = os.path.join(DOCS_ROOT, p["name"])
        if os.path.isdir(doc_dir):
            _git(f"add -A", DOCS_ROOT)
            _git(f'commit -m "docs: {p["name"]} 文档更新"', DOCS_ROOT)

    # 3. Push
    out, err, code = _git(f"push origin {p['branch']}", cwd)
    if code == 0:
        results.append({"step": "push", "ok": True, "output": out[:200]})
        _log_action(pid, "push", message, "ok", out[:200])
    else:
        results.append({"step": "push", "ok": False, "output": err[:200]})
        _log_action(pid, "push", message, "error", err[:200])

    return {"ok": all(r["ok"] for r in results), "results": results}


@app.post("/api/projects/batch-push")
def batch_push(ids: list[int] = None, message: str = Query("batch-update")):
    """推送多个项目"""
    db = get_db()
    if ids:
        placeholders = ",".join("?" * len(ids))
        projects = db.execute(f"SELECT * FROM projects WHERE id IN ({placeholders})", ids).fetchall()
    else:
        projects = db.execute("SELECT * FROM projects").fetchall()
    db.close()

    results = {}
    for p in projects:
        cwd = p["path"]
        _git("add -A", cwd)
        _git(f"commit -m {shlex.quote(message)}", cwd)
        _git(f"push origin {p['branch']}", cwd)
        results[str(p["id"])] = True
    return {"ok": True, "results": results}


# ═══════════════════════════════════════════
# API: Logs
# ═══════════════════════════════════════════
@app.get("/api/logs")
def list_logs(project_id: int = None, limit: int = 50):
    db = get_db()
    if project_id:
        rows = db.execute(
            "SELECT l.*, p.name as project_name FROM push_logs l LEFT JOIN projects p ON l.project_id=p.id WHERE l.project_id=? ORDER BY l.id DESC LIMIT ?",
            (project_id, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT l.*, p.name as project_name FROM push_logs l LEFT JOIN projects p ON l.project_id=p.id ORDER BY l.id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    db.close()
    return {"logs": [dict(r) for r in rows]}


# ═══════════════════════════════════════════
# API: Documents
# ═══════════════════════════════════════════
def _get_doc_dir(project: dict) -> str:
    """Get document directory for a project"""
    if project["docs_storage"] == "project":
        return os.path.join(project["path"], project["docs_path"])
    return os.path.join(DOCS_ROOT, project["name"])


@app.get("/api/projects/{pid}/docs")
def list_docs(pid: int):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    doc_dir = _get_doc_dir(dict(p))
    if not os.path.isdir(doc_dir):
        return {"files": [], "tree": []}

    def build_tree(d):
        items = []
        for entry in sorted(os.scandir(d), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith(".") or entry.name == "assets":
                continue
            if entry.is_dir():
                items.append({"name": entry.name, "type": "dir", "children": build_tree(entry.path)})
            elif entry.name.endswith(".md"):
                items.append({"name": entry.name, "type": "file", "size": entry.stat().st_size})
        return items

    tree = build_tree(doc_dir)
    files = []
    for root, dirs, fnames in os.walk(doc_dir):
        for fn in fnames:
            if fn.endswith(".md"):
                rp = os.path.relpath(os.path.join(root, fn), doc_dir)
                files.append({"name": fn, "path": rp, "size": os.path.getsize(os.path.join(root, fn))})

    return {"files": files, "tree": tree, "doc_dir": doc_dir}


@app.get("/api/projects/{pid}/docs/{path:path}")
def read_doc(pid: int, path: str):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    doc_dir = _get_doc_dir(dict(p))
    full_path = os.path.abspath(os.path.join(doc_dir, path))
    if not full_path.startswith(os.path.abspath(doc_dir)):
        raise HTTPException(403, "路径越界")

    if not os.path.isfile(full_path):
        raise HTTPException(404, "文档不存在")

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"path": path, "content": content, "size": len(content)}


@app.put("/api/projects/{pid}/docs/{path:path}")
def save_doc(pid: int, path: str, doc: DocSave):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    doc_dir = _get_doc_dir(dict(p))
    full_path = os.path.abspath(os.path.join(doc_dir, path))
    if not full_path.startswith(os.path.abspath(doc_dir)):
        raise HTTPException(403)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(doc.content)

    # Git commit if in git repo
    repo_root = doc_dir if p["docs_storage"] == "manager" else p["path"]
    if os.path.isdir(os.path.join(repo_root, ".git")):
        _git(f'add "{full_path}"', repo_root)
        _git(f'commit -m "docs: 更新 {path}"', repo_root)

    _log_action(pid, "doc_save", f"保存文档: {path}")
    return {"ok": True, "path": path}


@app.post("/api/projects/{pid}/docs")
def create_doc(pid: int, name: str = Query(...), folder: str = Query(""), template: str = Query("blank")):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    if not name.endswith(".md"):
        name += ".md"

    doc_dir = _get_doc_dir(dict(p))
    target_dir = os.path.join(doc_dir, folder) if folder else doc_dir
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, name)

    if os.path.exists(full_path):
        raise HTTPException(409, "文档已存在")

    templates = {
        "blank": f"# {name.replace('.md', '')}\n\n",
        "requirements": f"# {name.replace('.md', '')}\n\n## 背景\n\n## 功能需求\n\n## 验收标准\n\n",
        "design": f"# {name.replace('.md', '')}\n\n## 架构设计\n\n## 数据模型\n\n## 接口设计\n\n",
        "meeting": f"# {name.replace('.md', '')}\n\n**日期**: {datetime.now().strftime('%Y-%m-%d')}\n\n## 参会人\n\n## 议题\n\n## 决议\n\n",
    }
    content = templates.get(template, templates["blank"])

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    _log_action(pid, "doc_create", f"创建文档: {name}")
    rel_path = os.path.join(folder, name) if folder else name
    return {"ok": True, "path": rel_path, "content": content}


@app.delete("/api/projects/{pid}/docs/{path:path}")
def delete_doc(pid: int, path: str):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    doc_dir = _get_doc_dir(dict(p))
    full_path = os.path.abspath(os.path.join(doc_dir, path))
    if not full_path.startswith(os.path.abspath(doc_dir)):
        raise HTTPException(403)

    if os.path.isfile(full_path):
        os.remove(full_path)
    elif os.path.isdir(full_path):
        shutil.rmtree(full_path)

    _log_action(pid, "doc_delete", f"删除: {path}")
    return {"ok": True}


@app.get("/api/docs/search")
def search_docs(q: str = Query(...)):
    """全文搜索所有项目文档"""
    results = []
    db = get_db()
    projects = db.execute("SELECT * FROM projects").fetchall()
    db.close()

    for p in projects:
        p = dict(p)
        doc_dir = _get_doc_dir(p)
        if not os.path.isdir(doc_dir):
            continue
        for root, dirs, fnames in os.walk(doc_dir):
            for fn in fnames:
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                    if q.lower() in content.lower() or q.lower() in fn.lower():
                        rel = os.path.relpath(fp, doc_dir)
                        idx = content.lower().find(q.lower())
                        snippet = content[max(0, idx - 30):idx + 80].replace("\n", " ").strip()
                        results.append({
                            "project_id": p["id"],
                            "project_name": p["name"],
                            "path": rel,
                            "name": fn,
                            "snippet": f"...{snippet}..."
                        })
                except:
                    pass
    return {"results": results, "count": len(results)}


@app.get("/api/projects/{pid}/docs/{path:path}/history")
def doc_history(pid: int, path: str):
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    doc_dir = _get_doc_dir(dict(p))
    full_path = os.path.join(doc_dir, path)

    repo_root = doc_dir if p["docs_storage"] == "manager" else p["path"]
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return {"commits": []}

    rel = os.path.relpath(full_path, repo_root)
    out, err, code = _git(f"log --oneline -10 -- {shlex.quote(rel)}", repo_root)
    commits = []
    if out:
        for line in out.split("\n"):
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append({"hash": parts[0], "message": parts[1]})

    return {"commits": commits}


# ═══════════════════════════════════════════
# API: Remotes & Manager Self-Protection
# ═══════════════════════════════════════════
# ── Remotes ──────────────────────────────────
@app.get("/api/remotes")
def list_remotes():
    db = get_db()
    rows = db.execute("SELECT * FROM remotes ORDER BY created_at DESC").fetchall()
    db.close()
    return {"remotes": [dict(r) for r in rows]}


@app.post("/api/remotes")
def add_remote(r: RemoteIn):
    db = get_db()
    existing = db.execute("SELECT id FROM remotes WHERE url=?", (r.url,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(409, "远程已存在")
    db.execute("INSERT INTO remotes (name, url) VALUES (?,?)", (r.name, r.url))
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/api/remotes/{rid}")
def delete_remote(rid: int):
    db = get_db()
    db.execute("DELETE FROM remotes WHERE id=?", (rid,))
    db.commit()
    db.close()
    return {"ok": True}


# ── Self Status ─────────────────────────────
SELF_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))


@app.get("/api/self/status")
def self_status():
    """检查管理器自身 Git 状态"""
    if not os.path.isdir(os.path.join(SELF_DIR, ".git")):
        return {
            "is_git": False,
            "message": "管理器目录不是 Git 仓库",
            "remote_count": 0,
            "remotes": [],
        }

    # Get all remotes
    out, err, code = _git("remote -v", SELF_DIR)
    remotes = {}
    if out:
        for line in out.split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1].rstrip(")")
    remote_list = [{"name": k, "url": v} for k, v in remotes.items()]

    # Check current branch and status
    out2, _, _ = _git("branch --show-current", SELF_DIR)
    branch = out2.strip() if out2 else "unknown"

    status = check_git_status(SELF_DIR)

    return {
        "is_git": True,
        "branch": branch,
        "remote_count": len(remotes),
        "remotes": remote_list,
        "status": status,
    }


@app.post("/api/self/push")
def self_push(message: str = Query("manager-update"), remote: str = Query(None)):
    """推送管理器自身到远程仓库"""
    if not os.path.isdir(os.path.join(SELF_DIR, ".git")):
        raise HTTPException(400, "管理器目录不是 Git 仓库")

    results = []

    # Stage all
    _git("add -A", SELF_DIR)
    out, err, code = _git(f"commit -m {shlex.quote(message)}", SELF_DIR)
    if code == 0:
        results.append({"step": "commit", "ok": True, "output": out[:200]})
    elif "nothing to commit" in (out + err):
        results.append({"step": "commit", "ok": True, "output": "nothing to commit"})
    else:
        results.append({"step": "commit", "ok": False, "output": err[:200]})

    # Push to remotes
    if remote:
        remotes_to_push = [remote]
    else:
        out2, _, _ = _git("remote", SELF_DIR)
        remotes_to_push = [r for r in (out2.split("\n") if out2 else []) if r.strip()]

    if not remotes_to_push:
        return {"ok": all(r["ok"] for r in results), "results": results, "pushed_to": []}

    pushed_to = []
    for rmt in remotes_to_push:
        rmt = rmt.strip()
        if not rmt:
            continue
        out, err, code = _git(f"push {rmt} HEAD --force-with-lease", SELF_DIR, timeout=60)
        if code == 0:
            pushed_to.append(rmt)
            results.append({"step": f"push:{rmt}", "ok": True, "output": out[:200]})
        else:
            results.append({"step": f"push:{rmt}", "ok": False, "output": err[:200]})

    _log_action(0, "self_push", f"推送管理器到 {','.join(pushed_to) if pushed_to else '无'}")
    return {"ok": all(r["ok"] for r in results), "results": results, "pushed_to": pushed_to}


@app.post("/api/self/remote/{rid}/sync")
def self_sync_remote(rid: int):
    """同步配置的远程到管理器 git remote"""
    db = get_db()
    r = db.execute("SELECT * FROM remotes WHERE id=?", (rid,)).fetchone()
    db.close()
    if not r:
        raise HTTPException(404, "远程不存在")

    rmt_name = r["name"]
    rmt_url = r["url"]

    # Check if remote already exists
    out, _, _ = _git("remote", SELF_DIR)
    existing = [x.strip() for x in (out.split("\n") if out else [])]

    if rmt_name in existing:
        _git(f"remote set-url {rmt_name} {shlex.quote(rmt_url)}", SELF_DIR)
        action = "更新"
    else:
        _git(f"remote add {rmt_name} {shlex.quote(rmt_url)}", SELF_DIR)
        action = "添加"

    return {"ok": True, "action": action, "name": rmt_name}


# ── Backups ──────────────────────────────────
BACKUP_DIR = os.path.join(BASE_DIR, "..", "backups")


@app.get("/api/self/backups")
def list_backups():
    """列出所有备份"""
    db = get_db()
    rows = db.execute("SELECT * FROM backups ORDER BY created_at DESC").fetchall()
    db.close()

    backups = []
    for r in rows:
        b = dict(r)
        # Check if file still exists
        b["file_exists"] = os.path.isfile(b["file_path"])
        if b["file_exists"]:
            b["size_mb"] = round(os.path.getsize(b["file_path"]) / (1024 * 1024), 2)
        else:
            b["size_mb"] = 0
        backups.append(b)

    return {"backups": backups, "count": len(backups)}


@app.post("/api/self/backup")
def create_backup(name: str = Query(None), include_docs: bool = Query(True)):
    """立即创建备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = name or f"backup_{timestamp}"
    archive_base = os.path.join(BACKUP_DIR, backup_name)
    backup_file = archive_base + ".tar.gz"

    # Collect data to backup
    db = get_db()
    projects = db.execute("SELECT * FROM projects").fetchall()
    db.close()

    # Create a temp dir for backup contents
    tmp_dir = os.path.join(BACKUP_DIR, f".tmp_{timestamp}")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        # Export DB data
        export = {
            "version": "2.1",
            "timestamp": timestamp,
            "projects": [dict(p) for p in projects],
        }

        with open(os.path.join(tmp_dir, "manager_export.json"), "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)

        # Export docs if requested
        docs_count = 0
        if include_docs and os.path.isdir(DOCS_ROOT):
            docs_tmp = os.path.join(tmp_dir, "docs")
            shutil.copytree(DOCS_ROOT, docs_tmp, dirs_exist_ok=True)
            docs_count = sum(1 for _ in Path(docs_tmp).rglob("*.md"))

        # Create tar.gz
        shutil.make_archive(archive_base, "gztar",
            root_dir=os.path.dirname(tmp_dir),
            base_dir=os.path.basename(tmp_dir),
        )

        file_size = os.path.getsize(backup_file)

        # Save to DB
        db = get_db()
        db.execute(
            "INSERT INTO backups (name, file_path, size, projects_count, docs_count) VALUES (?,?,?,?,?)",
            (backup_name, backup_file, file_size, len(projects), docs_count),
        )
        db.commit()
        bid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()

        _log_action(0, "backup", f"创建备份: {backup_name} ({file_size / 1024 / 1024:.1f}MB)")
        return {
            "ok": True,
            "id": bid,
            "name": backup_name,
            "file": backup_file,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "projects_count": len(projects),
            "docs_count": docs_count,
        }
    finally:
        # Cleanup temp dir
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/self/restore/{bid}")
def restore_backup(bid: int):
    """从备份恢复"""
    db = get_db()
    backup = db.execute("SELECT * FROM backups WHERE id=?", (bid,)).fetchone()
    db.close()

    if not backup:
        raise HTTPException(404, "备份不存在")
    if not os.path.isfile(backup["file_path"]):
        raise HTTPException(404, "备份文件丢失")

    import tarfile

    tmp_dir = os.path.join(BACKUP_DIR, f".restore_{int(datetime.now().timestamp())}")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        with tarfile.open(backup["file_path"], "r:gz") as tar:
            tar.extractall(tmp_dir)

        # Read export
        export_file = os.path.join(tmp_dir, os.listdir(tmp_dir)[0], "manager_export.json")
        if not os.path.isfile(export_file):
            raise HTTPException(400, "备份文件格式无效")

        with open(export_file, "r", encoding="utf-8") as f:
            export = json.load(f)

        restored_projects = 0
        for proj in export.get("projects", []):
            db2 = get_db()
            existing = db2.execute("SELECT id FROM projects WHERE path=?", (proj["path"],)).fetchone()
            if not existing:
                db2.execute(
                    "INSERT INTO projects (name, path, type, remote_url, branch, docs_storage, docs_path, auto_push_docs) VALUES (?,?,?,?,?,?,?,?)",
                    (proj["name"], proj["path"], proj.get("type", "code"),
                     proj.get("remote_url", ""), proj.get("branch", "main"),
                     proj.get("docs_storage", "manager"), proj.get("docs_path", "docs"),
                     proj.get("auto_push_docs", 1)),
                )
                restored_projects += 1
            db2.commit()
            db2.close()

        # Restore docs
        restored_docs = 0
        docs_src = os.path.join(tmp_dir, os.listdir(tmp_dir)[0], "docs")
        if os.path.isdir(docs_src):
            if os.path.isdir(DOCS_ROOT):
                shutil.rmtree(DOCS_ROOT)
            shutil.copytree(docs_src, DOCS_ROOT)
            restored_docs = sum(1 for _ in Path(DOCS_ROOT).rglob("*.md"))

        _log_action(0, "restore", f"从备份恢复: {backup['name']} ({restored_projects}项目, {restored_docs}文档)")
        return {
            "ok": True,
            "backup_name": backup["name"],
            "restored_projects": restored_projects,
            "restored_docs": restored_docs,
        }
    finally:
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.delete("/api/self/backups/{bid}")
def delete_backup(bid: int):
    db = get_db()
    backup = db.execute("SELECT * FROM backups WHERE id=?", (bid,)).fetchone()
    if not backup:
        db.close()
        raise HTTPException(404)
    db.execute("DELETE FROM backups WHERE id=?", (bid,))
    db.commit()
    db.close()
    if os.path.isfile(backup["file_path"]):
        os.remove(backup["file_path"])
    return {"ok": True}


# ── Settings ─────────────────────────────────
@app.get("/api/self/settings")
def get_settings():
    db = get_db()
    rows = db.execute("SELECT * FROM settings").fetchall()
    db.close()
    return {"settings": {r["key"]: r["value"] for r in rows}}


@app.put("/api/self/settings")
def update_settings(settings: dict):
    db = get_db()
    for k, v in settings.items():
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,datetime('now','localtime'))",
            (k, str(v)),
        )
    db.commit()
    db.close()
    return {"ok": True}


# ── Image Upload ──────────────────────────
DOCS_UPLOADS_DIR = os.path.join(BASE_DIR, "..", "uploads", "docs")
os.makedirs(DOCS_UPLOADS_DIR, exist_ok=True)


@app.post("/api/projects/{pid}/docs/upload-image")
async def upload_doc_image(pid: int, file: UploadFile = File(...)):
    """上传文档图片（支持粘贴）"""
    db = get_db()
    p = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)

    # Validate image type
    ext = file.filename.split(".")[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
        ext = "png"

    # Save with unique name
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    safe_name = f"{p['name']}_{ts}_{uid}.{ext}"
    save_path = os.path.join(DOCS_UPLOADS_DIR, safe_name)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # Return the relative URL (served via the uploads mount below)
    url = f"/push/uploads/docs/{safe_name}"
    return {"ok": True, "url": url, "name": safe_name, "size": len(content)}


# Static mount for uploaded images (must be before SPA fallback)
UPLOADS_DIR = os.path.join(BASE_DIR, "..", "uploads")
if os.path.isdir(UPLOADS_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# ═══════════════════════════════════════════
# Health
# ═══════════════════════════════════════════
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "push-manager"}


# ═══════════════════════════════════════════
# Local paths quick select
# ═══════════════════════════════════════════
@app.get("/api/local-paths")
async def local_paths():
    """Return local project directories for path quick-select"""
    import glob
    project_dirs = []
    base = os.path.expanduser("~/projects")
    if os.path.isdir(base):
        for d in sorted(os.listdir(base)):
            full = os.path.join(base, d)
            if os.path.isdir(full) and not d.startswith("."):
                project_dirs.append(full)
    return {"paths": project_dirs}


# ═══════════════════════════════════════════
# Static Files & SPA
# ═══════════════════════════════════════════
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        fp = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(fp):
            return FileResponse(fp)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
