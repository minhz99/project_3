// ===== ESP8266-12E -> SSR (1 Hz burst) with TLS MQTT interlock =====
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// WIFI CONFIGURATION
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// MQTT BROKER CONFIGURATION  
const char* mqtt_server = "YOUR_MQTT_BROKER_HOST";
const int   mqtt_port   = 8883;  // 8883 cho TLS, 1883 cho không mã hóa
const char* mqtt_user   = "YOUR_MQTT_USERNAME";
const char* mqtt_pass   = "YOUR_MQTT_PASSWORD";
const char* mqtt_topic  = "sensors/cooling_tower";
const char* device_id   = "ESP32_TOWER_01";  // ID thiết bị duy nhất

// ==================== CONTROL PARAMS ====================
#ifndef SSR_PIN
#define SSR_PIN             D7      // GPIO13 (đầu vào điều khiển SSR)
#endif

#ifndef LED_PIN  
#define LED_PIN             BUILTIN_LED  // LED on-board ESP8266 (GPIO2)
#endif

// Các tham số có thể cấu hình
#ifndef WINDOW_MS
const uint32_t WINDOW_MS   = 1000;  // 1 Hz "burst" cửa sổ 1 giây
#endif

#ifndef DEFAULT_DUTY_PERCENT
volatile int duty_percent  = 30;    // duty mặc định 30%
#else
volatile int duty_percent  = DEFAULT_DUTY_PERCENT;
#endif

#ifndef FLOW_THRESHOLD_LPM
float flow_threshold_lpm   = 0.20f; // ngưỡng "có lưu lượng" 
#else
float flow_threshold_lpm   = FLOW_THRESHOLD_LPM;
#endif

#ifndef FLOW_MSG_TIMEOUT_MS
uint32_t flow_msg_timeout_ms = 12000; // >12s không nhận gói -> OFF
#else
uint32_t flow_msg_timeout_ms = FLOW_MSG_TIMEOUT_MS;
#endif

// Các biến runtime
uint32_t last_window_start = 0;
uint32_t last_flow_msg_ms  = 0;
uint32_t led_blink_ms      = 0;     // thời gian LED nháy

bool heater_enable = true;
bool interlock_ok  = false;
bool ssr_on        = false;
float last_flow_lpm= 0.0f;

// ==================== GLOBALS ====================
BearSSL::WiFiClientSecure tls;
PubSubClient mqtt(tls);

// ==================== HELPERS ====================
void setSSR(bool on) {
  ssr_on = on;
  digitalWrite(SSR_PIN, on ? HIGH : LOW); // HIGH thường là kích SSR
}

void applyFailsafeCheck() {
  uint32_t now = millis();
  bool timeout = (now - last_flow_msg_ms) > flow_msg_timeout_ms;
  interlock_ok = (!timeout) && (last_flow_lpm >= flow_threshold_lpm);
  if (!interlock_ok) setSSR(false);
}

void handleBurst1Hz() {
  if (!heater_enable) { setSSR(false); return; }
  applyFailsafeCheck();
  if (!interlock_ok) return;

  uint32_t now = millis();
  if (now - last_window_start >= WINDOW_MS) {
    last_window_start = now;
  }
  uint32_t on_ms = (uint32_t)((WINDOW_MS * (uint32_t)duty_percent) / 100UL);
  uint32_t t_in  = now - last_window_start;
  bool should_on = (duty_percent > 0) && (t_in < on_ms);
  setSSR(should_on);
}

void parseFlowJson(const char* payload, size_t len) {
  StaticJsonDocument<768> doc;
  auto err = deserializeJson(doc, payload, len);
  if (err) return;

  // Lọc theo device_id nếu có trường này trong JSON của ESP32
  if (doc.containsKey("device_id")) {
    const char* dev = doc["device_id"];
    if (!dev || strcmp(dev, device_id) != 0) return; // bỏ qua gói không khớp
  }

  // Ưu tiên flow_rate từ ESP32; fallback các trường khác
  if (doc.containsKey("flow_rate")) {
    last_flow_lpm = doc["flow_rate"].as<float>();
  } else if (doc.containsKey("water_flow_lpm")) {
    last_flow_lpm = doc["water_flow_lpm"].as<float>();
  } else if (doc.containsKey("flow_lpm")) {
    last_flow_lpm = doc["flow_lpm"].as<float>();
  } else if (doc.containsKey("flow_hz")) {
    float hz = doc["flow_hz"].as<float>();
    last_flow_lpm = hz / 7.5f;          // YF-S201  ≈ 7.5 Hz / LPM (xấp xỉ)
  } else if (doc.containsKey("pulses_per_sec")) {
    float pps = doc["pulses_per_sec"].as<float>();
    last_flow_lpm = (pps * 60.0f) / 450.0f; // ~450 pulses/L (hãy hiệu chuẩn lại)
  } else {
    return;
  }
  last_flow_msg_ms = millis();
  
  // Kích hoạt LED nháy khi có tín hiệu MQTT mới
  led_blink_ms = millis();
  digitalWrite(LED_PIN, HIGH); // Bật LED ngay lập tức
  
  // Debug: in thông tin nhận được
  Serial.printf("Received: flow=%.3f LPM, temp_in=%.1f°C, temp_out=%.1f°C, air_temp=%.1f°C, humidity=%.1f%%\n",
    last_flow_lpm,
    doc.containsKey("water_temp_inlet") ? doc["water_temp_inlet"].as<float>() : -999.0f,
    doc.containsKey("water_temp_outlet") ? doc["water_temp_outlet"].as<float>() : -999.0f,
    doc.containsKey("air_temp_inlet") ? doc["air_temp_inlet"].as<float>() : -999.0f,
    doc.containsKey("air_humidity_inlet") ? doc["air_humidity_inlet"].as<float>() : -999.0f
  );
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, mqtt_topic) == 0) parseFlowJson((const char*)payload, length);
}

void ensureMqtt() {
  if (mqtt.connected()) return;
  while (!mqtt.connected()) {
    String cid = String("heater8266-") + String(ESP.getChipId(), HEX);
    // Last Will (tùy chọn)
    // const char* willTopic = "actuators/heater/status";
    // const char* willMsg   = "{\"state\":\"offline\"}";
    // bool ok = mqtt.connect(cid.c_str(), mqtt_user, mqtt_pass, willTopic, 0, true, willMsg);
    bool ok = mqtt.connect(cid.c_str(), mqtt_user, mqtt_pass);
    if (ok) {
      mqtt.subscribe(mqtt_topic, 0);
      Serial.println("MQTT connected and subscribed to topic");
      // mqtt.publish("actuators/heater/status", "{\"state\":\"online\"}", true);
    } else {
      Serial.println("MQTT connection failed, retrying...");
      delay(2000);
    }
  }
}

// ==================== SETUP/LOOP ====================
void setup() {
  pinMode(SSR_PIN, OUTPUT);
  setSSR(false);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // LED OFF khi khởi động

  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) { Serial.print("."); delay(300); }
  Serial.printf("\nWiFi OK: %s\n", WiFi.localIP().toString().c_str());

  // ---- TLS config ----
  // Bỏ qua xác thực certificate để test nhanh
  tls.setInsecure();

  // Điều chỉnh bộ đệm TLS cho ESP8266 (giảm lỗi handshake trên broker TLS)
  tls.setBufferSizes(4096, 512);

  mqtt.setServer(mqtt_server, mqtt_port);
  mqtt.setCallback(onMqttMessage);

  last_window_start = millis();
  last_flow_msg_ms  = 0; // failsafe OFF cho đến khi có gói đầu tiên
  led_blink_ms      = 0; // LED OFF khi khởi động

  Serial.printf("Heater TLS MQTT ready: 1Hz burst, duty=%d%%, interlock by flow from ESP32.\n", duty_percent);
  Serial.println("Serial: ON|OFF|DUTY <0..100> | THR <LPM> | STATUS");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) ensureMqtt();
  mqtt.loop();
  handleBurst1Hz();

  // ---- Serial điều khiển nhanh ----
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { line += c; continue; }

    line.trim();
    if (line.equalsIgnoreCase("ON")) {
      heater_enable = true;  Serial.println(F("OK ON"));
    } else if (line.equalsIgnoreCase("OFF")) {
      heater_enable = false; setSSR(false); Serial.println(F("OK OFF"));
    } else if (line.startsWith("DUTY") || line.startsWith("duty")) {
      int v = line.substring(4).toInt();
      v = constrain(v, 0, 100); duty_percent = v;
      Serial.printf("OK DUTY=%d%%\n", duty_percent);
    } else if (line.startsWith("THR") || line.startsWith("thr")) {
      float th = line.substring(3).toFloat();
      if (th < 0) th = 0; flow_threshold_lpm = th;
      Serial.printf("OK THRESHOLD=%.2f LPM\n", flow_threshold_lpm);
    } else if (line.equalsIgnoreCase("STATUS")) {
      Serial.printf("STATUS duty=%d%%, enable=%d, interlock_ok=%d, flow=%.3f LPM, LED=%s\n",
        duty_percent, heater_enable, interlock_ok, last_flow_lpm, 
        digitalRead(LED_PIN) ? "ON" : "OFF");
    } else if (line.length()) {
      Serial.println(F("ERR use: ON|OFF|DUTY x|THR x|STATUS"));
    }
    line = "";
  }

  // ---- LED blink ----
  uint32_t now = millis();
  if (led_blink_ms > 0 && now - led_blink_ms > 500) { // nháy 500ms
    digitalWrite(LED_PIN, LOW); // Tắt LED sau 500ms
    led_blink_ms = 0; // reset thời gian nháy
  }
}