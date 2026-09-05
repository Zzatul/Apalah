"""
Definisi Arsitektur Model ANN (Multi-Task Learning Deep Neural Network)
Model ini menerima 5 fitur input sensor & tanaman, lalu memprediksi:
1. Regresi Dosis Pupuk [Urea, NPK] (kg/Ha)
2. Klasifikasi Kondisi Lahan [Aman (0), Waspada (1), Kritis (2)] + Confidence Score
"""

import torch
import torch.nn as nn

class FertilizerMultiTaskANN(nn.Module):
    def __init__(self, input_dim=5):
        super(FertilizerMultiTaskANN, self).__init__()
        
        # Shared Hidden Feature Extractor
        self.shared_layers = nn.Sequential(
            nn.Linear(input_dim, 24),
            nn.BatchNorm1d(24),
            nn.ReLU(),
            nn.Linear(24, 16),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # Task 1: Regression Head (Estimasi Dosis Urea & NPK)
        self.regression_head = nn.Sequential(
            nn.Linear(16, 12),
            nn.ReLU(),
            nn.Linear(12, 2) # [Dosis Urea, Dosis NPK]
        )
        
        # Task 2: Classification Head (Prediksi Status Lahan 3 Kelas)
        self.classification_head = nn.Sequential(
            nn.Linear(16, 12),
            nn.ReLU(),
            nn.Linear(12, 3) # [Logits: 0=Aman, 1=Waspada, 2=Kritis]
        )

    def forward(self, x):
        shared_features = self.shared_layers(x)
        doses = self.regression_head(shared_features)
        status_logits = self.classification_head(shared_features)
        return doses, status_logits
