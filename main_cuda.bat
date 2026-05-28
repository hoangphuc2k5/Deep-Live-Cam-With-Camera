@echo off
setlocal

cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [ERROR] Khong tim thay venv\Scripts\activate.bat
    pause
    exit /b 1
)

set "CUDNN_BIN=%CD%\venv\Lib\site-packages\nvidia\cudnn\bin"
if exist "%CUDNN_BIN%\cudnn64_9.dll" (
    set "PATH=%CUDNN_BIN%;%PATH%"
) else (
    echo [WARN] Khong tim thay cudnn64_9.dll trong:
    echo        %CUDNN_BIN%
    echo        Se thu chay tiep, co the se fallback CPU.
)

echo [INFO] Dang chay Deep-Live-Cam voi CUDA...
python main.py --execution-provider cuda

endlocal
