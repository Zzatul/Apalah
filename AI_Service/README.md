# 🧠 Panduan Layanan AI: Neural Network Rekomendasi Pupuk & Mitigasi Emisi CH₄

Layanan mikro (*microservice*) cerdas berbasis **Artificial Neural Network (PyTorch Multi-Task Deep Learning)** untuk memprediksi rekomendasi dosis pupuk (Urea & NPK) dan mengklasifikasikan tingkat aerasi/reduksi tanah berdasarkan sampel lingkungan dari IoT Smart Chamber.

---

## 📁 Struktur Folder
```text
AI_Service/
├── dataset/
│   ├── generate_dataset.py      # Script generator dataset simulasi agronomi
│   └── dataset_pupuk_padi.csv   # Dataset sampel dan label dosis
├── models/
│   ├── model_ann.pth            # Bobot terlatih jaringan syaraf tiruan
│   └── scaler.pkl               # Pengingat skala normalisasi fitur (MinMaxScaler)
├── model.py                     # Definisi arsitektur PyTorch Multi-Task ANN
├── train.py                     # Skrip training, loss optimasi, & evaluasi metrik
├── api_service.py               # REST API FastAPI (Port 8000)
├── test_api.py                  # Unit testing inferensi lokal & endpoint HTTP
├── requirements.txt             # Dependensi Python
└── run_service.bat              # Skrip one-click startup di Windows
```

---

## 🚀 Cara Menjalankan

### 1. Cara Cepat (Windows)
Cukup klik ganda (*double-click*) file `run_service.bat`. Skrip ini otomatis mengecek dependensi, melatih model awal jika belum ada, dan menyalakan server di `http://127.0.0.1:8000`.

### 2. Cara Manual (Terminal / Command Prompt)
```bash
# Masuk ke direktori AI_Service
cd "d:\BASE CORE\Main Data Research\PROJECT CORE\IsT Project\AI_Service"

# 1. Install Dependensi (Jika belum)
pip install -r requirements.txt

# 2. Buat Dataset & Latih Model
python train.py

# 3. Jalankan Server API
python api_service.py
```

---

## 📡 Dokumentasi Endpoint REST API

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Status keaktifan server & ketersediaan model AI. |
| `GET` | `/api/model-info` | Informasi detail arsitektur model dan rentang fitur. |
| `POST` | `/api/predict` | Inferensi real-time dari data sensor (Metana, Suhu, Lembap, Tekanan, HST). |
| `POST` | `/api/retrain` | Menerima data feedback lapangan baru dan melatih ulang model (*continuous learning*). |

---

## 🌾 Penjelasan Parameter & Arsitektur Model

* **Input Features (5 Parameter):**
  1. `gas_metana` (ppm)
  2. `suhu` (°C)
  3. `kelembaban` (%RH)
  4. `tekanan` (hPa)
  5. `hst_hari` (Hari Setelah Tanam)

* **Dual-Head Output:**
  1. **Regresi Dosis:** Dosis Urea (kg/Ha) & Dosis NPK (kg/Ha)
  2. **Klasifikasi Kondisi Lahan:** Aman (`0`), Waspada (`1`), Kritis (`2`) + Confidence Score (%)
