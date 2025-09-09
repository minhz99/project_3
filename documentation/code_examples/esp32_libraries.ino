// Core Libraries and Configuration
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <FlowSensor.h>
// Global objects and timing configuration
WiFiClientSecure espClient;
PubSubClient client(espClient);
WiFiManager wm;
// Timing configuration
const unsigned long
  SEND_INTERVAL = 30000,
  WIFI_RECONNECT_INTERVAL = 5000,
  MQTT_RECONNECT_INTERVAL = 5000;
unsigned long
  lastSendTime = 0,
  lastWiFiCheck = 0,
  lastMQTTAttempt = 0;
// Sensor data structure
struct SensorData { float
  flow_rate,
  water_temp_inlet,
  water_temp_outlet,
  air_temp_inlet,
  air_humidity_inlet; };