// simulator.js
// Script untuk mensimulasikan ESP32 mengirim data sensor ke server Node.js

const API_URL = 'http://localhost:3000/api/data';
const DEVICES = ['Chamber 1', 'Chamber 2']; // Mendukung simulasi beberapa Chamber sekaligus!

console.log('=== SIMULATOR ESP32 SMART CHAMBER ===');
console.log(`Mengirim data simulasi untuk ${DEVICES.join(', ')} ke ${API_URL} setiap 3 detik...\n`);

function generateRandom(min, max) {
    return parseFloat((Math.random() * (max - min) + min).toFixed(2));
}

async function sendMockData(device) {
    // Generate data sensor acak yang realistis
    const payload = {
        device: device,
        suhu: generateRandom(24.0, 31.0),          // Suhu: 24 - 31 C
        kelembaban: generateRandom(65.0, 85.0),    // Kelembaban: 65 - 85%
        tekanan: generateRandom(1009.0, 1012.0),   // Tekanan: 1009 - 1012 hPa
        gas_metana: Math.floor(generateRandom(15, 80)), // Gas Metana: 15 - 80 ppm
        syringe_present: Math.random() > 0.3 ? 1 : 0    // Status Syringe
    };

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        console.log(`[${new Date().toLocaleTimeString()}] ${device} Terkirim: Suhu=${payload.suhu}°C, Gas=${payload.gas_metana}ppm | Respon Server:`, JSON.stringify(result));
    } catch (error) {
        console.error(`[❌ Error] ${device} Gagal mengirim data simulasi: ${error.message}`);
    }
}

// Kirim data untuk seluruh device setiap 3 detik
setInterval(() => {
    DEVICES.forEach(device => {
        sendMockData(device);
    });
}, 3000);

// Kirim data langsung saat pertama kali dijalankan
DEVICES.forEach(device => {
    sendMockData(device);
});
