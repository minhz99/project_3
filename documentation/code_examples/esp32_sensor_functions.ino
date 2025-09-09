// Sensor Functions
float readFlowRate() { flowSensor.read(); return flowSensor.getFlowRate_m(); }
float readDS18B20(DallasTemperature &sensor) {
  sensor.requestTemperatures();
  float temp = sensor.getTempCByIndex(0);
  return (temp == DEVICE_DISCONNECTED_C) ? -999.0 : temp; }
// Read DHT sensor
void readDHT(DHT &sensor, float &temp, float &humidity) {
  temp = sensor.readTemperature();
  humidity = sensor.readHumidity();
  if (isnan(temp) || isnan(humidity)) { temp = -999.0; humidity = -999.0; } }
// Read all sensors
SensorData readAllSensors() {
  SensorData data;
  data.flow_rate = readFlowRate();
  data.water_temp_inlet = readDS18B20(ds18b20_inlet);
  data.water_temp_outlet = readDS18B20(ds18b20_outlet);
  readDHT(dht_inlet, data.air_temp_inlet, data.air_humidity_inlet);
  return data; }
// Check if sensor data is valid
bool isValidSensorData(const SensorData &data) {
  return !(data.flow_rate < 0 || data.water_temp_inlet == -999.0 || data.water_temp_outlet == -999.0 ||
          data.air_temp_inlet == -999.0 || data.air_humidity_inlet == -999.0 ||
          data.water_temp_inlet < 0 || data.water_temp_inlet > 100 ||
          data.water_temp_outlet < 0 || data.water_temp_outlet > 100 ||
          data.air_temp_inlet < -40 || data.air_temp_inlet > 80 ||
          data.air_humidity_inlet < 0 || data.air_humidity_inlet > 100); }
// Print sensor data
void printSensorData(const SensorData &data) {
  Serial.println("=== SENSOR DATA ===");
  Serial.printf("Flow: %.1f L/min | Water In: %.1f°C | Water Out: %.1f°C\n", 
                data.flow_rate, data.water_temp_inlet, data.water_temp_outlet);
  Serial.printf("Air: %.1f°C | Humidity: %.1f%%\n", data.air_temp_inlet, data.air_humidity_inlet);
  Serial.println("=================="); }