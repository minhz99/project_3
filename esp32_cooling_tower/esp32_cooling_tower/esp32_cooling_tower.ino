#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <FlowSensor.h>


// ==================== MQTT CONFIG ====================
#ifndef MQTT_SERVER_ENV
const char* mqtt_server = "YOUR_MQTT_BROKER_HOST";
#else
const char* mqtt_server = MQTT_SERVER_ENV;
#endif

#ifndef MQTT_PORT_ENV
const int mqtt_port = 8883;  // 8883 cho TLS, 1883 cho không mã hóa
#else
const int mqtt_port = MQTT_PORT_ENV;
#endif

#ifndef MQTT_USER_ENV
const char* mqtt_user = "YOUR_MQTT_USERNAME";
#else
const char* mqtt_user = MQTT_USER_ENV;
#endif

#ifndef MQTT_PASS_ENV
const char* mqtt_pass = "YOUR_MQTT_PASSWORD";
#else
const char* mqtt_pass = MQTT_PASS_ENV;
#endif

#ifndef MQTT_TOPIC_ENV
const char* mqtt_topic = "sensors/cooling_tower";
#else
const char* mqtt_topic = MQTT_TOPIC_ENV;
#endif

#ifndef DEVICE_ID_ENV
const char* device_id = "ESP32_TOWER_01";
#else
const char* device_id = DEVICE_ID_ENV;
#endif

// ==================== SENSOR PINS ====================
#ifndef YF_S201_PIN_CONFIG
#define YF_S201_PIN         13
#else
#define YF_S201_PIN         YF_S201_PIN_CONFIG
#endif

#ifndef DS18B20_INLET_PIN_CONFIG
#define DS18B20_INLET_PIN   4
#else
#define DS18B20_INLET_PIN   DS18B20_INLET_PIN_CONFIG
#endif

#ifndef DS18B20_OUTLET_PIN_CONFIG
#define DS18B20_OUTLET_PIN  5
#else
#define DS18B20_OUTLET_PIN  DS18B20_OUTLET_PIN_CONFIG
#endif

#ifndef DHT22_INLET_PIN_CONFIG
#define DHT22_INLET_PIN     17
#else
#define DHT22_INLET_PIN     DHT22_INLET_PIN_CONFIG
#endif
 
 // ==================== SENSOR OBJECTS ====================
 DHT dht_inlet(DHT22_INLET_PIN, DHT22);
 OneWire oneWire_inlet(DS18B20_INLET_PIN);
 OneWire oneWire_outlet(DS18B20_OUTLET_PIN);
 DallasTemperature ds18b20_inlet(&oneWire_inlet);
 DallasTemperature ds18b20_outlet(&oneWire_outlet);

#ifndef FLOW_SENSOR_TYPE
uint16_t type = YFS201; // YF-S201 có pulse/liter = 450
#else
uint16_t type = FLOW_SENSOR_TYPE;
#endif

FlowSensor flowSensor(type, YF_S201_PIN);
 
 WiFiClientSecure espClient;
 PubSubClient client(espClient);
 WiFiManager wm;
 
#ifndef SEND_INTERVAL_MS
const unsigned long SEND_INTERVAL = 5000;  // Chu kỳ gửi dữ liệu (ms)
#else
const unsigned long SEND_INTERVAL = SEND_INTERVAL_MS;
#endif

#ifndef WIFI_CHECK_INTERVAL_MS
const unsigned long WIFI_RECONNECT_INTERVAL = 5000;  // Chu kỳ kiểm tra WiFi (ms)
#else
const unsigned long WIFI_RECONNECT_INTERVAL = WIFI_CHECK_INTERVAL_MS;
#endif

#ifndef MQTT_RETRY_INTERVAL_MS
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;  // Chu kỳ thử kết nối lại MQTT (ms)
#else
const unsigned long MQTT_RECONNECT_INTERVAL = MQTT_RETRY_INTERVAL_MS;
#endif
 
 unsigned long lastSendTime = 0;
 unsigned long lastWiFiCheck = 0;
 unsigned long lastMQTTAttempt = 0;
 
 struct SensorData {
   float flow_rate;
   float water_temp_inlet;
   float water_temp_outlet;
   float air_temp_inlet;
   float air_humidity_inlet;
 };

 // Flow sensor interrupt function
 void IRAM_ATTR flowSensorISR() {
   flowSensor.count();
 }
 
 bool connectWiFiNonBlocking() {
   static bool wifiManagerStarted = false;
   
   if (WiFi.status() == WL_CONNECTED) {
     return true;
   }
   
     if (!wifiManagerStarted) {
    // Cấu hình WiFiManager - NON-BLOCKING
#ifndef WIFI_CONFIG_TIMEOUT
    wm.setConfigPortalTimeout(120); // 2 phút timeout
#else
    wm.setConfigPortalTimeout(WIFI_CONFIG_TIMEOUT);
#endif

#ifndef WIFI_CONNECT_TIMEOUT
    wm.setConnectTimeout(30);       // 30 giây connect timeout
#else
    wm.setConnectTimeout(WIFI_CONNECT_TIMEOUT);
#endif
    wm.setAPStaticIPConfig(IPAddress(192,168,4,1), IPAddress(192,168,4,1), IPAddress(255,255,255,0));
    
    String apName = "ESP32-CoolingTower-" + String((uint32_t)(ESP.getEfuseMac() >> 32), HEX);
    
    // NON-BLOCKING autoConnect
    wifiManagerStarted = true;
    return wm.autoConnect(apName.c_str(), "12345678");
  }
   
   return false;
 }
 
 bool connectMQTTNonBlocking() {
   if (client.connected()) {
     return true;
   }
   
   if (WiFi.status() != WL_CONNECTED) {
     return false;
   }
   
   unsigned long now = millis();
   if (now - lastMQTTAttempt < MQTT_RECONNECT_INTERVAL) {
     return false; // Chưa đến lúc thử lại
   }
   
   lastMQTTAttempt = now;
   
     client.setServer(mqtt_server, mqtt_port);
  espClient.setInsecure();
  
  String clientId = String(device_id) + "_" + String(random(0xffff), HEX);
  
  if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
    return true;
  } else {
    return false;
  }
 }
 
 float readFlowRate() {
   flowSensor.read();
   return flowSensor.getFlowRate_m(); // Lít/phút
 }
 
 float readDS18B20(DallasTemperature &sensor) {
   sensor.requestTemperatures();
   float temp = sensor.getTempCByIndex(0);
   return (temp == DEVICE_DISCONNECTED_C) ? -999.0 : temp;
 }
 
 void readDHT(DHT &sensor, float &temp, float &humidity) {
   temp = sensor.readTemperature();
   humidity = sensor.readHumidity();
   if (isnan(temp) || isnan(humidity)) {
     temp = -999.0;
     humidity = -999.0;
   }
 }
 
 SensorData readAllSensors() {
   SensorData data;
   data.flow_rate = readFlowRate();
   data.water_temp_inlet = readDS18B20(ds18b20_inlet);
   data.water_temp_outlet = readDS18B20(ds18b20_outlet);
   readDHT(dht_inlet, data.air_temp_inlet, data.air_humidity_inlet);
 
   return data;
 }
 
 String createJson(const SensorData &data) {
   DynamicJsonDocument doc(512);
   doc["device_id"] = device_id;
   doc["timestamp"] = millis();
   doc["flow_rate"] = data.flow_rate;
   doc["water_temp_inlet"] = data.water_temp_inlet;
   doc["water_temp_outlet"] = data.water_temp_outlet;
   doc["air_temp_inlet"] = data.air_temp_inlet;
   doc["air_humidity_inlet"] = data.air_humidity_inlet;

   String json;
   serializeJson(doc, json);
   return json;
 }
 
 void setup() {
  // Khởi tạo sensors
  dht_inlet.begin();
  ds18b20_inlet.begin();
  ds18b20_outlet.begin();
  
  // Khởi tạo FlowSensor với interrupt
  flowSensor.begin(flowSensorISR);
}
 
 void loop() {
   // ============ CRITICAL: client.loop() LUÔN Ở ĐẦU ============
   client.loop();
   
   unsigned long now = millis();
   
     // Non-blocking WiFi connection check (mỗi 5 giây)
  if (now - lastWiFiCheck >= WIFI_RECONNECT_INTERVAL) {
    lastWiFiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      connectWiFiNonBlocking();
    }
  }
   
   // Non-blocking MQTT connection attempt
   if (!client.connected()) {
     connectMQTTNonBlocking();
   }
 
   // Gửi dữ liệu định kỳ (chỉ khi có kết nối)
   if (now - lastSendTime >= SEND_INTERVAL && client.connected()) {
     lastSendTime = now;
     
         SensorData data = readAllSensors();
    String jsonPayload = createJson(data);
    
    client.publish(mqtt_topic, jsonPayload.c_str());
   }
   
   // Micro delay để tránh watchdog reset
   delay(10);
 } 