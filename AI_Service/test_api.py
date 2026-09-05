"""
Skrip Verifikasi & Unit Test Cepat untuk Model ANN & API Server
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

def test_local_model_inference():
    print("\n--- 1. Testing Inferensi Model PyTorch Langsung ---")
    try:
        from model import FertilizerMultiTaskANN
        import joblib
        import torch
        import numpy as np

        base_dir = os.path.dirname(os.path.abspath(__file__))
        scaler = joblib.load(os.path.join(base_dir, "models", "scaler.pkl"))
        model = FertilizerMultiTaskANN(input_dim=5)
        model.load_state_dict(torch.load(os.path.join(base_dir, "models", "model_ann.pth"), map_location='cpu'))
        model.eval()

        # Test Case 1: Normal Aerobik (320 ppm, 28.5 C, 75%, 1013.25 hPa, 30 HST)
        test_in = np.array([[320.0, 28.5, 75.0, 1013.25, 30.0]])
        test_in_scaled = scaler.transform(test_in)
        tensor_in = torch.tensor(test_in_scaled, dtype=torch.float32)

        with torch.no_grad():
            doses, logits = model(tensor_in)
            probs = torch.softmax(logits, dim=1).numpy()[0]
            status_idx = int(np.argmax(probs))
            doses_out = doses.numpy()[0]

        print("[OK] Test Case 1 (Normal): Metana 320 ppm, Suhu 28.5 C, HST 30")
        print(f"     Status Prediksi: {['Aman', 'Waspada', 'Kritis'][status_idx]} (Confidence: {probs[status_idx]*100:.1f}%)")
        print(f"     Dosis Urea: {doses_out[0]:.1f} kg/Ha | NPK: {doses_out[1]:.1f} kg/Ha")

        # Test Case 2: Kritis / Anaerobik Tinggi (1150 ppm, 33.0 C, 88%, 1010 hPa, 30 HST)
        test_in2 = np.array([[1150.0, 33.0, 88.0, 1010.0, 30.0]])
        test_in2_scaled = scaler.transform(test_in2)
        tensor_in2 = torch.tensor(test_in2_scaled, dtype=torch.float32)

        with torch.no_grad():
            doses2, logits2 = model(tensor_in2)
            probs2 = torch.softmax(logits2, dim=1).numpy()[0]
            status_idx2 = int(np.argmax(probs2))
            doses_out2 = doses2.numpy()[0]

        print("[OK] Test Case 2 (Kritis): Metana 1150 ppm, Suhu 33.0 C, HST 30")
        print(f"     Status Prediksi: {['Aman', 'Waspada', 'Kritis'][status_idx2]} (Confidence: {probs2[status_idx2]*100:.1f}%)")
        print(f"     Dosis Raw: Urea {doses_out2[0]:.1f} kg/Ha | NPK: {doses_out2[1]:.1f} kg/Ha")

        return True
    except Exception as e:
        print(f"[ERROR] Error Test Model: {str(e)}")
        return False

def test_api_endpoint():
    print("\n--- 2. Testing HTTP Endpoint FastAPI (http://127.0.0.1:8000) ---")
    try:
        res = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
        if res.status_code == 200:
            print("[OK] Server API Online:", res.json())
            
            predict_res = requests.post("http://127.0.0.1:8000/api/predict", json={
                "gas_metana": 327.0,
                "suhu": 28.5,
                "kelembaban": 75.0,
                "tekanan": 1013.25,
                "hst_hari": 30.0,
                "chamber_id": "Chamber 1",
                "crop_name": "Padi Sawah",
                "crop_variety": "Inpari 32"
            }, timeout=3)
            print("[OK] Response Predict API:", json.dumps(predict_res.json(), indent=2))
            return True
        else:
            print("[WARN] Server API merespon dengan status:", res.status_code)
            return False
    except Exception:
        print("[INFO] Server API belum aktif di background (Jalankan 'run_service.bat' untuk menyalakan API).")
        return False

if __name__ == "__main__":
    test_local_model_inference()
    test_api_endpoint()
