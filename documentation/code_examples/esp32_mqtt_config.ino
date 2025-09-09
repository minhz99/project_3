// MQTT Configuration
const char* mqtt_server = getenv("MQTT_SERVER");
const int mqtt_port = atoi(getenv("MQTT_PORT"));
const char* mqtt_user = getenv("MQTT_USER");
const char* mqtt_pass = getenv("MQTT_PASS");
const char* mqtt_topic = getenv("MQTT_TOPIC");
const char* device_id = getenv("DEVICE_ID");
// MQTT connection
bool connectMQTTNonBlocking() {
  if (client.connected()) return true;
  if (WiFi.status() != WL_CONNECTED) return false;
  unsigned long now = millis();
  if (now - lastMQTTAttempt < MQTT_RECONNECT_INTERVAL) return false;  
  lastMQTTAttempt = now;
  client.setServer(mqtt_server, mqtt_port);
  espClient.setInsecure();
  String clientId = String(device_id) + "_" + String(random(0xffff), HEX);
  if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
    Serial.println("MQTT connected");
    return true;
  } else {
    Serial.printf("MQTT failed, rc=%d\n", client.state());
    return false;
  }
}
// JSON creation
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