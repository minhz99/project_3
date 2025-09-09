"""InfluxDB Handler"""
import os
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
from datetime import datetime
from typing import Dict, List
# InfluxDB Handler
class InfluxDBHandler:
    def __init__(self, config: Dict[str, str]):
        self.url = config.get('url', 'http://localhost:8086')
        self.token = config.get('token')
        self.org = config.get('org', 'your-organization')
        self.bucket = config.get('bucket', 'cooling_tower_data')
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
    # Write data to InfluxDB
    def write_data(self, data: Dict, measurement: str = "cooling_tower") -> bool:
        try:
            point = Point(measurement).tag("device_id", data.get('device_id', 'unknown'))
            for field in ['water_flow_lpm', 'water_temp_in', 'water_temp_out', 'air_temp_in', 'air_humidity_in']:
                if field in data: point.field(field, float(data[field]))
            point.time(data.get('timestamp', datetime.utcnow()), WritePrecision.S)
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True
        except Exception as e:
            logging.error(f"Write error: {e}")
            return False
    # Query data from InfluxDB
    def query_data(self, device_id: str, limit: int = 10) -> List[Dict]:
        try:
            query = f'from(bucket: "{self.bucket}") |> range(start: -1h) |> filter(fn: (r) => r["device_id"] == "{device_id}") |> limit(n: {limit})'
            result = self.query_api.query(org=self.org, query=query)
            return [{'time': r.get_time(), 'field': r.get_field(), 'value': r.get_value()} for table in result for r in table.records]
        except: return []
    # Check connection to InfluxDB
    def check_connection(self) -> bool:
        try: return self.client.health().status == "pass"
        except: return False
    # Close connection to InfluxDB
    def close(self): self.client.close()
# Configuration
INFLUXDB_CONFIG = {"url": "http://localhost:8086", "token": os.getenv("INFLUXDB_TOKEN"), "org": "your-organization", "bucket": "cooling_tower_data"}
def create_handler() -> InfluxDBHandler: return InfluxDBHandler(INFLUXDB_CONFIG)