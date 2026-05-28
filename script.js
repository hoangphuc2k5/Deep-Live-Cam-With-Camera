// ==================== AUTHENTICATION ====================

async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('login_error');
    
    if (!username || !password) {
        errorMsg.textContent = 'Vui lòng nhập tên người dùng và mật khẩu';
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('currentUser', username);
            showMainContent();
            loadUserInfo();
            loadUserVideos();
            loadCurrentProgress();
            errorMsg.textContent = '';
        } else {
            const error = await response.json();
            errorMsg.textContent = error.detail || 'Đăng nhập thất bại';
        }
    } catch (error) {
        errorMsg.textContent = 'Lỗi kết nối: ' + error.message;
    }
}

async function logout() {
    try {
        await fetch('/logout', { method: 'POST' });
        localStorage.removeItem('currentUser');
        stopProgressPolling();
        showLoginSection();
        resetForm();
    } catch (error) {
        console.error('Lỗi đăng xuất:', error);
    }
}

function showLoginSection() {
    document.getElementById('login_section').style.display = 'block';
    document.getElementById('main_section').style.display = 'none';
}

function showMainContent() {
    document.getElementById('login_section').style.display = 'none';
    document.getElementById('main_section').style.display = 'block';
}

// ==================== USER INFO & VIDEOS ====================

async function loadUserInfo() {
    try {
        const response = await fetch('/current_user');
        const data = await response.json();
        
        if (data.user) {
            document.getElementById('current_username').textContent = data.user.username;
            document.getElementById('video_count_info').textContent =
                `(${data.user.video_count} video)`;
        }
    } catch (error) {
        console.error('Lỗi tải thông tin user:', error);
    }
}

async function loadUserVideos() {
    try {
        const response = await fetch('/user_videos');
        if (!response.ok) {
            if (response.status === 401) {
                showLoginSection();
            }
            return;
        }
        
        const data = await response.json();
        const videoList = document.getElementById('video_list');
        
        if (!data.videos || data.videos.length === 0) {
            videoList.innerHTML = '<p class="empty-message">Chưa có video nào. Hãy tạo video đầu tiên!</p>';
            return;
        }
        
        let html = '<div class="video-items">';
        data.videos.forEach(video => {
            const date = new Date(video.created_at).toLocaleString('vi-VN');
            const type = video.type === 'image' ? '🖼️ Ảnh' : '🎬 Video';
            const safeRelativePath = String(video.filename || '')
                .replaceAll('\\', '/')
                .split('/')
                .map(segment => encodeURIComponent(segment))
                .join('/');
            const mediaUrl = `/static/video/${safeRelativePath}`;
            const mediaPreview = video.type === 'image'
                ? `<img class="video-preview-thumb" src="${mediaUrl}" alt="preview-${video.id}" loading="lazy">`
                : `<video class="video-preview-thumb" src="${mediaUrl}" controls preload="metadata"></video>`;
            const downloadName = video.type === 'image' ? 'result.png' : 'result.mp4';
            html += `
                <div class="video-item">
                    <div class="video-preview-wrap">
                        ${mediaPreview}
                    </div>
                    <div class="video-info">
                        <p><strong>${type}</strong></p>
                        <p class="video-file">${video.source_file}</p>
                        <p class="video-date">${date}</p>
                    </div>
                    <div class="video-actions">
                        <a class="download-item-btn" href="${mediaUrl}" download="${downloadName}">Tải xuống</a>
                        <button class="delete-btn" onclick="deleteVideo('${video.id}')">Xóa</button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        videoList.innerHTML = html;
        
        const totalVideosElement = document.getElementById('total_videos');
        if (totalVideosElement) {
            totalVideosElement.textContent = data.videos.length;
        }
    } catch (error) {
        console.error('Lỗi tải danh sách video:', error);
    }
}

async function deleteVideo(videoId) {
    if (!confirm('Bạn chắc chắn muốn xóa video này?')) {
        return;
    }
    
    try {
        const response = await fetch(`/delete_video?video_id=${videoId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            setStatus('Video đã được xóa');
            await loadUserVideos();
            await loadUserInfo();
        } else {
            setStatus('Lỗi xóa video');
        }
    } catch (error) {
        setStatus('Lỗi: ' + error.message);
    }
}

// ==================== PERSISTENT PROGRESS ====================

async function loadCurrentProgress() {
    try {
        const response = await fetch('/current_progress');
        if (!response.ok) return;
        
        const data = await response.json();
        if (data.progress) {
            const progress = data.progress;
            
            setStatus(`Tiến độ đã lưu: ${progress.message}`);
            setProgress(progress.message);
            
            if (progress.progress) {
                updateProgressBar(progress.progress);
            }
            
            if (progress.status === 'running' || progress.status === 'started') {
                showProgressLog();
                startProgressPolling();
            }

            if (progress.status === 'completed') {
                setStatus('Tác vụ trước đó đã hoàn thành. Video đã có trong thư viện.');
                await loadUserVideos();
                await loadUserInfo();
            }

            if (progress.status === 'failed') {
                setStatus(`Tác vụ trước đó thất bại: ${progress.message}`);
            }
        }
    } catch (error) {
        console.error('Lỗi tải tiến độ:', error);
    }
}

function updateProgressBar(percentage) {
    const progressFill = document.getElementById('progress_fill');
    if (progressFill) {
        progressFill.style.width = percentage + '%';
    }
}

// ==================== SETTINGS & STORAGE ====================

function saveSettings() {
    const settings = {
        keep_fps: document.getElementById('keep_fps').checked,
        keep_audio: document.getElementById('keep_audio').checked,
        multiple_faces: document.getElementById('multiple_faces').checked,
        show_fps: document.getElementById('show_fps').checked,
        poisson_blend: document.getElementById('poisson_blend').checked,
        face_mapping: document.getElementById('face_mapping').checked,
        face_enhancer: document.getElementById('face_enhancer').value,
        transparency: document.getElementById('transparency').value,
        sharpness: document.getElementById('sharpness').value,
        mouth_mask: document.getElementById('mouth_mask').value
    };
    localStorage.setItem('deepLiveCamSettings', JSON.stringify(settings));
}

function loadSettings() {
    const saved = localStorage.getItem('deepLiveCamSettings');
    if (saved) {
        const settings = JSON.parse(saved);
        document.getElementById('keep_fps').checked = settings.keep_fps || false;
        document.getElementById('keep_audio').checked = settings.keep_audio !== false; // default true
        document.getElementById('multiple_faces').checked = settings.multiple_faces || false;
        document.getElementById('show_fps').checked = settings.show_fps || false;
        document.getElementById('poisson_blend').checked = settings.poisson_blend || false;
        document.getElementById('face_mapping').checked = settings.face_mapping || false;
        document.getElementById('face_enhancer').value = settings.face_enhancer || 'none';
        document.getElementById('transparency').value = settings.transparency || 1.0;
        document.getElementById('sharpness').value = settings.sharpness || 0.0;
        document.getElementById('mouth_mask').value = settings.mouth_mask || 0.0;
        
        updateSliderValues();
    }
}

function updateSliderValues() {
    document.getElementById('transparency_val').textContent = document.getElementById('transparency').value;
    document.getElementById('sharpness_val').textContent = document.getElementById('sharpness').value;
    document.getElementById('mouth_mask_val').textContent = document.getElementById('mouth_mask').value;
}

// ==================== IMAGE/VIDEO PREVIEW ====================

function setupPreviewListeners() {
    // File inputs
    document.getElementById('image_source').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('source_preview').src = e.target.result;
                document.getElementById('source_preview').style.display = 'block';
                document.getElementById('source_error').style.display = 'none';
                // Clear URL input when file is selected
                document.getElementById('image_source_url').value = '';
            };
            reader.readAsDataURL(file);
        }
    });

    document.getElementById('image_target').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('target_preview').src = e.target.result;
                document.getElementById('target_preview').style.display = 'block';
                document.getElementById('target_error').style.display = 'none';
                // Clear URL input when file is selected
                document.getElementById('image_target_url').value = '';
            };
            reader.readAsDataURL(file);
        }
    });

    document.getElementById('video_target').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const url = URL.createObjectURL(file);
            document.getElementById('video_preview').src = url;
            document.getElementById('video_preview').style.display = 'block';
            document.getElementById('video_error').style.display = 'none';
            // Clear URL input when file is selected
            document.getElementById('video_target_url').value = '';
        }
    });

    // URL inputs
    document.getElementById('image_source_url').addEventListener('input', function(e) {
        const url = e.target.value.trim();
        if (url) {
            // Clear file input when URL is entered
            document.getElementById('image_source').value = '';
            document.getElementById('source_preview').style.display = 'none';
            previewFromUrl(url, 'source');
        } else {
            document.getElementById('source_preview').style.display = 'none';
            document.getElementById('source_error').style.display = 'none';
            document.getElementById('source_loading').style.display = 'none';
        }
    });

    document.getElementById('image_target_url').addEventListener('input', function(e) {
        const url = e.target.value.trim();
        if (url) {
            // Clear file input when URL is entered
            document.getElementById('image_target').value = '';
            document.getElementById('target_preview').style.display = 'none';
            previewFromUrl(url, 'target');
        } else {
            document.getElementById('target_preview').style.display = 'none';
            document.getElementById('target_error').style.display = 'none';
            document.getElementById('target_loading').style.display = 'none';
        }
    });

    document.getElementById('video_target_url').addEventListener('input', function(e) {
        const url = e.target.value.trim();
        if (url) {
            // Clear file input when URL is entered
            document.getElementById('video_target').value = '';
            document.getElementById('video_preview').style.display = 'none';
            previewVideoFromUrl(url);
        } else {
            document.getElementById('video_preview').style.display = 'none';
            document.getElementById('video_error').style.display = 'none';
            document.getElementById('video_loading').style.display = 'none';
        }
    });
}

async function previewFromUrl(url, type) {
    const preview = document.getElementById(`${type}_preview`);
    const error = document.getElementById(`${type}_error`);
    const loading = document.getElementById(`${type}_loading`);

    loading.style.display = 'block';
    preview.style.display = 'none';
    error.style.display = 'none';

    try {
        new URL(url);
        const img = new Image();
        img.crossOrigin = 'anonymous';

        const loadPromise = new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = () => reject(new Error('Image load failed'));
            img.src = url;
        });

        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Timeout')), 3000);
        });

        try {
            await Promise.race([loadPromise, timeoutPromise]);
            preview.src = url;
            preview.style.display = 'block';
            loading.style.display = 'none';
            error.style.display = 'none';
        } catch (imgErr) {
            console.warn('Direct image load failed, trying backend download:', imgErr);
            try {
                const response = await fetch(`/preview_image?url=${encodeURIComponent(url)}`);
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Backend download failed');
                }
                preview.src = data.local_url;
                preview.style.display = 'block';
                loading.style.display = 'none';
                error.style.display = 'none';
            } catch (backendErr) {
                console.error('Backend download also failed:', backendErr);
                loading.style.display = 'none';
                error.textContent = 'Không thể tải ảnh từ URL này';
                error.style.display = 'block';
            }
        }
    } catch (err) {
        loading.style.display = 'none';
        preview.style.display = 'none';
        error.textContent = 'URL không hợp lệ';
        error.style.display = 'block';
    }
}

async function previewVideoFromUrl(url) {
    const preview = document.getElementById('video_preview');
    const error = document.getElementById('video_error');
    const loading = document.getElementById('video_loading');

    loading.style.display = 'block';
    preview.style.display = 'none';
    error.style.display = 'none';

    try {
        new URL(url);

        const video = document.createElement('video');
        video.crossOrigin = 'anonymous';
        video.preload = 'metadata';

        const loadPromise = new Promise((resolve, reject) => {
            video.onloadedmetadata = resolve;
            video.onerror = () => reject(new Error('Video load failed'));
            video.src = url;
        });

        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Timeout')), 5000);
        });

        try {
            await Promise.race([loadPromise, timeoutPromise]);
            preview.src = url;
            preview.style.display = 'block';
            loading.style.display = 'none';
            error.style.display = 'none';
        } catch (videoErr) {
            console.warn('Direct video preview failed, trying backend download:', videoErr);
            try {
                const response = await fetch(`/preview_video?url=${encodeURIComponent(url)}`);
                const data = await response.json();

                if (response.ok && data.success) {
                    preview.src = data.local_url;
                    preview.style.display = 'block';
                    loading.style.display = 'none';
                    error.style.display = 'none';
                } else {
                    throw new Error(data.detail || 'Backend preview failed');
                }
            } catch (backendErr) {
                console.error('Video preview backend failed:', backendErr);
                loading.style.display = 'none';
                preview.style.display = 'none';
                error.textContent = 'Không thể tải video từ URL này hoặc URL không phải link trực tiếp đến file video.';
                error.style.display = 'block';
            }
        }
    } catch (err) {
        loading.style.display = 'none';
        preview.style.display = 'none';
        error.textContent = 'URL không hợp lệ';
        error.style.display = 'block';
    }
}

// ==================== STATUS & PROGRESS ====================

const statusMessage = document.getElementById('status_message');
const progressText = document.getElementById('progress_text');
const progressLog = document.getElementById('progress_log');
const progressLogContainer = document.querySelector('.progress-log-container');

// WebSocket for progress
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

ws.onopen = function() {
    console.log('WebSocket connected');
};

ws.onmessage = function(event) {
    const data = event.data;
    if (data.startsWith('progress:')) {
        const message = data.replace('progress:', '');
        setProgress(message);
    }
};

ws.onclose = function() {
    console.log('WebSocket closed');
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

function setStatus(message) {
    if (statusMessage) {
        statusMessage.textContent = message;
    }
}

function setProgress(message) {
    if (progressText) {
        progressText.textContent = message;
    }
    
    if (progressLog) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${message}\n`;
        progressLog.value += logEntry;
        progressLog.scrollTop = progressLog.scrollHeight;
    }
    
    const percentMatch = message.match(/(\d+)%/);
    if (percentMatch) {
        const percentage = parseInt(percentMatch[1]);
        updateProgressBar(percentage);
        document.getElementById('progress_bar').style.display = 'block';
    }
    
    if (message.includes('100%') || message.includes('failed') || message.includes('complete') || message.includes('canceled')) {
        setTimeout(() => {
            const progressBar = document.getElementById('progress_bar');
            if (progressBar) {
                progressBar.style.display = 'none';
            }
            hideProgressLog();
        }, 5000);
    }
}

function resetProgressBar() {
    const progressFill = document.getElementById('progress_fill');
    if (progressFill) {
        progressFill.style.width = '0%';
    }
    if (progressLog) {
        progressLog.value = '';
    }
}

function showProgressLog() {
    if (progressLogContainer) {
        progressLogContainer.style.display = 'block';
    }
}

function hideProgressLog() {
    if (progressLogContainer) {
        progressLogContainer.style.display = 'none';
    }
}

// ==================== PROCESSING ====================

let currentRequestController = null;
let progressPollTimer = null;

function stopProgressPolling() {
    if (progressPollTimer) {
        clearInterval(progressPollTimer);
        progressPollTimer = null;
    }
}

function startProgressPolling() {
    stopProgressPolling();
    progressPollTimer = setInterval(async () => {
        try {
            const response = await fetch('/current_progress');
            if (!response.ok) return;
            const data = await response.json();
            if (!data.progress) return;

            const progress = data.progress;
            if (progress.message) {
                setProgress(progress.message);
            }
            if (typeof progress.progress === 'number') {
                updateProgressBar(progress.progress);
            }

            if (progress.status === 'completed') {
                stopProgressPolling();
                setStatus('Xử lý video hoàn thành. Đã lưu vào thư viện.');
                await loadUserVideos();
                await loadUserInfo();
            } else if (progress.status === 'failed') {
                stopProgressPolling();
                setStatus(`Xử lý video thất bại: ${progress.message}`);
            }
        } catch (error) {
            console.error('Lỗi polling tiến độ:', error);
        }
    }, 2000);
}

function hasRequiredFiles(mode) {
    if (mode === 'image') {
        const hasSource = hasSourceInput();
        const hasTarget = hasTargetInput();
        return hasSource && hasTarget;
    }
    if (mode === 'video') {
        const hasSource = hasSourceInput();
        const hasVideo = hasVideoInput();
        return hasSource && hasVideo;
    }
    return false;
}

function hasSourceInput() {
    const fileInput = document.getElementById('image_source');
    const urlInput = document.getElementById('image_source_url');
    return fileInput.files[0] || (urlInput.value.trim() && urlInput.style.display !== 'none');
}

function hasTargetInput() {
    const fileInput = document.getElementById('image_target');
    const urlInput = document.getElementById('image_target_url');
    return fileInput.files[0] || (urlInput.value.trim() && urlInput.style.display !== 'none');
}

function hasVideoInput() {
    const fileInput = document.getElementById('video_target');
    const urlInput = document.getElementById('video_target_url');
    return fileInput.files[0] || (urlInput.value.trim() && urlInput.style.display !== 'none');
}

function showPreviewSection() {
    const previewVideo = document.getElementById('video_preview');
    const sourcePreview = document.getElementById('source_preview');
    const targetPreview = document.getElementById('target_preview');
    if (previewVideo.style.display === 'block') {
        previewVideo.scrollIntoView({ behavior: 'smooth' });
    } else if (targetPreview.style.display === 'block') {
        targetPreview.scrollIntoView({ behavior: 'smooth' });
    } else if (sourcePreview.style.display === 'block') {
        sourcePreview.scrollIntoView({ behavior: 'smooth' });
    }
}

function clearResult() {
    const resultImage = document.getElementById('result_image');
    const resultVideo = document.getElementById('result_video');
    if (resultImage) resultImage.style.display = 'none';
    if (resultVideo) resultVideo.style.display = 'none';
    if (resultVideo) resultVideo.src = '';
    if (resultImage) resultImage.src = '';
    const downloadLink = document.getElementById('download_link');
    if (downloadLink) downloadLink.style.display = 'none';
}

async function processImage() {
    if (!hasRequiredFiles('image')) {
        setStatus('Vui lòng chọn ảnh nguồn và ảnh mục tiêu trước khi bắt đầu.');
        return;
    }

    const formData = new FormData();
    
    // Add source image (file or URL)
    if (document.getElementById('image_source').files[0]) {
        formData.append('image_source', document.getElementById('image_source').files[0]);
    } else {
        formData.append('image_source_url', document.getElementById('image_source_url').value.trim());
    }
    
    // Add target image (file or URL)
    if (document.getElementById('image_target').files[0]) {
        formData.append('image_target', document.getElementById('image_target').files[0]);
    } else {
        formData.append('image_target_url', document.getElementById('image_target_url').value.trim());
    }
    
    formData.append('keep_fps', document.getElementById('keep_fps').checked);
    formData.append('keep_audio', document.getElementById('keep_audio').checked);
    formData.append('multiple_faces', document.getElementById('multiple_faces').checked);
    formData.append('show_fps', document.getElementById('show_fps').checked);
    formData.append('poisson_blend', document.getElementById('poisson_blend').checked);
    formData.append('face_mapping', document.getElementById('face_mapping').checked);
    formData.append('transparency', document.getElementById('transparency').value);
    formData.append('sharpness', document.getElementById('sharpness').value);
    formData.append('mouth_mask', document.getElementById('mouth_mask').value);
    formData.append('face_enhancer', document.getElementById('face_enhancer').value);

    document.getElementById('loading').style.display = 'block';
    setStatus('Đang xử lý ảnh... Vui lòng chờ.');
    setProgress('Processing: 0% | | 0/0');
    resetProgressBar();
    showProgressLog();
    clearResult();

    currentRequestController = new AbortController();

    try {
        const response = await fetch('/process_image', {
            method: 'POST',
            body: formData,
            signal: currentRequestController.signal
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const resultImage = document.getElementById('result_image');
            resultImage.src = url;
            resultImage.style.display = 'block';
            document.getElementById('result_video').style.display = 'none';
            const downloadLink = document.getElementById('download_link');
            downloadLink.href = url;
            downloadLink.download = 'output.png';
            downloadLink.style.display = 'inline-block';
            setStatus('Swap ảnh thành công. Có thể xem và tải về. Video đã được lưu vào thư viện.');
            setProgress('Processing: 100% | █ | 1/1');
            document.getElementById('result').style.display = 'block';
            
            await loadUserVideos();
            await loadUserInfo();
        } else {
            setStatus('Lỗi xử lý ảnh: ' + response.statusText);
            setProgress('Processing failed.');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            setStatus('Đã hủy tác vụ.');
            setProgress('Processing canceled.');
        } else {
            setStatus('Lỗi: ' + error.message);
            setProgress('Processing failed.');
        }
    } finally {
        document.getElementById('loading').style.display = 'none';
        currentRequestController = null;
    }
}

async function exportVideo() {
    if (!hasRequiredFiles('video')) {
        setStatus('Vui lòng chọn ảnh nguồn và video mục tiêu trước khi xuất video.');
        return;
    }

    const formData = new FormData();
    
    // Add source image (file or URL)
    if (document.getElementById('image_source').files[0]) {
        formData.append('image_source', document.getElementById('image_source').files[0]);
    } else {
        formData.append('image_source_url', document.getElementById('image_source_url').value.trim());
    }
    
    // Add target image (file or URL, optional)
    if (document.getElementById('image_target').files[0]) {
        formData.append('image_target', document.getElementById('image_target').files[0]);
    } else if (document.getElementById('image_target_url').value.trim()) {
        formData.append('image_target_url', document.getElementById('image_target_url').value.trim());
    }
    
    // Add video target (file or URL)
    if (document.getElementById('video_target').files[0]) {
        formData.append('video_target', document.getElementById('video_target').files[0]);
    } else {
        formData.append('video_target_url', document.getElementById('video_target_url').value.trim());
    }
    
    formData.append('keep_fps', document.getElementById('keep_fps').checked);
    formData.append('keep_audio', document.getElementById('keep_audio').checked);
    formData.append('multiple_faces', document.getElementById('multiple_faces').checked);
    formData.append('show_fps', document.getElementById('show_fps').checked);
    formData.append('poisson_blend', document.getElementById('poisson_blend').checked);
    formData.append('face_mapping', document.getElementById('face_mapping').checked);
    formData.append('transparency', document.getElementById('transparency').value);
    formData.append('sharpness', document.getElementById('sharpness').value);
    formData.append('mouth_mask', document.getElementById('mouth_mask').value);
    formData.append('face_enhancer', document.getElementById('face_enhancer').value);
    
    document.getElementById('loading').style.display = 'block';
    setStatus('Đang xuất video... Vui lòng chờ.');
    setProgress('Processing: 0% | | 0/0');
    resetProgressBar();
    showProgressLog();
    clearResult();

    currentRequestController = new AbortController();

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData,
            signal: currentRequestController.signal
        });
        
        if (response.ok) {
            const data = await response.json();
            setStatus(data.message || 'Đã bắt đầu xử lý video nền.');
            setProgress(`Đã tạo tác vụ: ${data.task_id}`);
            showProgressLog();
            startProgressPolling();
        } else {
            setStatus('Lỗi xử lý: ' + response.statusText);
            setProgress('Processing failed.');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            setStatus('Đã hủy tác vụ.');
        } else {
            setStatus('Lỗi: ' + error.message);
        }
    } finally {
        document.getElementById('loading').style.display = 'none';
        currentRequestController = null;
    }
}

// ==================== EVENT LISTENERS ====================

function setupEventListeners() {
    // Login
    document.getElementById('login_btn').addEventListener('click', login);
    document.getElementById('username').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });
    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });
    
    // Logout
    document.getElementById('logout_btn').addEventListener('click', logout);
    
    // Settings
    document.getElementById('keep_fps').addEventListener('change', saveSettings);
    document.getElementById('keep_audio').addEventListener('change', saveSettings);
    document.getElementById('multiple_faces').addEventListener('change', saveSettings);
    document.getElementById('show_fps').addEventListener('change', saveSettings);
    document.getElementById('poisson_blend').addEventListener('change', saveSettings);
    document.getElementById('face_mapping').addEventListener('change', saveSettings);
    document.getElementById('face_enhancer').addEventListener('change', saveSettings);
    document.getElementById('transparency').addEventListener('input', function() {
        updateSliderValues();
        saveSettings();
    });
    document.getElementById('sharpness').addEventListener('input', function() {
        updateSliderValues();
        saveSettings();
    });
    document.getElementById('mouth_mask').addEventListener('input', function() {
        updateSliderValues();
        saveSettings();
    });
    
    // Processing
    document.getElementById('start').addEventListener('click', processImage);
    document.getElementById('export').addEventListener('click', exportVideo);
    document.getElementById('stop').addEventListener('click', function() {
        if (currentRequestController) {
            currentRequestController.abort();
            setStatus('Đã hủy tác vụ.');
        } else {
            setStatus('Không có tác vụ xử lý đang chạy.');
        }
    });
    document.getElementById('preview').addEventListener('click', function() {
        const hasSource = !!document.getElementById('image_source').files[0];
        const hasTargetImage = !!document.getElementById('image_target').files[0];
        const hasVideo = !!document.getElementById('video_target').files[0];
        if (!hasSource && !hasTargetImage && !hasVideo) {
            setStatus('Chọn file trước khi xem trước.');
            return;
        }
        setStatus('Hiển thị xem trước file đã chọn.');
        showPreviewSection();
    });
}

function resetForm() {
    stopProgressPolling();
    document.getElementById('image_source').value = '';
    document.getElementById('image_target').value = '';
    document.getElementById('video_target').value = '';
    document.getElementById('image_source_url').value = '';
    document.getElementById('image_target_url').value = '';
    document.getElementById('video_target_url').value = '';
    document.getElementById('source_preview').style.display = 'none';
    document.getElementById('target_preview').style.display = 'none';
    document.getElementById('video_preview').style.display = 'none';
    document.getElementById('source_error').style.display = 'none';
    document.getElementById('target_error').style.display = 'none';
    document.getElementById('video_error').style.display = 'none';
    document.getElementById('source_loading').style.display = 'none';
    document.getElementById('target_loading').style.display = 'none';
    document.getElementById('video_loading').style.display = 'none';
    clearResult();
    setStatus('Chưa có hành động.');
    resetProgressBar();
}

// ==================== INIT ====================

document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    setupPreviewListeners();
    loadSettings();
    
    // Check if user is already logged in
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
        showMainContent();
        loadUserInfo();
        loadUserVideos();
        loadCurrentProgress();
    } else {
        showLoginSection();
    }
});
