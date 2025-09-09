// Pin Configuration and Sensor Setup
#define YF_S201_PIN         19
#define DS18B20_INLET_PIN   4
#define DS18B20_OUTLET_PIN  5
#define DHT22_INLET_PIN     17
#define SSR_CONTROL_PIN     16
// Initialize sensor objects
DHT dht_inlet(DHT22_INLET_PIN, DHT22);
OneWire oneWire_inlet(DS18B20_INLET_PIN);
OneWire oneWire_outlet(DS18B20_OUTLET_PIN);
DallasTemperature ds18b20_inlet(&oneWire_inlet);
DallasTemperature ds18b20_outlet(&oneWire_outlet);
uint16_t type = YFS201; // Flow sensor type
FlowSensor flowSensor(type, YF_S201_PIN);
// Flow sensor interrupt handler
void IRAM_ATTR flowSensorISR() { flowSensor.count(); }
// SSR control functions
void setupSSR() {
  pinMode(SSR_CONTROL_PIN, OUTPUT);
  digitalWrite(SSR_CONTROL_PIN, LOW); }
// Control SSR based on flow rate
void controlSSR(float flowRate) {
  analogWrite(SSR_CONTROL_PIN, (flowRate > 0.1) ? 64 : 0); }
// Initialize all sensors and components
void initAllSensors() {
  dht_inlet.begin();
  ds18b20_inlet.begin();
  ds18b20_outlet.begin();
  flowSensor.begin(flowSensorISR);
  setupSSR();
  Serial.println("All sensors initialized successfully");
}