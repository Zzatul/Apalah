from http.server import BaseHTTPRequestHandler
import json
import os
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_FILE = os.path.join(BASE_DIR, "ann_weights.json")

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

    raw_x = [metana, suhu, kelembaban, tekanan, hst]
    x_norm = []
    for i in range(5):
        val = raw_x[i] * scaler["scale"][i] + scaler["min_val"][i]
        x_norm.append(min(1.0, max(0.0, val)))

    # Shared Layers
    h1 = linear_forward(x_norm, w["shared_layers.0.weight"], w["shared_layers.0.bias"])
    h1_bn = batch_norm_forward(
        h1,
        w["shared_layers.1.weight"],
        w["shared_layers.1.bias"],
        w["shared_layers.1.running_mean"],
        w["shared_layers.1.running_var"]
    )
    a1 = relu(h1_bn)

    h2 = linear_forward(a1, w["shared_layers.3.weight"], w["shared_layers.3.bias"])
    h2_bn = batch_norm_forward(
        h2,
        w["shared_layers.4.weight"],
        w["shared_layers.4.bias"],
        w["shared_layers.4.running_mean"],
        w["shared_layers.4.running_var"]
    )
    a2 = relu(h2_bn)

    # Regression Head
    r1 = relu(linear_forward(a2, w["regression_head.0.weight"], w["regression_head.0.bias"]))
    doses = linear_forward(r1, w["regression_head.2.weight"], w["regression_head.2.bias"])

    # Classification Head
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

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            req = json.loads(body.decode('utf-8'))
            metana = float(req.get('gas_metana', 327.0))
            suhu = float(req.get('suhu', 28.5))
            kelembaban = float(req.get('kelembaban', 75.0))
            tekanan = float(req.get('tekanan', 1013.25))
            hst = float(req.get('hst_hari', 30.0))
            chamber_id = req.get('chamber_id', 'Chamber 1')
            crop_name = req.get('crop_name', 'Padi Sawah')
            crop_variety = req.get('crop_variety', 'Inpari 32')

            res = run_ann_inference(metana, suhu, kelembaban, tekanan, hst)
            status_idx = res["status_idx"]
            confidence = res["confidence"]
            pred_urea = res["urea"]
            pred_npk = res["npk"]

            if status_idx == 0:
                status = "Aman"
                status_text = "Aman (Kondisi Aerobik Optimal)"
                status_class = "badge-aman"
                action_status = "Waktu Optimal Pemupukan"
                action_class = "action-optimal"
                confidence_class = "bg-success"
                status_desc = f"Model PyTorch ANN (Vercel Live) memproyeksikan efisiensi aerasi tanah sangat optimal pada {chamber_id} ({crop_name} - {crop_variety}). Emisi metana rendah ({metana} ppm), akar siap menyerap pupuk secara maksimal."
                saran = "Waktu pemupukan sangat tepat. Disarankan aplikasi pada pagi hari (06.30 - 09.00) atau sore hari. Pertahankan ketinggian air dangkal / macak-macak (1-2 cm) agar pupuk terserap sempurna ke rizosfer."
            elif status_idx == 1:
                status = "Waspada"
                status_text = "Waspada Anaerobik (Reduksi Tanah Meningkat)"
                status_class = "badge-waspada"
                action_status = "Kurangi Dosis 50%"
                action_class = "action-reduce"
                confidence_class = "bg-warning"
                pred_urea = round(pred_urea * 0.5, 1)
                pred_npk = round(pred_npk * 0.5, 1)
                status_desc = f"Inferensi ANN mendeteksi kenaikan dekomposisi anaerobik ({metana} ppm). Rekomendasi dosis dikurangi 50% untuk mencegah pelepasan gas CH₄."
                saran = "Kurangi dosis pemupukan menjadi 50%. Lakukan pengeringan lahan sementara (intermittent aeration) 2-3 hari untuk mengalirkan oksigen ke perakaran."
            else:
                status = "Kritis"
                status_text = "Kritis / Toksik Anaerobik (Akumulasi Gas Metan Tinggi)"
                status_class = "badge-kritis"
                action_status = "Tunda Pemupukan"
                action_class = "action-delay"
                confidence_class = "bg-danger"
                pred_urea = 0.0
                pred_npk = 0.0
                status_desc = f"PERINGATAN ANN: Akumulasi gas metana tinggi ({metana} ppm). Tanah sangat tereduksi. Hentikan pemupukan untuk mencegah busuk akar dan pemborosan hara."
                saran = "HENTIKAN sementara pemupukan! Segera lakukan pembuangan genangan air / drainase intensif selama 3-5 hari sebelum melakukan sampling ulang."

            dosis_utama = pred_urea if pred_urea > 0 else (pred_npk if pred_npk > 0 else 0.0)

            response_data = {
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
                    "gas_metana": metana,
                    "suhu": suhu,
                    "kelembaban": kelembaban,
                    "tekanan": tekanan,
                    "hst_hari": hst,
                    "chamber_id": chamber_id
                }
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            err_data = {"error": str(e)}
            self.wfile.write(json.dumps(err_data).encode('utf-8'))
