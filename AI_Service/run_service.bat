@echo off
title IoT Smart Chamber - AI Fertilizer Neural Network Service
echo ======================================================================
echo    IoT Smart Chamber - AI Fertilizer Neural Network Service
echo    Framework: PyTorch + FastAPI (Port 8000)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Memeriksa Python & Dependensi...
python -c "import fastapi, torch, sklearn, pandas, uvicorn; print('   -> Semua dependensi siap!')" 2>nul
if %errorlevel% neq 0 (
    echo [!] Menginstall dependensi yang diperlukan...
    pip install -r requirements.txt
)

echo.
echo [2/3] Memeriksa Model Terlatih (model_ann.pth)...
if not exist "models\model_ann.pth" (
    echo [!] Model belum ditemukan. Memulai pelatihan awal...
    python train.py
)

echo.
echo [3/3] Menjalankan Server API FastAPI di http://127.0.0.1:8000 ...
echo [i] Tekan CTRL + C untuk menghentikan server.
echo.
python -m uvicorn api_service:app --host 127.0.0.1 --port 8000 --reload
pause
