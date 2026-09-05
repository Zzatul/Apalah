"""
Skrip Pelatihan Model ANN: Rekomendasi Dosis Pupuk & Prediksi Status Lahan
Membaca dataset, melakukan normalisasi, melatih Multi-Task ANN, dan menyimpan model.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import joblib

from model import FertilizerMultiTaskANN

def train_model(dataset_path=None, model_dir=None, epochs=250, batch_size=32, lr=0.005):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if dataset_path is None:
        dataset_path = os.path.join(base_dir, "dataset", "dataset_pupuk_padi.csv")
    if model_dir is None:
        model_dir = os.path.join(base_dir, "models")
    
    os.makedirs(model_dir, exist_ok=True)
    
    if not os.path.exists(dataset_path):
        print("[INFO] Dataset belum ditemukan. Menjalankan generator dataset...")
        from dataset.generate_dataset import generate_dataset
        df = generate_dataset(num_samples=2000)
        os.makedirs(os.path.dirname(dataset_path), exist_ok=True)
        df.to_csv(dataset_path, index=False)
    else:
        df = pd.read_csv(dataset_path)

    print(f"[INFO] Dataset dimuat: {len(df)} baris data.")

    # 1. Pisahkan Fitur (X) dan Target (y)
    feature_cols = ['gas_metana', 'suhu', 'kelembaban', 'tekanan', 'hst_hari']
    X = df[feature_cols].values
    y_doses = df[['dosis_urea', 'dosis_npk']].values
    y_status = df['status_lahan'].values

    # 2. Normalisasi Fitur (Min-Max Scaling)
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # Simpan scaler
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    joblib.dump(scaler, scaler_path)
    print(f"[OK] Scaler disimpan ke: {scaler_path}")

    # 3. Train-Test Split (80% Train, 20% Val)
    X_train, X_val, yd_train, yd_val, ys_train, ys_val = train_test_split(
        X_scaled, y_doses, y_status, test_size=0.20, random_state=42, stratify=y_status
    )

    # Konversi ke PyTorch Tensor
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    yd_train_t = torch.tensor(yd_train, dtype=torch.float32)
    ys_train_t = torch.tensor(ys_train, dtype=torch.long)

    X_val_t = torch.tensor(X_val, dtype=torch.float32)
    yd_val_t = torch.tensor(yd_val, dtype=torch.float32)
    ys_val_t = torch.tensor(ys_val, dtype=torch.long)

    train_dataset = torch.utils.data.TensorDataset(X_train_t, yd_train_t, ys_train_t)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    # 4. Inisialisasi Model, Loss & Optimizer
    model = FertilizerMultiTaskANN(input_dim=len(feature_cols))
    criterion_regression = nn.SmoothL1Loss() # Robust Huber loss untuk dosis pupuk
    criterion_classification = nn.CrossEntropyLoss() # Multi-class classification loss
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=20)

    # 5. Training Loop
    print(f"\n[AI] Memulai Pelatihan Model ANN ({epochs} Epochs)...")
    best_val_loss = float('inf')
    model_save_path = os.path.join(model_dir, "model_ann.pth")

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0

        for batch_x, batch_yd, batch_ys in train_loader:
            optimizer.zero_grad()
            pred_doses, pred_status = model(batch_x)

            loss_reg = criterion_regression(pred_doses, batch_yd)
            loss_cls = criterion_classification(pred_status, batch_ys)
            loss = loss_reg + (1.5 * loss_cls)

            loss.backward()
            optimizer.step()
            total_train_loss += loss.item() * batch_x.size(0)

        train_loss = total_train_loss / len(train_loader.dataset)

        # Evaluasi Validasi
        model.eval()
        with torch.no_grad():
            v_doses, v_status = model(X_val_t)
            v_loss_reg = criterion_regression(v_doses, yd_val_t).item()
            v_loss_cls = criterion_classification(v_status, ys_val_t).item()
            val_loss = v_loss_reg + (1.5 * v_loss_cls)

            # Hitung Akurasi & Mean Absolute Error (MAE)
            pred_classes = torch.argmax(v_status, dim=1)
            accuracy = (pred_classes == ys_val_t).float().mean().item() * 100
            mae_urea = torch.mean(torch.abs(v_doses[:, 0] - yd_val_t[:, 0])).item()
            mae_npk = torch.mean(torch.abs(v_doses[:, 1] - yd_val_t[:, 1])).item()

        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), model_save_path)

        if epoch % 25 == 0 or epoch == epochs:
            print(f"Epoch [{epoch:3d}/{epochs}] | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Akurasi: {accuracy:.1f}% | MAE Urea: {mae_urea:.2f} kg/Ha | MAE NPK: {mae_npk:.2f} kg/Ha")

    print(f"\n[OK] Model berhasil dilatih dan disimpan ke: {model_save_path}")
    print(f"[RESULT] Akurasi Akhir Klasifikasi Lahan: {accuracy:.1f}%")
    print(f"[RESULT] Rata-rata Error Dosis Urea: +- {mae_urea:.2f} kg/Ha | NPK: +- {mae_npk:.2f} kg/Ha")
    
    return accuracy, mae_urea, mae_npk

if __name__ == "__main__":
    train_model()
