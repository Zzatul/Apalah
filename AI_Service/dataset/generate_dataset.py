"""
Script Generator Dataset Agronomi: IoT Smart Chamber & Emisi Gas Metana Padi
Menghasilkan dataset realistis berdasarkan kaidah agronomi padi sawah (Inpari 32)
dan korelasi laju emisi gas metana (CH4) terhadap penyerapan pupuk Urea & NPK.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd

def generate_dataset(num_samples=1500, random_seed=42):
    np.random.seed(random_seed)
    
    # 1. Generate Fitur Masukan (Sensors & Crop Lifecycle)
    metana_base = np.random.gamma(shape=3.5, scale=110, size=num_samples)
    gas_metana = np.clip(metana_base + 50, 60.0, 1450.0)

    # Suhu Tanah/Air: 22.0 s.d 36.0 °C (Rata-rata 28.5 °C)
    suhu = np.random.normal(loc=28.5, scale=2.8, size=num_samples)
    suhu = np.clip(suhu, 21.0, 36.5)

    # Kelembaban Relatif (%RH): 50 s.d 98 % (Rata-rata 76 %)
    kelembaban = np.random.normal(loc=76.0, scale=8.5, size=num_samples)
    kelembaban = np.clip(kelembaban, 50.0, 98.0)

    # Tekanan Udara (hPa): 1000 s.d 1022 hPa (Rata-rata 1013.25 hPa)
    tekanan = np.random.normal(loc=1013.25, scale=3.5, size=num_samples)
    tekanan = np.clip(tekanan, 1000.0, 1024.0)

    # Hari Setelah Tanam (HST): 5 s.d 105 Hari
    hst_hari = np.random.uniform(low=5.0, high=105.0, size=num_samples)

    # 2. Hitung Label Target (Kaidah Agronomi Pemupukan Padi)
    dosis_urea = []
    dosis_npk = []
    status_lahan = [] # 0: Aman (Aerobik), 1: Waspada (Anaerobik parsial), 2: Kritis (Toksik)

    for i in range(num_samples):
        ch4 = gas_metana[i]
        t = suhu[i]
        h = kelembaban[i]
        hst = hst_hari[i]

        # Base dosage berdasarkan fase pertumbuhan padi
        if hst <= 20: # Fase Vegetatif Awal
            base_urea = 40.0
            base_npk = 100.0
        elif hst <= 45: # Fase Vegetatif Aktif (Puncak Anakan)
            base_urea = 70.0
            base_npk = 75.0
        elif hst <= 65: # Fase Primordia / Bunting
            base_urea = 35.0
            base_npk = 40.0
        else: # Fase Pematangan / Pengisian Bulir (Tidak perlu tambahan Urea)
            base_urea = 0.0
            base_npk = 0.0

        # Faktor penyesuaian emisi metana & kondisi aerobik tanah
        if ch4 < 450.0 and t < 33.5:
            # Kondisi Aman: Serapan maksimal, aerasi tanah optimal
            factor = np.random.uniform(0.92, 1.05)
            u = base_urea * factor
            n = base_npk * factor
            st = 0 # Aman
        elif ch4 < 900.0 or (ch4 < 950.0 and t > 33.5):
            # Kondisi Waspada: Terjadi reduksi tanah, efisiensi serapan turun 50%
            factor = np.random.uniform(0.40, 0.60)
            u = base_urea * factor
            n = base_npk * factor
            st = 1 # Waspada
        else:
            # Kondisi Kritis: Potensial reduksi ekstrem, metan berlebih, bahaya busuk akar
            u = 0.0
            n = 0.0
            st = 2 # Kritis

        # Noise realistis pada hasil takaran
        if u > 0:
            u += np.random.normal(0, 1.5)
        if n > 0:
            n += np.random.normal(0, 2.0)

        dosis_urea.append(max(0.0, round(float(u), 1)))
        dosis_npk.append(max(0.0, round(float(n), 1)))
        status_lahan.append(int(st))

    df = pd.DataFrame({
        'gas_metana': np.round(gas_metana, 1),
        'suhu': np.round(suhu, 1),
        'kelembaban': np.round(kelembaban, 1),
        'tekanan': np.round(tekanan, 2),
        'hst_hari': np.round(hst_hari, 0).astype(int),
        'dosis_urea': dosis_urea,
        'dosis_npk': dosis_npk,
        'status_lahan': status_lahan
    })

    return df

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, "dataset_pupuk_padi.csv")
    
    print("[INFO] Membuat dataset simulasi sampling agronomi...")
    df = generate_dataset(num_samples=2000)
    df.to_csv(output_path, index=False)
    
    print(f"[OK] Berhasil membuat dataset: {output_path}")
    print(f"[INFO] Jumlah Data: {len(df)} baris")
    print(df.head(10))
    print("\nDistribusi Status Lahan:")
    print(df['status_lahan'].value_counts())
