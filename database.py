import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables and run lightweight migrations."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_contact TEXT NOT NULL,
            target_page TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            original_filename TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            drive_file_id TEXT DEFAULT '',
            drive_file_url TEXT NOT NULL,
            local_filename TEXT DEFAULT '',
            is_google_drive INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            completed_at TEXT DEFAULT NULL,
            admin_notes TEXT DEFAULT '',
            files_json TEXT DEFAULT '[]'
        )
    """)

    # Ensure files_json column exists if DB was created with older schema
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [col[1] for col in cursor.fetchall()]
    if "files_json" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN files_json TEXT DEFAULT '[]'")
    if "department" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN department TEXT DEFAULT ''")

    conn.commit()
    conn.close()

def _parse_task_row(row: sqlite3.Row) -> Dict[str, Any]:
    task = dict(row)
    
    # Department handling & smart fallback
    dept = (task.get("department") or "").strip()
    if not dept:
        author = task.get("author_name", "")
        if "(" in author and ")" in author:
            try:
                dept = author.split("(")[1].split(")")[0].strip()
            except Exception:
                dept = ""
        tp = (task.get("target_page") or "").lower()
        if not dept:
            if "quality" in tp or "качеств" in tp:
                dept = "Отдел качества"
            elif "market" in tp or "маркет" in tp:
                dept = "Отдел маркетинга"
            elif "decan" in tp or "декан" in tp:
                dept = "Деканат"
            elif "it" in tp or "ит" in tp:
                dept = "IT отдел"
            else:
                dept = "Общий отдел"
    task["department"] = dept

    files_raw = task.get("files_json") or "[]"
    try:
        parsed_files = json.loads(files_raw)
        if isinstance(parsed_files, list) and len(parsed_files) > 0:
            task["files"] = parsed_files
        else:
            task["files"] = [{
                "name": task.get("original_filename", "document"),
                "url": task.get("drive_file_url", "#"),
                "size": task.get("file_size", 0),
                "is_google_drive": bool(task.get("is_google_drive", 0))
            }]
    except Exception:
        task["files"] = [{
            "name": task.get("original_filename", "document"),
            "url": task.get("drive_file_url", "#"),
            "size": task.get("file_size", 0),
            "is_google_drive": bool(task.get("is_google_drive", 0))
        }]
    return task

def get_next_task_id() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tasks")
    next_id = cursor.fetchone()[0]
    conn.close()
    return next_id

def create_task(
    author_name: str,
    author_contact: str,
    target_page: str,
    description: str,
    priority: str,
    files: List[Dict[str, Any]],
    department: str = ""
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Primary file fields for backward compatibility
    primary_file = files[0] if files else {"name": "document", "url": "", "size": 0, "is_google_drive": False}
    if len(files) > 1:
        display_filename = f"{primary_file['name']} (+ ещё {len(files) - 1})"
    else:
        display_filename = primary_file['name']

    total_size = sum(f.get("size", 0) for f in files)
    is_drive_all = 1 if all(f.get("is_google_drive", False) for f in files) else 0
    files_json_str = json.dumps(files, ensure_ascii=False)
    dept_val = department.strip() if department else ""

    cursor.execute("""
        INSERT INTO tasks (
            created_at, author_name, author_contact, target_page,
            description, priority, original_filename, file_size,
            drive_file_id, drive_file_url, local_filename, is_google_drive, status, files_json, department
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
    """, (
        now_iso, author_name, author_contact, target_page,
        description, priority, display_filename, total_size,
        primary_file.get("id", ""), primary_file.get("url", ""),
        primary_file.get("local_filename", ""), is_drive_all, files_json_str, dept_val
    ))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_tasks(status_filter: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    
    if status_filter and status_filter != "all":
        if status_filter == "pending":
            query += " AND status IN ('new', 'in_progress')"
        else:
            query += " AND status = ?"
            params.append(status_filter)
            
    if search:
        search_param = f"%{search.strip()}%"
        query += " AND (author_name LIKE ? OR department LIKE ? OR target_page LIKE ? OR description LIKE ? OR original_filename LIKE ?)"
        params.extend([search_param, search_param, search_param, search_param, search_param])
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    tasks = [_parse_task_row(row) for row in rows]
    conn.close()
    return tasks

def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return _parse_task_row(row) if row else None

def update_task_status(task_id: int, new_status: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "completed" else None
    
    cursor.execute("""
        UPDATE tasks 
        SET status = ?, completed_at = ?
        WHERE id = ?
    """, (new_status, completed_at, task_id))
    
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def update_task_notes(task_id: int, notes: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET admin_notes = ? WHERE id = ?", (notes, task_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def delete_task(task_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected

def get_stats() -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'new'")
    new_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'in_progress'")
    in_progress = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "new": new_count,
        "in_progress": in_progress,
        "completed": completed,
        "pending": new_count + in_progress
    }

def search_public_task(query_str: str, dept_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search tasks for public tracking by task ID, contact, author name, or department."""
    clean_query = (query_str or "").strip()
    id_candidate = clean_query.lstrip("#")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Priority 1: Exact ID match
    if id_candidate.isdigit():
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (int(id_candidate),))
        rows = cursor.fetchall()
        if rows:
            conn.close()
            return [_parse_task_row(r) for r in rows]
            
    # Priority 2: Search across name, department, contact, or page
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if clean_query:
        param = f"%{clean_query}%"
        query += " AND (author_name LIKE ? OR department LIKE ? OR author_contact LIKE ? OR target_page LIKE ? OR description LIKE ?)"
        params.extend([param, param, param, param, param])

    if dept_filter and dept_filter != "all":
        query += " AND department = ?"
        params.append(dept_filter)

    query += " ORDER BY id DESC LIMIT 50"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [_parse_task_row(r) for r in rows]

def get_public_board_tasks(limit: int = 50, dept_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches recent tasks for public tracking overview, optionally filtered by department."""
    conn = get_connection()
    cursor = conn.cursor()
    if dept_filter and dept_filter != "all":
        cursor.execute("SELECT * FROM tasks WHERE department = ? ORDER BY id DESC LIMIT ?", (dept_filter, limit))
    else:
        cursor.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [_parse_task_row(r) for r in rows]

def get_departments() -> List[str]:
    """Returns sorted unique departments found in tasks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT department FROM tasks WHERE department IS NOT NULL AND department != ''")
    depts = [row[0].strip() for row in cursor.fetchall() if row[0] and row[0].strip()]
    conn.close()
    
    # Standard departments to recommend if none in DB yet
    defaults = ["Отдел качества", "Отдел маркетинга", "Деканат", "IT отдел", "Бухгалтерия", "Отдел кадров", "Пресс-служба"]
    all_depts = sorted(list(set(depts + defaults)))
    return all_depts
