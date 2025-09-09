// WiFi Configuration
bool connectWiFiNonBlocking() {
  static bool wifiManagerStarted = false;
  if (WiFi.status() == WL_CONNECTED) return true;
  // Start WiFi manager if not started
  if (!wifiManagerStarted) {
    wm.setConfigPortalTimeout(120);
    wm.setConnectTimeout(30);
    wm.setAPStaticIPConfig(IPAddress(192,168,4,1),
                           IPAddress(192,168,4,1),
                           IPAddress(255,255,255,0));
    // Set WiFi manager started to true
    String apName = "ESP32-CoolingTower-" + 
                    String((uint32_t)(ESP.getEfuseMac() >> 32), HEX);
    wifiManagerStarted = true;
    return wm.autoConnect(apName.c_str(), "12345678"); }
  // Return false if WiFi manager is already started
  return false; }
// WiFi connection monitoring and auto-reconnect
void checkWiFiConnection() {
  unsigned long now = millis();
  if (now - lastWiFiCheck >= WIFI_RECONNECT_INTERVAL) {
    lastWiFiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      connectWiFiNonBlocking(); } } }