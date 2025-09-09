# 🏭 HỆ THỐNG GIÁM SÁT THÁP GIẢI NHIỆT THÔNG MINH (IoT)

## 📋 Giới thiệu

Đây là dự án xây dựng hệ thống giám sát thông minh cho tháp giải nhiệt sử dụng công nghệ IoT. Hệ thống được thiết kế để giám sát và tối ưu hóa hoạt động của tháp giải nhiệt trong các nhà máy điện, trung tâm dữ liệu và cơ sở công nghiệp - nơi chi phí làm mát có thể chiếm tới 30-50% chi phí vận hành.

### 🎯 Mục tiêu chính:
- **Giám sát thời gian thực** các thông số vận hành của tháp giải nhiệt
- **Tính toán tự động** hiệu suất và công suất giải nhiệt
- **Tối ưu chi phí** với giải pháp mã nguồn mở
- **Dễ triển khai** cho doanh nghiệp vừa và nhỏ

## 🏗️ Kiến trúc hệ thống

```
┌─────────────┐     MQTT/TLS     ┌─────────────┐     ┌──────────┐     ┌─────────┐
│   ESP32     │ ──────────────>  │   Python    │ ──> │InfluxDB  │ ──> │ Grafana │
│  Sensors    │                  │   Backend   │     │          │     │         │
└─────────────┘                  └─────────────┘     └──────────┘     └─────────┘
       │                                │
       │                                │
       ▼                                ▼
┌─────────────┐                  ┌─────────────┐
│  ESP8266    │ <──── MQTT ────  │ Calculations│
│  SSR Control│                  │  & Logic    │
└─────────────┘                  └─────────────┘
```

## 📦 Thành phần hệ thống

### 1. **ESP32 - Thu thập dữ liệu** (`/esp32_cooling_tower/`)
- **Cảm biến sử dụng:**
  - YF-S201: Đo lưu lượng nước (L/phút)
  - DS18B20 x2: Đo nhiệt độ nước vào/ra (°C)
  - DHT22: Đo nhiệt độ và độ ẩm không khí (°C, %)
- **Kết nối:** WiFi + MQTT với TLS
- **Chu kỳ gửi dữ liệu:** 5 giây

### 2. **Backend Python** (`/backend/`)
- **Chức năng chính:**
  - Nhận dữ liệu từ ESP32 qua MQTT
  - Xử lý và tính toán các thông số kỹ thuật
  - Lưu trữ dữ liệu vào InfluxDB
  - Đánh giá chất lượng dữ liệu
- **Tính toán:**
  - Nhiệt độ bầu ướt (Stull 2011)
  - Hiệu suất tháp giải nhiệt (%)
  - Công suất giải nhiệt (kW)

### 3. **ESP8266 - Điều khiển SSR** (`/esp32_cooling_tower/ssr_control/`)
- Điều khiển công suất với Solid State Relay
- Burst control 1Hz với duty cycle điều chỉnh được
- Interlock an toàn dựa trên lưu lượng nước
- Failsafe timeout 12 giây

### 4. **Cơ sở dữ liệu & Trực quan hóa**
- **InfluxDB:** Lưu trữ dữ liệu chuỗi thời gian
- **Grafana:** Dashboard trực quan hóa dữ liệu

### 5. **Tài liệu báo cáo** (`/documentation/`)
- Báo cáo LaTeX chi tiết về hệ thống
- Hình ảnh, sơ đồ kỹ thuật
- Code examples

## 🚀 Cài đặt và triển khai

### Yêu cầu hệ thống
- Python 3.8+
- InfluxDB 2.0+
- MQTT Broker (hỗ trợ TLS)
- ESP32 DevKit
- ESP8266 (optional cho điều khiển SSR)

### 1. Cài đặt Backend

```bash
# Clone repository
git clone <repository-url>
cd project_3/backend

# Cài đặt dependencies
pip install -r requirements.txt

# Cấu hình biến môi trường
cp config.env.example .env
# Chỉnh sửa file .env với thông tin MQTT và InfluxDB của bạn

# Chạy backend
python main.py
```

### 2. Cấu hình ESP32

1. Mở file `esp32_cooling_tower/esp32_cooling_tower/esp32_cooling_tower.ino` trong Arduino IDE
2. Cập nhật thông tin WiFi và MQTT broker:
```cpp
const char* mqtt_server = "YOUR_MQTT_BROKER_HOST";
const char* mqtt_user = "YOUR_MQTT_USERNAME";
const char* mqtt_pass = "YOUR_MQTT_PASSWORD";
```
3. Upload code lên ESP32

### 3. Cấu hình ESP8266 (Optional)

1. Mở file `esp32_cooling_tower/ssr_control/ssr_control.ino`
2. Cập nhật thông tin WiFi và MQTT
3. Upload code lên ESP8266

## 📊 Dữ liệu và tính toán

### Format dữ liệu từ ESP32
```json
{
  "device_id": "ESP32_TOWER_01",
  "timestamp": 31729,
  "flow_rate": 5.555555,
  "water_temp_inlet": 28,
  "water_temp_outlet": 26.6875,
  "air_temp_inlet": 28.6,
  "air_humidity_inlet": 49.5
}
```

### Kết quả xử lý từ Backend
```json
{
  "device_id": "ESP32_TOWER_01",
  "timestamp": "2024-01-15T10:30:00Z",
  "processed_at": "2024-01-15T10:30:05.123Z",
  "water_flow_lpm": 5.56,
  "water_temp_in": 28.0,
  "water_temp_out": 26.69,
  "air_temp_in": 28.6,
  "air_humidity_in": 49.5,
  "wet_bulb_temp_in": 22.8,
  "cooling_efficiency": 78.5,
  "cooling_capacity": 262.1,
  "data_quality": "excellent",
  "processing_status": "success"
}
```

### Công thức tính toán

1. **Nhiệt độ bầu ướt (Stull 2011):**
   - Sử dụng công thức Stull cho độ chính xác cao
   - Input: Nhiệt độ khô và độ ẩm tương đối

2. **Hiệu suất tháp giải nhiệt:**
   ```
   η = (T_water_in - T_water_out) / (T_water_in - T_wet_bulb) × 100%
   ```

3. **Công suất giải nhiệt:**
   ```
   Q = ṁ × Cp × ΔT
   ```
   Trong đó:
   - ṁ: Lưu lượng khối lượng (kg/s)
   - Cp: Nhiệt dung riêng của nước (4.186 kJ/kg·K)
   - ΔT: Chênh lệch nhiệt độ (K)

## 🔒 Bảo mật

- Kết nối MQTT sử dụng TLS encryption
- Authentication với username/password
- Failsafe mechanisms cho điều khiển SSR
- Data validation ở nhiều tầng

## 📈 Monitoring & Alerts

- Dashboard Grafana realtime
- Đánh giá chất lượng dữ liệu (excellent/good/fair/poor)
- Xử lý lỗi tính toán mà không làm dừng hệ thống
- Log chi tiết các hoạt động và lỗi

## 🛠️ Troubleshooting

### ESP32 không kết nối WiFi
- Kiểm tra SSID và password
- ESP32 sẽ tự động tạo AP `ESP32-CoolingTower-XXXX` với mật khẩu `12345678`

### Không nhận được dữ liệu MQTT
- Kiểm tra kết nối MQTT broker
- Verify TLS certificates (hoặc dùng `setInsecure()` để test)
- Kiểm tra topic subscription

### Lỗi tính toán
- Hệ thống sẽ tiếp tục hoạt động với partial data
- Kiểm tra log để xem chi tiết lỗi
- Đảm bảo cảm biến hoạt động bình thường (không trả về -999)

## 👥 Đóng góp

Dự án được phát triển bởi tui trong khuôn khổ ĐATN cử nhân. Mọi đóng góp và phản hồi đều được hoan nghênh.

## 📄 License

Dự án sử dụng giấy phép MIT. Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

```
MIT License - Copyright (c) 2024 HUST Cooling Tower IoT Monitoring System
```

---

**Lưu ý:** Đây là dự án nghiên cứu học thuật. Khi triển khai trong môi trường sản xuất, cần thêm các biện pháp bảo mật và kiểm thử kỹ lưỡng.
