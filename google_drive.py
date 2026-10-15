import os
import io
import uuid
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

import config

logger = logging.getLogger("google_drive")
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Initializes Google Drive API service using service account credentials."""
    cred_path = config.BASE_DIR / config.GOOGLE_SERVICE_ACCOUNT_FILE
    if not cred_path.exists():
        raise FileNotFoundError(f"Service account file not found at {cred_path}")
    
    credentials = service_account.Credentials.from_service_account_file(
        str(cred_path),
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials)

def test_google_drive_connection() -> Tuple[bool, str]:
    """Tests Google Drive API connection and folder access."""
    gas_url = config.get_apps_script_url()
    if gas_url:
        try:
            res = httpx.get(gas_url, follow_redirects=True, timeout=15.0)
            if res.status_code == 200:
                return True, "Google Apps Script веб-сервис доступен и готов к приему файлов!"
            return True, f"Google Apps Script веб-сервис ответил с кодом {res.status_code}"
        except Exception as e:
            return False, f"Ошибка проверки Google Apps Script: {str(e)}"

    cred_path = config.BASE_DIR / config.GOOGLE_SERVICE_ACCOUNT_FILE
    if not cred_path.exists() or cred_path.stat().st_size <= 50:
        return False, "Файл ключа service_account.json не найден. Используется локальный режим."
    
    try:
        service = get_drive_service()
        folder_id = config.get_drive_folder_id()
        if folder_id:
            folder = service.files().get(
                fileId=folder_id,
                fields="id, name, mimeType"
            ).execute()
            return True, f"Успешное подключение к Google Диску! Папка: '{folder.get('name')}'"
        else:
            about = service.about().get(fields="user").execute()
            user_email = about.get("user", {}).get("emailAddress", "Сервисный аккаунт")
            return True, f"Подключено от имени: {user_email}. Папка не указана (загрузка в корень Диска)."
    except Exception as e:
        return False, f"Ошибка подключения к Google Drive: {str(e)}"

def upload_file_to_drive(
    file_bytes: bytes,
    original_filename: str,
    content_type: str = "application/octet-stream"
) -> Dict[str, Any]:
    """
    Uploads a file directly to Google Drive (via Google Apps Script webhook or Service Account).
    If Google Drive is not configured, saves locally in UPLOADS_DIR as fallback.
    """
    gas_url = config.get_apps_script_url()
    folder_id = config.get_drive_folder_id()

    # 1. Try Google Apps Script Webhook if configured
    if gas_url and (gas_url.startswith("https://script.google.com") or "macros" in gas_url):
        try:
            print(f"[GoogleDrive] Uploading '{original_filename}' ({len(file_bytes)} bytes) to Apps Script...")
            payload = {
                "filename": original_filename,
                "mimeType": content_type or "application/octet-stream",
                "folderId": folder_id,
                "base64": base64.b64encode(file_bytes).decode("utf-8")
            }
            response = httpx.post(
                gas_url,
                json=payload,
                follow_redirects=True,
                timeout=90.0
            )
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success"):
                    print(f"[GoogleDrive] Successfully uploaded to Google Drive! ID: {res_data.get('id')}")
                    return {
                        "success": True,
                        "is_google_drive": True,
                        "drive_file_id": res_data.get("id", ""),
                        "url": res_data.get("url", f"https://drive.google.com/drive/folders/{folder_id}"),
                        "local_filename": ""
                    }
                else:
                    print(f"[GoogleDrive] Apps Script returned error: {res_data}")
            else:
                print(f"[GoogleDrive] Apps Script returned status {response.status_code}: {response.text[:200]}")
        except Exception as gas_err:
            print(f"[GoogleDrive] Exception uploading to Google Apps Script: {gas_err}")

    # 2. Try Google Drive API (Service Account)
    cred_path = config.BASE_DIR / config.GOOGLE_SERVICE_ACCOUNT_FILE
    if cred_path.exists() and cred_path.stat().st_size > 50:
        try:
            service = get_drive_service()
            file_metadata = {'name': original_filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaIoBaseUpload(
                io.BytesIO(file_bytes),
                mimetype=content_type or "application/octet-stream",
                resumable=True
            )
            
            uploaded_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink'
            ).execute()
            
            file_id = uploaded_file.get('id')
            view_link = uploaded_file.get('webViewLink')
            
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
            except Exception as perm_err:
                logger.warning("Could not set public permission on Google Drive file: %s", perm_err)
                
            return {
                "success": True,
                "is_google_drive": True,
                "drive_file_id": file_id,
                "url": view_link or f"https://drive.google.com/file/d/{file_id}/view",
                "local_filename": ""
            }
        except Exception as e:
            print(f"[GoogleDrive] Exception uploading via Service Account: {e}")
    
    # 3. Local Fallback
    print(f"[GoogleDrive] Falling back to local storage for '{original_filename}'")
    safe_name = f"{uuid.uuid4().hex[:8]}_{original_filename.replace(' ', '_')}"
    target_path = config.UPLOADS_DIR / safe_name
    with open(target_path, "wb") as f:
        f.write(file_bytes)
        
    return {
        "success": True,
        "is_google_drive": False,
        "drive_file_id": "",
        "url": f"/uploads/{safe_name}",
        "local_filename": safe_name
    }
