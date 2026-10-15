import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

def reload_env():
    """Reloads environment variables from .env file."""
    load_dotenv(BASE_DIR / ".env", override=True)

# Initial load
reload_env()

# App settings
APP_TITLE = os.getenv("APP_TITLE", "Центр запросов на обновление контента")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "content-task-manager-super-secret-key-change-in-prod")

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# Dynamic getters to ensure changes in .env are always picked up immediately
def get_apps_script_url() -> str:
    reload_env()
    return os.getenv("GOOGLE_APPS_SCRIPT_URL", "").strip()

def get_drive_folder_id() -> str:
    reload_env()
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

def get_admin_password() -> str:
    reload_env()
    return os.getenv("ADMIN_PASSWORD", "admin123").strip()

def get_admin_code() -> str:
    reload_env()
    # Check ADMIN_CODE, then ADMIN_PIN, then ADMIN_PASSWORD, default '7788'
    return os.getenv("ADMIN_CODE") or os.getenv("ADMIN_PIN") or os.getenv("ADMIN_PASSWORD", "7788")

# Uploads directory (fallback if Google Drive credentials not present)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Database path
DB_PATH = BASE_DIR / "tasks.db"

def is_google_drive_configured() -> bool:
    """Checks if Google Apps Script webhook or Google Service Account is configured."""
    gas_url = get_apps_script_url()
    if gas_url and (gas_url.startswith("https://script.google.com") or "macros" in gas_url):
        return True
    cred_path = BASE_DIR / GOOGLE_SERVICE_ACCOUNT_FILE
    return cred_path.exists() and cred_path.stat().st_size > 50
