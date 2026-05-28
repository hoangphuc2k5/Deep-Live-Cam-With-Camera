# --- START OF FILE globals.py ---
# File cấu hình toàn cục cho ứng dụng face swap
# Tối ưu cho: i5-14400 (16 luồng) + RTX 3060 12GB VRAM

import os
from typing import List, Dict, Any

# Đường dẫn gốc của dự án
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_DIR = os.path.join(ROOT_DIR, "workflow")

# Các loại file được phép nhập
file_types = [
    ("Image", ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp")),
    ("Video", ("*.mp4", "*.mkv")),
]

# Dữ liệu ánh xạ khuôn mặt
source_target_map: List[Dict[str, Any]] = []   # Lưu mapping chi tiết cho ảnh/video
simple_map: Dict[str, Any] = {}                # Lưu mapping đơn giản cho live/simple mode

# Đường dẫn file
source_path: str | None = None   # File nguồn (khuôn mặt cần swap)
target_path: str | None = None   # File đích (ảnh/video cần thay mặt)
output_path: str | None = None   # Thư mục hoặc file đầu ra

# -------------------- TÙY CHỌN XỬ LÝ --------------------
frame_processors: List[str] = []          # Danh sách bộ xử lý frame (VD: face_swapper, face_enhancer)
keep_fps: bool = True                     # Giữ nguyên FPS của video gốc
keep_audio: bool = True                   # Giữ nguyên âm thanh
keep_frames: bool = False                 # Không giữ các frame trung gian (tiết kiệm dung lượng)
many_faces: bool = False                  # False = chỉ swap khuôn mặt lớn nhất/được chọn; True = swap tất cả khuôn mặt (dùng source mặc định)
map_faces: bool = False                   # Dùng source_target_map để swap theo cặp cụ thể
poisson_blend: bool = True                # Bật poisson blending -> kết quả mượt, ít lộ biên
color_correction: bool = True             # Bật cân bằng màu sắc giữa mặt nguồn và mặt đích
nsfw_filter: bool = False                 # Không lọc nội dung nhạy cảm

# -------------------- XUẤT VIDEO --------------------
video_encoder: str | None = "h264_nvenc"  # Dùng NVENC của GPU (nhanh gấp 3-5 lần so với CPU)
video_quality: int | None = 18            # CRF/CQ: 18 = chất lượng cao (dung lượng vừa phải). Tăng lên 22-23 nếu muốn file nhẹ hơn.

# -------------------- LIVE MODE --------------------
live_mirror: bool = False                 # Không lật gương
live_resizable: bool = True               # Cho phép thay đổi kích thước cửa sổ live
camera_input_combobox: Any | None = None  # Dành cho UI
webcam_preview_running: bool = False
show_fps: bool = False                    # Không hiển thị FPS

# -------------------- CẤU HÌNH HỆ THỐNG --------------------
max_memory: int | None = None             # Không giới hạn RAM (để ONNX tự quản lý)
execution_providers: List[str] = [        # Thứ tự ưu tiên execution provider
    "CUDAExecutionProvider",              # Dùng GPU RTX 3060 (nhanh nhất)
    "CPUExecutionProvider"                # Fallback sang CPU nếu GPU lỗi
]
execution_threads: int | None = 8         # Số luồng CPU: i5-14400 có 16 luồng, để 8 tránh nghẽn và dành tài nguyên cho GPU
headless: bool | None = None              # None = tự động, không chạy headless
log_level: str = "error"                  # Chỉ hiển thị log lỗi (giảm tải I/O)

# -------------------- BỘ TĂNG CƯỜNG KHUÔN MẶT --------------------
# Bật/tắt các bộ tăng cường chất lượng mặt (tốn VRAM và thời gian)
fp_ui: Dict[str, bool] = {
    "face_enhancer": False,      # Tắt GFPGAN (tiết kiệm VRAM, tăng tốc)
    "face_enhancer_gpen256": False,
    "face_enhancer_gpen512": False
}

# -------------------- BỘ SWAP KHUÔN MẶT --------------------
face_swapper_enabled: bool = True   # Bật tính năng swap mặt
opacity: float = 1.0                # Độ mờ của mặt đã swap (1 = hoàn toàn)
sharpness: float = 0.0              # Không làm sắc nét thêm (tránh artifact)

# -------------------- TÙY CHỌN MẶT NẠ MIỆNG --------------------
mouth_mask: bool = False               # Tắt mask miệng (để swap toàn bộ mặt)
show_mouth_mask_box: bool = False      # Không hiển thị box debug
mask_feather_ratio: int = 12           # Tỉ lệ feather của mask (càng nhỏ càng mềm)
mask_down_size: float = 0.1            # Kích thước mở rộng cho môi dưới
mask_size: float = 1.0                 # Kích thước mở rộng cho môi trên
mouth_mask_size: float = 0.0           # Tắt mask miệng (0 = không dùng)

# -------------------- NỘI SUY FRAME (LÀM MƯỢT THỜI GIAN) --------------------
enable_interpolation: bool = False     # TẮT để tăng FPS xử lý, tránh giật hình
interpolation_weight: float = 0.0      # Trọng số frame hiện tại (0 = tắt)

# --- END OF FILE globals.py ---