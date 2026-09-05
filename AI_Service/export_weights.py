"""
Script Export Bobot Model PyTorch ke JSON/NumPy
Memungkinkan model ANN berjalan di Vercel Serverless Function secara instan (ultra-lightweight, <1ms inference)
tanpa batasan ukuran memori library besar.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import torch
import joblib
import json
import numpy as np

from model import FertilizerMultiTaskANN

def export_weights(model_path="models/model_ann.pth", scaler_path="models/scaler.pkl", output_dir="../api"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    m_path = os.path.join(base_dir, model_path)
    s_path = os.path.join(base_dir, scaler_path)
    out_dir = os.path.join(base_dir, output_dir)
    
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Muat Scaler
    scaler = joblib.load(s_path)
    scaler_info = {
        "min": scaler.data_min_.tolist(),
        "max": scaler.data_max_.tolist(),
        "scale": scaler.scale_.tolist(),
        "min_val": scaler.min_.tolist()
    }
    
    # 2. Muat Model PyTorch
    model = FertilizerMultiTaskANN(input_dim=5)
    model.load_state_dict(torch.load(m_path, map_location='cpu'))
    model.eval()
    
    state_dict = model.state_dict()
    weights_dict = {}
    
    for k, v in state_dict.items():
        weights_dict[k] = v.cpu().numpy().tolist()
        
    export_payload = {
        "framework": "PyTorch Exported Multi-Task Deep ANN",
        "scaler": scaler_info,
        "weights": weights_dict
    }
    
    out_file = os.path.join(out_dir, "ann_weights.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)
        
    print(f"[OK] Bobot model berhasil diekspor ke: {out_file} ({os.path.getsize(out_file)} bytes)")
    return out_file

if __name__ == "__main__":
    export_weights()
