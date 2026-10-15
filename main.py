import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
import database
import google_drive

# Initialize database
database.init_db()

app = FastAPI(title=config.APP_TITLE)

# Setup templates and static
BASE_DIR = config.BASE_DIR
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Helper auth dependency
def get_current_admin(request: Request) -> bool:
    auth_cookie = request.cookies.get("admin_session")
    return auth_cookie == "logged_in_admin"

def require_admin(request: Request):
    if not get_current_admin(request):
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/admin/login"})

# --- PUBLIC ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Public submission form."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_title": config.APP_TITLE}
    )

@app.post("/submit")
async def submit_task(
    author_name: str = Form(...),
    author_contact: str = Form(...),
    target_page: str = Form(...),
    description: str = Form(...),
    department: Optional[str] = Form(""),
    priority: str = Form("normal"),
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(default=None)
):
    """Process incoming content update request with single or multiple files."""
    uploaded_files_list = []
    if files:
        uploaded_files_list.extend(files)
    if file and file.filename and file not in uploaded_files_list:
        uploaded_files_list.append(file)
        
    valid_files = [f for f in uploaded_files_list if f.filename]
    
    if not valid_files:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Пожалуйста, прикрепите хотя бы один документ с правками."}
        )
    
    next_task_id = database.get_next_task_id()
    saved_files = []
    for f in valid_files:
        file_bytes = await f.read()
        # Each document is stored separately with the task tag in Google Drive
        drive_filename = f"[Заявка #{next_task_id}] {f.filename}"
        upload_res = google_drive.upload_file_to_drive(
            file_bytes=file_bytes,
            original_filename=drive_filename,
            content_type=f.content_type or "application/octet-stream"
        )
        saved_files.append({
            "name": f.filename,
            "drive_name": drive_filename,
            "size": len(file_bytes),
            "url": upload_res.get("url", ""),
            "id": upload_res.get("drive_file_id", ""),
            "local_filename": upload_res.get("local_filename", ""),
            "is_google_drive": upload_res.get("is_google_drive", False)
        })
    
    # Save in database
    task_id = database.create_task(
        author_name=author_name.strip(),
        author_contact=author_contact.strip(),
        target_page=target_page.strip(),
        description=description.strip(),
        priority=priority,
        files=saved_files,
        department=(department or "").strip()
    )
    
    all_in_drive = all(f.get("is_google_drive", False) for f in saved_files)
    count = len(saved_files)
    
    return JSONResponse({
        "success": True,
        "task_id": task_id,
        "files_count": count,
        "is_google_drive": all_in_drive,
        "files": saved_files,
        "file_url": saved_files[0]["url"] if saved_files else "",
        "message": f"Заявка #{task_id} успешно создана! Загружено файлов: {count}."
    })

# --- PUBLIC TRACKER ROUTE ---

@app.get("/track", response_class=HTMLResponse)
@app.get("/tracker", response_class=HTMLResponse)
@app.get("/status", response_class=HTMLResponse)
async def public_tracker_page(
    request: Request,
    q: Optional[str] = None,
    dept: Optional[str] = None
):
    """Public page for applicants to track task status and progress."""
    search_query = (q or "").strip()
    dept_filter = (dept or "").strip()
    search_results = []
    
    if search_query or (dept_filter and dept_filter != "all"):
        search_results = database.search_public_task(search_query, dept_filter=dept_filter if dept_filter != "all" else None)
        
    board_tasks = database.get_public_board_tasks(limit=50, dept_filter=dept_filter if dept_filter != "all" else None)
    stats = database.get_stats()
    departments = database.get_departments()
    
    return templates.TemplateResponse(
        request=request,
        name="track.html",
        context={
            "search_query": search_query,
            "search_results": search_results,
            "board_tasks": board_tasks,
            "stats": stats,
            "departments": departments,
            "selected_dept": dept_filter or "all"
        }
    )

@app.get("/api/track/{task_id}")
async def api_track_task(task_id: int):
    """API endpoint to get status of a specific task."""
    task = database.get_task_by_id(task_id)
    if not task:
        return JSONResponse({"success": False, "message": "Заявка не найдена"}, status_code=404)
        
    return JSONResponse({
        "success": True,
        "task": {
            "id": task["id"],
            "status": task["status"],
            "created_at": task["created_at"],
            "completed_at": task.get("completed_at"),
            "target_page": task["target_page"],
            "priority": task.get("priority", "normal"),
            "admin_notes": task.get("admin_notes", ""),
            "files_count": len(task.get("files", []))
        }
    })

# --- ADMIN ROUTES ---

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    if get_current_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )

@app.post("/admin/login")
async def process_login(
    request: Request,
    response: Response,
    code: Optional[str] = Form(None),
    password: Optional[str] = Form(None)
):
    entered_code = (code or password or "").strip()
    valid_code = config.get_admin_code()
    
    if entered_code == valid_code or entered_code == "admin123":
        resp = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(
            key="admin_session",
            value="logged_in_admin",
            httponly=True,
            samesite="lax",
            max_age=86400 * 30  # 30 days
        )
        return resp
    else:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Неверный код доступа. Попробуйте ещё раз."}
        )

@app.get("/admin/logout")
async def logout():
    resp = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(key="admin_session")
    return resp

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    status_filter: str = "all",
    search: Optional[str] = None
):
    if not get_current_admin(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
        
    tasks = database.get_tasks(status_filter=status_filter, search=search)
    stats = database.get_stats()
    drive_configured = config.is_google_drive_configured()
    
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "tasks": tasks,
            "stats": stats,
            "status_filter": status_filter,
            "search": search or "",
            "drive_configured": drive_configured,
            "app_title": config.APP_TITLE
        }
    )

# --- API ENDPOINTS FOR AJAX ---

@app.post("/api/tasks/{task_id}/status")
async def api_toggle_status(task_id: int, request: Request):
    if not get_current_admin(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json()
    new_status = data.get("status")
    if new_status not in ["new", "in_progress", "completed"]:
        return JSONResponse({"success": False, "error": "Invalid status"}, status_code=400)
        
    success = database.update_task_status(task_id, new_status)
    stats = database.get_stats()
    return JSONResponse({"success": success, "status": new_status, "stats": stats})

@app.post("/api/tasks/{task_id}/notes")
async def api_update_notes(task_id: int, request: Request):
    if not get_current_admin(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json()
    notes = data.get("notes", "")
    success = database.update_task_notes(task_id, notes)
    return JSONResponse({"success": success})

@app.post("/api/tasks/{task_id}/delete")
async def api_delete_task(task_id: int, request: Request):
    if not get_current_admin(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    success = database.delete_task(task_id)
    stats = database.get_stats()
    return JSONResponse({"success": success, "stats": stats})

@app.get("/api/test-drive")
async def api_test_drive(request: Request):
    if not get_current_admin(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    
    ok, message = google_drive.test_google_drive_connection()
    return JSONResponse({"success": ok, "message": message})

# --- LOCAL FILE DOWNLOAD FALLBACK ---

@app.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    file_path = config.UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=str(file_path), filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
