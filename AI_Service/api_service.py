"""
Layanan REST API FastAPI: Inference & Retraining ANN IoT Smart Chamber
Menyediakan endpoint untuk inferensi rekomendasi dosis pupuk dan klasifikasi kondisi lahan secara real-time.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import torch
import joblib
import numpy as np
import pandas as pd
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from model import FertilizerMultiTaskANN
from train import train_model

app = FastAPI(
    title="IoT Smart Chamber - AI Fertilizer Recommendation API",
    description="Layanan AI berbasis Multi-Task ANN (PyTorch) untuk rekomendasi pemupukan dan mitigasi gas metana CH4.",
    version="1.0.0"
)

# Konfigurasi CORS agar frontend web dapat mengakses API secara bebas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model_ann.pth")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.pkl")
DATASET_PATH = os.path.join(BASE_DIR, "dataset", "dataset_pupuk_padi.csv")

# Global variables model
scaler = None
model = None

def load_ai_model():
    global scaler, model
    try:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            print("[INFO] Model/Scaler belum ditemukan. Memulai pelatihan otomatis awal...")
            train_model()
            
        scaler = joblib.load(SCALER_PATH)
        m = FertilizerMultiTaskANN(input_dim=5)
        m.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
        m.eval()
        model = m
        print("[OK] Model PyTorch ANN & Scaler berhasil dimuat ke memori!")
    except Exception as e:
        print(f"[ERROR] Gagal memuat model: {str(e)}")

# Load model saat startup
load_ai_model()

# --- SCHEMA / REQUEST-RESPONSE MODELS ---

class SensorPredictRequest(BaseModel):
    gas_metana: float = Field(..., example=327.5, description="Konsentrasi gas CH4 dalam ppm")
    suhu: float = Field(..., example=28.5, description="Suhu tanah/air dalam °C")
    kelembaban: float = Field(..., example=75.0, description="Kelembaban relatif %RH")
    tekanan: float = Field(..., example=1013.25, description="Tekanan barometrik hPa")
    hst_hari: Optional[float] = Field(30.0, example=30.0, description="Hari Setelah Tanam (Fase Tanam Padi)")
    chamber_id: Optional[str] = Field("Chamber 1", example="Chamber 1")
    crop_name: Optional[str] = Field("Padi Sawah", example="Padi Sawah")
    crop_variety: Optional[str] = Field("Inpari 32", example="Inpari 32")

class PredictResponse(BaseModel):
    engine: str = "PyTorch Deep ANN (Multi-Task)"
    status: str
    status_text: str
    status_class: str
    confidence: float
    confidence_class: str
    status_desc: str
    action_status: str
    action_class: str
    dosis_urea_kg_ha: float
    dosis_npk_kg_ha: float
    dosis_rekomendasi_utama: float
    urea_text: str
    npk_text: str
    saran_tindakan: str
    input_received: dict

class RetrainRecord(BaseModel):
    gas_metana: float
    suhu: float
    kelembaban: float
    tekanan: float
    hst_hari: float
    dosis_urea: float
    dosis_npk: float
    status_lahan: int # 0=Aman, 1=Waspada, 2=Kritis
    notes: Optional[str] = None

# --- ENDPOINTS ---

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "IoT Chamber AI Fertilizer API",
        "framework": "PyTorch + FastAPI",
        "model_loaded": model is not None,
        "scaler_loaded": scaler is not None
    }

@app.get("/api/model-info")
def model_info():
    return {
        "model_type": "Multi-Task Feedforward Artificial Neural Network",
        "framework": "PyTorch 2.x",
        "input_features": ["gas_metana (ppm)", "suhu (°C)", "kelembaban (%RH)", "tekanan (hPa)", "hst_hari (HST)"],
        "outputs": {
            "regression": ["dosis_urea (kg/Ha)", "dosis_npk (kg/Ha)"],
            "classification": ["status_lahan (0=Aman, 1=Waspada, 2=Kritis)", "confidence (%)"]
        },
        "description": "Model cerdas pemantauan emisi metan dan optimasi dosis nutrisi tanaman padi."
    }

@app.post("/api/predict", response_model=PredictResponse)
def predict_fertilizer(req: SensorPredictRequest):
    global model, scaler
    if model is None or scaler is None:
        load_ai_model()
        if model is None or scaler is None:
            raise HTTPException(status_code=500, detail="Model ANN belum siap atau gagal dimuat.")

    try:
        # 1. Normalisasi Input
        raw_x = np.array([[req.gas_metana, req.suhu, req.kelembaban, req.tekanan, req.hst_hari]])
        scaled_x = scaler.transform(raw_x)
        tensor_x = torch.tensor(scaled_x, dtype=torch.float32)

        # 2. Forward Propagation
        with torch.no_grad():
            doses, status_logits = model(tensor_x)
            
            # Hitung Probabilitas dengan Softmax
            probs = torch.softmax(status_logits, dim=1).numpy()[0]
            status_idx = int(np.argmax(probs))
            confidence = round(float(probs[status_idx]) * 100, 1)

            # Hitung Dosis
            doses_out = doses.numpy()[0]
            pred_urea = max(0.0, round(float(doses_out[0]), 1))
            pred_npk = max(0.0, round(float(doses_out[1]), 1))

        # 3. Post-Processing & Kaidah Agronomi
        if status_idx == 0: # AMAN
            status = "Aman"
            status_text = "Aman (Kondisi Aerobik Optimal)"
            status_class = "badge-aman"
            action_status = "Waktu Optimal Pemupukan"
            action_class = "action-optimal"
            confidence_class = "bg-success"
            status_desc = f"Model PyTorch ANN memproyeksikan efisiensi aerasi tanah sangat tinggi pada {req.chamber_id} ({req.crop_name} - {req.crop_variety}). Emisi metana rendah ({req.gas_metana} ppm), tanah siap menyerap pemupukan secara maksimal tanpa memicu pelepasan gas metana berlebih."
            saran = "Waktu pemupukan sangat tepat. Disarankan aplikasi pada pagi hari (06.30 - 09.00) atau sore hari. Pertahankan ketinggian air dangkal / macak-macak (1-2 cm) agar pupuk terserap sempurna ke rizosfer."
        elif status_idx == 1: # WASPADA
            status = "Waspada"
            status_text = "Waspada Anaerobik (Reduksi Tanah Meningkat)"
            status_class = "badge-waspada"
            action_status = "Kurangi Dosis 50%"
            action_class = "action-reduce"
            confidence_class = "bg-warning"
            pred_urea = round(pred_urea * 0.5, 1)
            pred_npk = round(pred_npk * 0.5, 1)
            status_desc = f"Inferensi PyTorch ANN mendeteksi peningkatan dekomposisi bahan organik anaerobik ({req.gas_metana} ppm). Rekomendasi dosis dikurangi 50% untuk mencegah pelepasan gas CH₄ dan kehilangan nitrogen secara sia-sia."
            saran = "Kurangi dosis pemupukan menjadi 50%. Disarankan melakukan pengeringan lahan sementara (intermittent aeration / pengeringan parit) selama 2-3 hari untuk memasukkan suplai oksigen ke zona perakaran."
        else: # KRITIS
            status = "Kritis"
            status_text = "Kritis / Toksik Anaerobik (Akumulasi Gas Metan Tinggi)"
            status_class = "badge-kritis"
            action_status = "Tunda Pemupukan"
            action_class = "action-delay"
            confidence_class = "bg-danger"
            pred_urea = 0.0
            pred_npk = 0.0
            status_desc = f"PERINGATAN PyTorch ANN: Akumulasi gas metana tinggi ({req.gas_metana} ppm) mengindikasikan tanah sangat tereduksi. Aplikasi pupuk saat ini berisiko meracuni perakaran padi (busuk akar) dan meningkatkan laju emisi gas rumah kaca."
            saran = "HENTIKAN sementara pemupukan! Segera lakukan pembuangan genangan air / drainase lahan intensif selama 3-5 hari agar tanah teraerasi dan retak rambut. Lakukan sampling ulang dengan Smart Chamber sebelum pemupukan dijadwalkan kembali."

        dosis_utama = pred_urea if pred_urea > 0 else (pred_npk if pred_npk > 0 else 0.0)

        return PredictResponse(
            status=status,
            status_text=status_text,
            status_class=status_class,
            confidence=confidence,
            confidence_class=confidence_class,
            status_desc=status_desc,
            action_status=action_status,
            action_class=action_class,
            dosis_urea_kg_ha=pred_urea,
            dosis_npk_kg_ha=pred_npk,
            dosis_rekomendasi_utama=dosis_utama,
            urea_text=f"Urea: {pred_urea} kg/Ha",
            npk_text=f"NPK: {pred_npk} kg/Ha",
            saran_tindakan=saran,
            input_received={
                "gas_metana": req.gas_metana,
                "suhu": req.suhu,
                "kelembaban": req.kelembaban,
                "tekanan": req.tekanan,
                "hst_hari": req.hst_hari,
                "chamber_id": req.chamber_id
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan inferensi model: {str(e)}")

@app.post("/api/retrain")
def retrain_model_endpoint(background_tasks: BackgroundTasks, new_records: Optional[List[RetrainRecord]] = None):
    """Menambahkan data observasi baru dan melatih ulang model ANN"""
    try:
        if new_records and len(new_records) > 0:
            rows = []
            for r in new_records:
                rows.append({
                    'gas_metana': r.gas_metana,
                    'suhu': r.suhu,
                    'kelembaban': r.kelembaban,
                    'tekanan': r.tekanan,
                    'hst_hari': r.hst_hari,
                    'dosis_urea': r.dosis_urea,
                    'dosis_npk': r.dosis_npk,
                    'status_lahan': r.status_lahan
                })
            new_df = pd.DataFrame(rows)
            if os.path.exists(DATASET_PATH):
                existing_df = pd.read_csv(DATASET_PATH)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_csv(DATASET_PATH, index=False)
            else:
                new_df.to_csv(DATASET_PATH, index=False)
            print(f"[INFO] {len(new_records)} data evaluasi baru ditambahkan ke dataset!")

        # Jalankan pelatihan ulang
        acc, mae_u, mae_n = train_model(epochs=150)
        load_ai_model()

        return {
            "status": "berhasil",
            "message": "Model ANN berhasil dilatih ulang (retrained) dengan dataset terbaru.",
            "akurasi_baru": f"{acc:.1f}%",
            "mae_urea": f"+- {mae_u:.2f} kg/Ha",
            "mae_npk": f"+- {mae_n:.2f} kg/Ha"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal melatih ulang model: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("[INFO] Menjalankan Server API AI Smart Chamber di http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
