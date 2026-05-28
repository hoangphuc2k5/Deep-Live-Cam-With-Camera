from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks, WebSocket, Cookie, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
import tempfile
import os
import shutil
from typing import Optional, Any, Dict
import sys
import modules.core as core
import modules.globals
import subprocess
import threading
import asyncio
import re
import json
import secrets
import uuid
from datetime import datetime
from pathlib import Path
import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.platform.startswith("win"):
    # Avoid Proactor-specific connection reset noise on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ==================== DATABASE MANAGEMENT ====================
DB_FILE = os.path.join(ROOT_DIR, "database.json")
VIDEO_STORAGE_DIR = os.path.join(ROOT_DIR, "video")
TASK_STORAGE_DIR = os.path.join(ROOT_DIR, "task_storage")

os.makedirs(VIDEO_STORAGE_DIR, exist_ok=True)
os.makedirs(TASK_STORAGE_DIR, exist_ok=True)

def load_database():
    """Load database from JSON file"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db = json.load(f)
                # Backward-compatible migration for older database.json schemas.
                if not isinstance(db, dict):
                    raise ValueError("Invalid database format")
                db.setdefault("users", {})
                db.setdefault("sessions", {})
                db.setdefault("processing_tasks", {})
                for user_data in db["users"].values():
                    if isinstance(user_data, dict):
                        user_data.setdefault("videos", [])
                        user_data.setdefault("current_processing", None)
                return db
        except:
            pass
    # Return default database if file doesn't exist
    return {
        "users": {
            "khach1": {"password": "123@123@456@!", "created_at": str(datetime.now()), "videos": [], "current_processing": None},
            "khach2": {"password": "123@123@456@!", "created_at": str(datetime.now()), "videos": [], "current_processing": None}
        },
        "sessions": {},
        "processing_tasks": {}
    }

def save_database(db):
    """Save database to JSON file"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving database: {e}")
        return False

def create_session_token(username):
    """Create a new session token for user"""
    token = secrets.token_urlsafe(32)
    db = load_database()
    db["sessions"][token] = {
        "username": username,
        "created_at": str(datetime.now()),
        "last_accessed": str(datetime.now())
    }
    save_database(db)
    return token

def verify_session(token):
    """Verify if session token is valid"""
    if not token:
        return None
    db = load_database()
    if token in db["sessions"]:
        return db["sessions"][token]["username"]
    return None

def get_user_videos(username):
    """Get list of videos for a user"""
    db = load_database()
    if username in db["users"]:
        return db["users"][username].get("videos", [])
    return []

def add_video_to_user(username, video_data):
    """Add video to user's list."""
    db = load_database()
    if username not in db["users"]:
        return False
    
    db["users"][username]["videos"].append(video_data)
    return save_database(db)

def delete_user_video(username, video_id):
    """Delete a specific video for user"""
    db = load_database()
    if username not in db["users"]:
        return False
    
    videos = db["users"][username]["videos"]
    for i, v in enumerate(videos):
        if v["id"] == video_id:
            video_path = os.path.join(VIDEO_STORAGE_DIR, v["filename"])
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
            videos.pop(i)
            return save_database(db)
    return False

def start_processing_task(username, task_id, task_type, parameters=None):
    """Start a processing task for user"""
    db = load_database()
    if username not in db["users"]:
        return False
    
    task_data = {
        "id": task_id,
        "type": task_type,
        "status": "running",
        "progress": 0,
        "message": "Bắt đầu xử lý...",
        "start_time": str(datetime.now()),
        "parameters": parameters or {}
    }
    
    db.setdefault("processing_tasks", {})
    db["users"][username]["current_processing"] = task_data
    db["processing_tasks"][task_id] = {
        "username": username,
        "task_data": task_data
    }
    return save_database(db)

def update_processing_progress(task_id, progress, message):
    """Update processing progress"""
    db = load_database()
    db.setdefault("processing_tasks", {})
    if task_id not in db["processing_tasks"]:
        return False
    
    username = db["processing_tasks"][task_id]["username"]
    if username not in db["users"]:
        return False
    
    if not db["users"][username].get("current_processing"):
        db["users"][username]["current_processing"] = {"id": task_id, "type": "video"}
    db["users"][username]["current_processing"]["progress"] = progress
    db["users"][username]["current_processing"]["message"] = message
    db["users"][username]["current_processing"]["last_update"] = str(datetime.now())
    
    return save_database(db)

def finish_processing_task(task_id, status="completed", message="Hoàn thành"):
    """Finish a processing task"""
    db = load_database()
    db.setdefault("processing_tasks", {})
    if task_id not in db["processing_tasks"]:
        return False
    
    username = db["processing_tasks"][task_id]["username"]
    if username not in db["users"]:
        return False
    
    if not db["users"][username].get("current_processing"):
        db["users"][username]["current_processing"] = {"id": task_id, "type": "video"}
    db["users"][username]["current_processing"]["status"] = status
    db["users"][username]["current_processing"]["message"] = message
    db["users"][username]["current_processing"]["finish_time"] = str(datetime.now())
    if status == "completed":
        db["users"][username]["current_processing"]["progress"] = 100
    
    # Keep it for a while before clearing
    db["processing_tasks"][task_id]["finished"] = True
    
    return save_database(db)

def get_user_current_processing(username):
    """Get current processing task for user"""
    db = load_database()
    if username not in db["users"]:
        return None
    return db["users"][username].get("current_processing")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()
MAIN_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


def handle_loop_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Ignore expected connection resets from clients closing partial content streams."""
    exception = context.get("exception")
    if isinstance(exception, (ConnectionResetError, BrokenPipeError)):
        return
    loop.default_exception_handler(context)


app = FastAPI()

# Create temp directory for downloaded images
TEMP_IMAGE_DIR = os.path.join(ROOT_DIR, "temp")
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="."), name="static")


@app.on_event("startup")
async def capture_main_loop() -> None:
    global MAIN_EVENT_LOOP
    MAIN_EVENT_LOOP = asyncio.get_running_loop()
    MAIN_EVENT_LOOP.set_exception_handler(handle_loop_exception)


def broadcast_progress(message: str) -> None:
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        future = asyncio.run_coroutine_threadsafe(manager.broadcast(message), MAIN_EVENT_LOOP)
        try:
            future.result(timeout=2)
        except Exception:
            pass


def sanitize_filename(filename: str) -> str:
    return os.path.basename(filename) if filename else "unknown_file"


async def download_from_url(url: str, dest_dir: str, filename_prefix: str, expected_type: str = 'auto') -> str:
    """Download file from URL and save to destination directory"""
    try:
        # Validate URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        
        # Try to get content-type with HEAD request and User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        content_type = ''
        try:
            response = requests.head(url, timeout=10, allow_redirects=True, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get('content-type', '').lower()
        except Exception as e:
            print(f"HEAD request failed for {url}: {e}, will try GET instead")
        
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.ts', '.wmv', '.mpeg', '.mpg']
        
        # Determine file extension
        if 'image' in content_type:
            if 'png' in content_type:
                ext = '.png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'
            else:
                ext = '.png'
        elif 'video' in content_type:
            if 'mp4' in content_type:
                ext = '.mp4'
            elif 'avi' in content_type:
                ext = '.avi'
            elif 'mov' in content_type:
                ext = '.mov'
            elif 'webm' in content_type:
                ext = '.webm'
            elif 'mkv' in content_type:
                ext = '.mkv'
            else:
                ext = '.mp4'
        else:
            path = parsed.path
            ext = os.path.splitext(path)[1].lower()
            if not ext:
                if expected_type == 'video':
                    ext = '.mp4'
                else:
                    ext = '.jpg'
            if ext not in image_exts + video_exts:
                if expected_type == 'video':
                    ext = '.mp4'
                else:
                    ext = '.jpg'
        
        filename = f"{filename_prefix}{ext}"
        filename = sanitize_filename(filename)
        filepath = os.path.join(dest_dir, filename)
        
        # Download file with GET request
        response = requests.get(url, timeout=30, stream=True, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if os.path.getsize(filepath) == 0:
            os.remove(filepath)
            raise ValueError("Downloaded file is empty")

        if expected_type == 'video':
            with open(filepath, 'rb') as f:
                header = f.read(16)

            is_video = False
            if header.startswith(b'\x00\x00\x00') and b'ftyp' in header:
                is_video = True
            elif header.startswith(b'RIFF') and header[8:12] in [b'AVI ', b'WEBP']:
                is_video = True
            elif header.startswith(b'\x1A\x45\xDF\xA3'):
                is_video = True
            elif header.startswith(b'FLV'):
                is_video = True

            if not is_video:
                os.remove(filepath)
                raise ValueError("URL phải là link trực tiếp tới file video hợp lệ")

        # For images, try to validate with PIL
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']
        if ext in image_exts:
            try:
                from PIL import Image
                with Image.open(filepath) as img:
                    img.verify()
                    img.close()
            except Exception as e:
                try:
                    with open(filepath, 'rb') as f:
                        header = f.read(16)

                    if header.startswith(b'\xff\xd8\xff'):
                        real_ext = '.jpg'
                    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
                        real_ext = '.png'
                    elif header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
                        real_ext = '.gif'
                    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
                        real_ext = '.webp'
                    elif header.startswith(b'BM'):
                        real_ext = '.bmp'
                    else:
                        raise ValueError(f"Unknown image format, header: {header[:4].hex()}")

                    if real_ext != ext:
                        new_filename = f"{filename_prefix}{real_ext}"
                        new_filename = sanitize_filename(new_filename)
                        new_filepath = os.path.join(dest_dir, new_filename)
                        os.rename(filepath, new_filepath)
                        filepath = new_filepath
                        print(f"Renamed file from {ext} to {real_ext} based on content")

                    with Image.open(filepath) as img:
                        img.verify()
                except Exception as e2:
                    os.remove(filepath)
                    raise ValueError(f"Downloaded file is not a valid image: {str(e)}, {str(e2)}")
        
        return filepath
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tải file từ URL: {str(e)}")


def build_process_command(
    source_path: str,
    target_path: str,
    output_path: str,
    keep_fps: bool,
    keep_audio: bool,
    multiple_faces: bool,
    show_fps: bool,
    poisson_blend: bool,
    face_mapping: bool,
    mouth_mask: float,
    frame_processors: list[str],
) -> list[str]:
    cmd = [
        sys.executable,
        os.path.join(ROOT_DIR, "run.py"),
        "--source",
        source_path,
        "--target",
        target_path,
        "--output",
        output_path,
    ]
    if keep_fps:
        cmd.append("--keep-fps")
    if keep_audio:
        cmd.append("--keep-audio")
    if multiple_faces:
        cmd.append("--many-faces")
    if show_fps:
        cmd.append("--show-fps")
    if poisson_blend:
        cmd.append("--poisson-blend")
    if face_mapping:
        cmd.append("--map-faces")
    if mouth_mask > 0:
        cmd.append("--mouth-mask")
    cmd.extend(["--frame-processor"] + frame_processors)
    cmd.extend(["--execution-provider", "cuda"])
    cmd.extend(["--lang", "vi"])
    return cmd


def run_video_task(task_id: str, username: str, payload: Dict[str, Any]) -> None:
    temp_dir = payload["temp_dir"]
    output_path = payload["output_path"]
    source_filename = payload["source_filename"]
    video_filename_original = payload["video_filename_original"]
    cmd = payload["cmd"]
    parameters = payload["parameters"]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            cwd=ROOT_DIR,
        )

        while True:
            line = process.stdout.readline() if process.stdout else ""
            if not line and process.poll() is not None:
                break
            if not line:
                continue
            msg = line.strip()
            print(msg)
            if "Processing" in msg:
                match = re.search(r"(\d+)%", msg)
                progress = int(match.group(1)) if match else 0
                update_processing_progress(task_id, progress, msg)
                broadcast_progress(f"progress:{msg}")

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"Subprocess exited with code {return_code}")

        if not os.path.exists(output_path):
            raise RuntimeError("Không tìm thấy file video đầu ra")

        user_video_dir = os.path.join(VIDEO_STORAGE_DIR, username)
        os.makedirs(user_video_dir, exist_ok=True)

        video_id = str(uuid.uuid4())
        video_filename = f"{video_id}_video.mp4"
        saved_path = os.path.join(user_video_dir, video_filename)
        shutil.copy2(output_path, saved_path)

        video_data = {
            "id": video_id,
            "filename": os.path.join(username, video_filename),
            "type": "video",
            "created_at": str(datetime.now()),
            "source_file": source_filename,
            "video_file": video_filename_original,
            "parameters": parameters,
        }
        add_video_to_user(username, video_data)
        finish_processing_task(task_id, "completed", "Xử lý video hoàn thành")
        broadcast_progress("progress:Processing: 100% | █ | done")
    except Exception as e:
        finish_processing_task(task_id, "failed", f"Lỗi: {str(e)}")
        broadcast_progress(f"progress:Lỗi xử lý video: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# ==================== IMAGE PREVIEW ENDPOINT ====================

@app.get("/preview_image")
async def preview_image(url: str):
    """Download image from URL and return local URL for preview"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="URL không hợp lệ")

        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        temp_filename = f"preview_{url_hash}"

        local_path = await download_from_url(url, TEMP_IMAGE_DIR, temp_filename, expected_type='image')
        filename = os.path.basename(local_path)
        return {"success": True, "local_url": f"/static/temp/{filename}"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tải ảnh: {str(e)}")

@app.get("/preview_video")
async def preview_video(url: str):
    """Download video from URL and return local URL for preview"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="URL không hợp lệ")

        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        temp_filename = f"preview_video_{url_hash}"

        local_path = await download_from_url(url, TEMP_IMAGE_DIR, temp_filename, expected_type='video')
        filename = os.path.basename(local_path)
        return {"success": True, "local_url": f"/static/temp/{filename}"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tải video: {str(e)}")

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Login endpoint"""
    db = load_database()
    
    if username not in db["users"]:
        raise HTTPException(status_code=401, detail="Tên người dùng không tồn tại")
    
    user = db["users"][username]
    if user["password"] != password:
        raise HTTPException(status_code=401, detail="Mật khẩu không đúng")
    
    # Create session token
    token = create_session_token(username)
    response = JSONResponse({
        "token": token,
        "username": username,
        "message": f"Đăng nhập thành công. Chào mừng {username}!"
    })
    response.set_cookie("session_token", token, httponly=True, max_age=7*24*60*60)
    return response

@app.post("/logout")
async def logout(response: Response):
    """Logout endpoint"""
    response.delete_cookie("session_token")
    return {"message": "Đã đăng xuất"}

@app.get("/current_user")
async def get_current_user(session_token: str = Cookie(None)):
    """Get current logged-in user"""
    if not session_token:
        return JSONResponse({"user": None})
    
    username = verify_session(session_token)
    if not username:
        return JSONResponse({"user": None})
    
    videos = get_user_videos(username)
    return JSONResponse({
        "user": {
            "username": username,
            "video_count": len(videos)
        }
    })

@app.get("/user_videos")
async def user_videos(session_token: str = Cookie(None)):
    """Get list of videos for current user"""
    username = verify_session(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    videos = get_user_videos(username)
    return JSONResponse({"videos": videos})

@app.delete("/delete_video")
async def delete_video(video_id: str, session_token: str = Cookie(None)):
    """Delete a video for current user"""
    username = verify_session(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    if delete_user_video(username, video_id):
        return JSONResponse({"message": "Video đã bị xóa"})
    else:
        raise HTTPException(status_code=404, detail="Video không tìm thấy")

@app.get("/current_progress")
async def get_current_progress(session_token: str = Cookie(None)):
    """Get current processing progress for user"""
    username = verify_session(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    progress = get_user_current_processing(username)
    if progress:
        return JSONResponse({"progress": progress})
    else:
        return JSONResponse({"progress": None})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.post("/process")
async def process_video(
    image_source: UploadFile = File(None),
    image_target: Optional[UploadFile] = File(None),
    video_target: UploadFile = File(None),
    image_source_url: str = Form(None),
    image_target_url: str = Form(None),
    video_target_url: str = Form(None),
    keep_fps: bool = Form(False),
    keep_audio: bool = Form(True),
    multiple_faces: bool = Form(False),
    show_fps: bool = Form(False),
    poisson_blend: bool = Form(False),
    face_mapping: bool = Form(False),
    transparency: float = Form(1.0),
    sharpness: float = Form(0.0),
    mouth_mask: float = Form(0.0),
    face_enhancer: str = Form("none"),
    session_token: str = Cookie(None)
):
    # Verify session
    username = verify_session(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Validate inputs
    if not ((image_source and image_source.filename) or image_source_url):
        raise HTTPException(status_code=400, detail="Cần có ảnh nguồn (file hoặc URL)")
    if not ((video_target and video_target.filename) or video_target_url):
        raise HTTPException(status_code=400, detail="Cần có video mục tiêu (file hoặc URL)")
    
    # Start processing task tracking
    task_id = str(uuid.uuid4())
    start_processing_task(username, task_id, "video", {
        "face_enhancer": face_enhancer,
        "transparency": transparency,
        "sharpness": sharpness,
        "mouth_mask": mouth_mask,
        "keep_fps": keep_fps,
        "keep_audio": keep_audio,
        "multiple_faces": multiple_faces
    })
    
    # Save uploaded files to a persistent task folder
    task_dir = os.path.join(TASK_STORAGE_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # Handle source image
    if image_source and image_source.filename:
        source_filename = sanitize_filename(image_source.filename)
        source_path = os.path.join(task_dir, source_filename)
        with open(source_path, "wb") as f:
            shutil.copyfileobj(image_source.file, f)
    elif image_source_url:
        source_filename = image_source_url  # Use URL as filename for tracking
        source_path = await download_from_url(image_source_url, task_dir, "source_image", expected_type='image')
    else:
        raise HTTPException(status_code=400, detail="Không có ảnh nguồn hợp lệ")
    
    # Handle target image (optional)
    target_path = None
    if image_target and image_target.filename:
        target_filename = sanitize_filename(image_target.filename)
        target_path = os.path.join(task_dir, target_filename)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(image_target.file, f)
    elif image_target_url:
        target_path = await download_from_url(image_target_url, task_dir, "target_image", expected_type='image')
    
    # Handle video target
    if video_target and video_target.filename:
        video_filename_original = sanitize_filename(video_target.filename)
        video_path = os.path.join(task_dir, video_filename_original)
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video_target.file, f)
    elif video_target_url:
        video_path = await download_from_url(video_target_url, task_dir, "target_video", expected_type='video')
        video_filename_original = os.path.basename(video_path)
    else:
        raise HTTPException(status_code=400, detail="Không có video mục tiêu hợp lệ")

    output_path = os.path.join(task_dir, "output.mp4")
    print(f"[process_video] task_dir={task_dir}")
    print(f"[process_video] source={source_path} exists={os.path.exists(source_path)}")
    print(f"[process_video] video={video_path} exists={os.path.exists(video_path)}")
    print(f"[process_video] output={output_path}")
    frame_processors = [face_enhancer] if face_enhancer != "none" else ["face_swapper"]
    if not core.pre_check():
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
        finish_processing_task(task_id, "failed", "Server pre-check failed")
        raise HTTPException(status_code=500, detail="Server pre-check failed. Please ensure ffmpeg is installed and Python 3.9+.")

    parameters = {
        "face_enhancer": face_enhancer,
        "transparency": transparency,
        "sharpness": sharpness,
        "mouth_mask": mouth_mask,
        "keep_fps": keep_fps,
        "keep_audio": keep_audio,
        "multiple_faces": multiple_faces,
    }
    cmd = build_process_command(
        source_path=source_path,
        target_path=video_path,
        output_path=output_path,
        keep_fps=keep_fps,
        keep_audio=keep_audio,
        multiple_faces=multiple_faces,
        show_fps=show_fps,
        poisson_blend=poisson_blend,
        face_mapping=face_mapping,
        mouth_mask=mouth_mask,
        frame_processors=frame_processors,
    )

    worker = threading.Thread(
        target=run_video_task,
        args=(
            task_id,
            username,
            {
                "temp_dir": task_dir,
                "output_path": output_path,
                "source_filename": source_filename,
                "video_filename_original": video_filename_original,
                "cmd": cmd,
                "parameters": parameters,
            },
        ),
        daemon=True,
    )
    worker.start()

    return JSONResponse(
        {
            "task_id": task_id,
            "status": "started",
            "message": "Đã bắt đầu xử lý video ở chế độ nền. Bạn có thể thoát ra và vào lại để xem tiến trình.",
        }
    )

@app.post("/process_image")
async def process_image(
    background_tasks: BackgroundTasks,
    image_source: UploadFile = File(None),
    image_target: UploadFile = File(None),
    image_source_url: str = Form(None),
    image_target_url: str = Form(None),
    keep_fps: bool = Form(False),
    keep_audio: bool = Form(True),
    multiple_faces: bool = Form(False),
    show_fps: bool = Form(False),
    poisson_blend: bool = Form(False),
    face_mapping: bool = Form(False),
    transparency: float = Form(1.0),
    sharpness: float = Form(0.0),
    mouth_mask: float = Form(0.0),
    face_enhancer: str = Form("none"),
    session_token: str = Cookie(None)
):
    # Verify session
    username = verify_session(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Validate inputs
    if not ((image_source and image_source.filename) or image_source_url):
        raise HTTPException(status_code=400, detail="Cần có ảnh nguồn (file hoặc URL)")
    if not ((image_target and image_target.filename) or image_target_url):
        raise HTTPException(status_code=400, detail="Cần có ảnh mục tiêu (file hoặc URL)")
    
    # Start processing task tracking
    task_id = str(uuid.uuid4())
    start_processing_task(username, task_id, "image", {
        "face_enhancer": face_enhancer,
        "transparency": transparency,
        "sharpness": sharpness,
        "mouth_mask": mouth_mask
    })
    
    temp_dir = tempfile.mkdtemp()
    
    # Handle source image
    if image_source and image_source.filename:
        source_path = os.path.join(temp_dir, image_source.filename)
        with open(source_path, "wb") as f:
            shutil.copyfileobj(image_source.file, f)
    elif image_source_url:
        source_path = await download_from_url(image_source_url, temp_dir, "source_image", expected_type='image')
    else:
        raise HTTPException(status_code=400, detail="Không có ảnh nguồn hợp lệ")
    
    # Handle target image
    if image_target and image_target.filename:
        target_path = os.path.join(temp_dir, image_target.filename)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(image_target.file, f)
    elif image_target_url:
        target_path = await download_from_url(image_target_url, temp_dir, "target_image", expected_type='image')
    else:
        raise HTTPException(status_code=400, detail="Không có ảnh mục tiêu hợp lệ")
    
    output_path = os.path.join(temp_dir, "output.png")
    print(f"[process_image] temp_dir={temp_dir}")
    print(f"[process_image] source={source_path} exists={os.path.exists(source_path)}")
    print(f"[process_image] target={target_path} exists={os.path.exists(target_path)}")
    print(f"[process_image] output={output_path}")
    
    modules.globals.source_path = source_path
    modules.globals.target_path = target_path
    modules.globals.output_path = output_path
    modules.globals.keep_fps = keep_fps
    modules.globals.keep_audio = keep_audio
    modules.globals.many_faces = multiple_faces
    modules.globals.show_fps = show_fps
    modules.globals.poisson_blend = poisson_blend
    modules.globals.map_faces = face_mapping
    modules.globals.opacity = transparency
    modules.globals.sharpness = sharpness
    modules.globals.mouth_mask_size = mouth_mask
    modules.globals.frame_processors = [face_enhancer] if face_enhancer != "none" else ["face_swapper"]
    modules.globals.headless = True
    modules.globals.execution_providers = core.suggest_execution_providers()
    modules.globals.video_encoder = 'libx264'
    modules.globals.video_quality = 18
    modules.globals.execution_threads = core.suggest_execution_threads()
    core.limit_resources()
    if not core.pre_check():
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail="Server pre-check failed. Please ensure ffmpeg is installed and Python 3.9+.")
    
    # Build command for image
    cmd = [sys.executable, os.path.join(ROOT_DIR, "run.py"), "--source", source_path, "--target", target_path, "--output", output_path]
    if keep_fps:
        cmd.append("--keep-fps")
    if keep_audio:
        cmd.append("--keep-audio")
    if multiple_faces:
        cmd.append("--many-faces")
    if show_fps:
        cmd.append("--show-fps")
    if poisson_blend:
        cmd.append("--poisson-blend")
    if face_mapping:
        cmd.append("--map-faces")
    if mouth_mask > 0:
        cmd.append("--mouth-mask")
    cmd.extend(["--frame-processor"] + modules.globals.frame_processors)
    cmd.extend(["--execution-provider", "cuda"])
    cmd.extend(["--lang", "vi"])
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'},
            cwd=ROOT_DIR,
        )

        main_loop = asyncio.get_running_loop()

        def broadcast_done(fut):
            exc = fut.exception()
            if exc is not None:
                print(f"DEBUG: Failed to broadcast progress: {exc}")

        def send_progress(line: str):
            if "Processing" not in line:
                return
            msg = line.strip()
            
            # Extract progress percentage
            match = re.search(r'(\d+)%', msg)
            progress = int(match.group(1)) if match else 0
            
            # Update task progress in database
            update_processing_progress(task_id, progress, msg)
            
            future = asyncio.run_coroutine_threadsafe(
                manager.broadcast(f"progress:{msg}"),
                main_loop,
            )
            future.add_done_callback(broadcast_done)

        def read_output():
            buffer = ""
            while True:
                char = process.stdout.read(1)
                if not char:
                    break
                print(char, end='')
                buffer += char
                if char == '\r' or char == '\n':
                    line = buffer.strip()
                    if line:
                        send_progress(line)
                    buffer = ""
            process.stdout.close()
            process.wait()

        await main_loop.run_in_executor(None, read_output)

        if process.returncode != 0:
            raise RuntimeError(f"Subprocess exited with code {process.returncode}")

        if os.path.exists(output_path):
            # Save to user's video directory
            user_video_dir = os.path.join(VIDEO_STORAGE_DIR, username)
            os.makedirs(user_video_dir, exist_ok=True)
            
            video_id = str(uuid.uuid4())
            video_filename = f"{video_id}_image.png"
            saved_path = os.path.join(user_video_dir, video_filename)
            print(f"[process_image] copying {output_path} to {saved_path}")
            shutil.copy2(output_path, saved_path)
            print(f"[process_image] saved_path exists: {os.path.exists(saved_path)}")
            
            # Add to database
            source_file = image_source.filename if image_source else image_source_url
            video_data = {
                "id": video_id,
                "filename": os.path.join(username, video_filename),
                "type": "image",
                "created_at": str(datetime.now()),
                "source_file": source_file,
                "parameters": {
                    "face_enhancer": face_enhancer,
                    "transparency": transparency,
                    "sharpness": sharpness,
                    "mouth_mask": mouth_mask
                }
            }
            print(f"[process_image] adding video_data: {video_data}")
            add_video_to_user(username, video_data)
            
            # Finish processing task
            finish_processing_task(task_id, "completed", "Xử lý ảnh hoàn thành")
            
            background_tasks.add_task(shutil.rmtree, temp_dir)
            
            # Return file content directly
            print(f"[process_image] returning FileResponse for {saved_path}")
            return FileResponse(saved_path, media_type='image/png', filename='output.png')
        else:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            finish_processing_task(task_id, "failed", "Xử lý ảnh thất bại")
            raise HTTPException(status_code=500, detail="Image processing failed")
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        finish_processing_task(task_id, "failed", f"Lỗi: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
