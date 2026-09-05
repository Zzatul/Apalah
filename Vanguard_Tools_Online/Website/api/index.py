"""
Vercel Serverless Function: Python AI Fertilizer & CH4 Emission Inference
Endpoint live untuk dashboard web di https://vanguard-labs-team-tools.vercel.app/api/predict
Ultra-lightweight, latency <10ms, berjalan 24/7 di Vercel Serverless Cloud.
"""

import os
import json
import math
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="IoT Smart Chamber AI - Vercel Serverless Function",
    description="Live PyTorch Neural Network API on Vercel Cloud",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_FILE = os.path.join(BASE_DIR, "ann_weights.json")

# Cache model weights
_MODEL_CACHE = None

def get_model_data():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        if os.path.exists(WEIGHTS_FILE):
            with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
                _MODEL_CACHE = json.load(f)
        else:
            raise RuntimeError(f"Weights file not found: {WEIGHTS_FILE}")
    return _MODEL_CACHE

def relu(x):
    return [max(0.0, float(v)) for v in x]

def softmax(x):
    max_x = max(x)
    exp_x = [math.exp(v - max_x) for v in x]
    sum_exp = sum(exp_x)
    return [v / sum_exp for v in exp_x]

def linear_forward(x, weight, bias):
    # weight: list of list [out_features, in_features]
    # bias: list [out_features]
    out = []
    for row, b in zip(weight, bias):
        val = b
        for i, w in enumerate(row):
            val += x[i] * w
        out.append(val)
    return out

def batch_norm_forward(x, weight, bias, running_mean, running_var, eps=1e-5):
    out = []
    for i, v in enumerate(x):
        norm = (v - running_mean[i]) / math.sqrt(running_var[i] + eps)
        out.append(norm * weight[i] + bias[i])
    return out

def run_ann_inference(metana, suhu, kelembaban, tekanan, hst):
    model_data = get_model_data()
    scaler = model_data["scaler"]
    w = model_data["weights"]

    # 1. Normalisasi Input (MinMaxScaler)
    raw_x = [metana, suhu, kelembaban, tekanan, hst]
    x_norm = []
    for i in range(5):
        # x_scaled = x * scale + min_val
        val = raw_x[i] * scaler["scale"][i] + scaler["min_val"][i]
        x_norm.append(min(1.0, max(0.0, val)))

    # 2. Shared Layers
    # Linear 1 (5 -> 24)
    h1 = linear_forward(x_norm, w["shared_layers.0.weight"], w["shared_layers.0.bias"])
    # BatchNorm 1
    h1_bn = batch_norm_forward(
        h1,
        w["shared_layers.1.weight"],
        w["shared_layers.1.bias"],
        w["shared_layers.1.running_mean"],
        w["shared_layers.1.running_var"]
    )
    # ReLU 1
    a1 = relu(h1_bn)

    # Linear 2 (24 -> 16)
    h2 = linear_forward(a1, w["shared_layers.3.weight"], w["shared_layers.3.bias"])
    # BatchNorm 2
    h2_bn = batch_norm_forward(
        h2,
        w["shared_layers.4.weight"],
        w["shared_layers.4.bias"],
        w["shared_layers.4.running_mean"],
        w["shared_layers.4.running_var"]
    )
    # ReLU 2
    a2 = relu(h2_bn)

    # 3. Regression Head (16 -> 12 -> 2)
    r1 = relu(linear_forward(a2, w["regression_head.0.weight"], w["regression_head.0.bias"]))
    doses = linear_forward(r1, w["regression_head.2.weight"], w["regression_head.2.bias"])

    # 4. Classification Head (16 -> 12 -> 3)
    c1 = relu(linear_forward(a2, w["classification_head.0.weight"], w["classification_head.0.bias"]))
    logits = linear_forward(c1, w["classification_head.2.weight"], w["classification_head.2.bias"])
    probs = softmax(logits)

    status_idx = probs.index(max(probs))
    confidence = round(probs[status_idx] * 100, 1)

    pred_urea = max(0.0, round(float(doses[0]), 1))
    pred_npk = max(0.0, round(float(doses[1]), 1))

    return {
        "status_idx": status_idx,
        "confidence": confidence,
        "urea": pred_urea,
        "npk": pred_npk,
        "probs": probs
    }

# --- Pydantic Request & Response Schemas ---

class SensorPredictRequest(BaseModel):
    gas_metana: float = Field(..., example=327.5)
    suhu: float = Field(..., example=28.5)
    kelembaban: float = Field(..., example=75.0)
    tekanan: float = Field(..., example=1013.25)
    hst_hari: Optional[float] = Field(30.0, example=30.0)
    chamber_id: Optional[str] = Field("Chamber 1", example="Chamber 1")
    crop_name: Optional[str] = Field("Padi Sawah", example="Padi Sawah")
    crop_variety: Optional[str] = Field("Inpari 32", example="Inpari 32")

@app.get("/api/health")
@app.get("/health")
@app.get("/api")
@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "IoT Smart Chamber AI - Vercel Serverless",
        "framework": "PyTorch Exported ANN (Ultra-Fast Engine)",
        "cloud": "Vercel Live"
    }

@app.get("/api/model-info")
@app.get("/model-info")
def model_info():
    return {
        "model_type": "Multi-Task Deep Neural Network (ANN)",
        "deployment": "Vercel Serverless Function",
        "input_features": ["gas_metana", "suhu", "kelembaban", "tekanan", "hst_hari"],
        "outputs": ["dosis_urea_kg_ha", "dosis_npk_kg_ha", "status_lahan", "confidence"]
    }

@app.post("/api/predict")
@app.post("/predict")
def predict_fertilizer(req: SensorPredictRequest):
    try:
        res = run_ann_inference(
            metana=req.gas_metana,
            suhu=req.suhu,
            kelembaban=req.kelembaban,
            tekanan=req.tekanan,
            hst=req.hst_hari
        )

        status_idx = res["status_idx"]
        confidence = res["confidence"]
        pred_urea = res["urea"]
        pred_npk = res["npk"]

        if status_idx == 0: # AMAN
            status = "Aman"
            status_text = "Aman (Kondisi Aerobik Optimal)"
            status_class = "badge-aman"
            action_status = "Waktu Optimal Pemupukan"
            action_class = "action-optimal"
            confidence_class = "bg-success"
            status_desc = f"Model PyTorch ANN (Vercel Live) memproyeksikan efisiensi serapan tanah sangat optimal pada {req.chamber_id} ({req.crop_name} - {req.crop_variety}). Emisi metana rendah ({req.gas_metana} ppm), akar siap menyerap pupuk tanpa memicu emisi berlebih."
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
            status_desc = f"Inferensi ANN mendeteksi kenaikan gas metana ({req.gas_metana} ppm). Rekomendasi dosis dikurangi 50% untuk mencegah pelepasan gas CH₄ dan efisiensi nutrisi."
            saran = "Kurangi dosis pemupukan menjadi 50%. Lakukan pengeringan lahan sementara (intermittent aeration) 2-3 hari untuk mengalirkan oksigen ke perakaran."
        else: # KRITIS
            status = "Kritis"
            status_text = "Kritis / Toksik Anaerobik (Akumulasi Gas Metan Tinggi)"
            status_class = "badge-kritis"
            action_status = "Tunda Pemupukan"
            action_class = "action-delay"
            confidence_class = "bg-danger"
            pred_urea = 0.0
            pred_npk = 0.0
            status_desc = f"PERINGATAN ANN: Akumulasi gas metana tinggi ({req.gas_metana} ppm). Tanah sangat tereduksi. Hentikan pemupukan untuk mencegah busuk akar dan keracunan gas."
            saran = "HENTIKAN sementara pemupukan! Segera lakukan pembuangan genangan air / drainase intensif selama 3-5 hari sebelum melakukan sampling ulang."

        dosis_utama = pred_urea if pred_urea > 0 else (pred_npk if pred_npk > 0 else 0.0)

        return {
            "engine": "PyTorch Deep ANN (Vercel Live Cloud)",
            "status": status,
            "status_text": status_text,
            "status_class": status_class,
            "confidence": confidence,
            "confidence_class": confidence_class,
            "status_desc": status_desc,
            "action_status": action_status,
            "action_class": action_class,
            "dosis_urea_kg_ha": pred_urea,
            "dosis_npk_kg_ha": pred_npk,
            "dosis_rekomendasi_utama": dosis_utama,
            "urea_text": f"Urea: {pred_urea} kg/Ha",
            "npk_text": f"NPK: {pred_npk} kg/Ha",
            "saran_tindakan": saran,
            "input_received": {
                "gas_metana": req.gas_metana,
                "suhu": req.suhu,
                "kelembaban": req.kelembaban,
                "tekanan": req.tekanan,
                "hst_hari": req.hst_hari,
                "chamber_id": req.chamber_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

# Handler untuk Vercel Serverless
handler = app
