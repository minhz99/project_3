// Sensor Configuration
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <FlowSensor.h>
// Configuration
const char* mqtt_server = getenv("MQTT_SERVER");
const char* mqtt_user = getenv("MQTT_USER");
const char* mqtt_pass = getenv("MQTT_PASS");
const char* mqtt_topic = getenv("MQTT_TOPIC");
const char* device_id = getenv("DEVICE_ID");
// Pin definitions
#define YF_S201_PIN 19
#define DS18B20_INLET_PIN 4
#define DS18B20_OUTLET_PIN 5
#define DHT22_INLET_PIN 17
// Sensor objects
DHT dht_inlet(DHT22_INLET_PIN, DHT22);
OneWire oneWire_inlet(DS18B20_INLET_PIN), oneWire_outlet(DS18B20_OUTLET_PIN);
DallasTemperature ds18b20_inlet(&oneWire_inlet), ds18b20_outlet(&oneWire_outlet);
FlowSensor flowSensor(YFS201, YF_S201_PIN);
WiFiClientSecure espClient;
PubSubClient client(espClient);
WiFiManager wm;
// Variables
const unsigned long SEND_INTERVAL = 5000;
unsigned long lastSendTime = 0;
struct SensorData { float flow_rate, water_temp_inlet, water_temp_outlet, air_temp_inlet, air_humidity_inlet; };
// Functions
void IRAM_ATTR flowSensorISR() { flowSensor.count(); }
bool connectWiFi() { return wm.autoConnect("ESP32-CoolingTower", "12345678"); }
bool connectMQTT() { return client.connect(device_id, mqtt_user, mqtt_pass); }
SensorData readSensors() { SensorData data; data.flow_rate = flowSensor.getFlowRate_m(); return data; }