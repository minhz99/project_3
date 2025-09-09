//Main Loop
void setup() {
  Serial.begin(115200); // Initialize serial communication
  Serial.println("ESP32 Starting...");
  initAllSensors(); // Initialize all sensors
  connectWiFiNonBlocking(); // Connect to WiFi
  client.setServer(mqtt_server, mqtt_port); // Set MQTT server
}
void loop() {
  client.loop(); // Loop MQTT client
  unsigned long now = millis();
  checkWiFiConnection();
  if (!client.connected()) connectMQTTNonBlocking(); // Connect to MQTT server
  if (now - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = now;
    SensorData data = readAllSensors();
    controlSSR(data.flow_rate);
    if (client.connected() && isValidSensorData(data)) {
      String jsonPayload = createJson(data);
      Serial.println(client.publish(mqtt_topic, jsonPayload.c_str()) ? "Data sent OK" : "MQTT failed");
    }
  } delay(10); // Delay 10ms
}
// Connection monitoring
void handleDisconnections() {
  static bool lastWiFi = false, lastMQTT = false;
  bool currentWiFi = (WiFi.status() == WL_CONNECTED);
  bool currentMQTT = client.connected();
  // Check WiFi connection
  if (currentWiFi != lastWiFi) {
    Serial.println(currentWiFi ? "WiFi OK" : "WiFi Lost");
    lastWiFi = currentWiFi; }
  // Check MQTT connection
  if (currentMQTT != lastMQTT) {
    Serial.println(currentMQTT ? "MQTT OK" : "MQTT Lost");
    lastMQTT = currentMQTT; } }