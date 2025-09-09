"""
COOLING TOWER MONITORING SYSTEM - CONFIGURATION & UTILITIES
===========================================================

Cấu hình tập trung và các hàm tiện ích cho hệ thống giám sát tháp giải nhiệt.
Kiến trúc: ESP32 -> MQTT -> Python Backend -> InfluxDB -> Grafana
"""

import os
import json
import ssl
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt

try:
    from influxdb_client.client.influxdb_client import InfluxDBClient
    from influxdb_client.client.write.point import Point
    from influxdb_client.domain.write_precision import WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    logging.warning("InfluxDB client not available. Install influxdb-client package.")

# ==================== CONFIGURATION ====================

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "true").lower() == "true"
MQTT_TOPIC = os.getenv("MQTT_TOPIC")
MQTT_STATUS_TOPIC = os.getenv("MQTT_STATUS_TOPIC")

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# System Configuration
SYSTEM_NAME = os.getenv("SYSTEM_NAME", "Cooling Tower Monitor")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ==================== LOGGING SETUP ====================

def setup_logging(level: str = LOG_LEVEL) -> logging.Logger:
    """
    Thiết lập logging cho hệ thống
    
    Args:
        level: Mức độ log (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('cooling_tower.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Logging setup complete - Level: {level}")
    return logger

# ==================== MQTT FUNCTIONS ====================

def create_mqtt_client() -> mqtt.Client:
    """
    Tạo và cấu hình MQTT client
    
    Returns:
        Configured MQTT client
    """
    client = mqtt.Client()
    
    # Authentication
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # TLS Setup
    if MQTT_USE_TLS:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    
    return client

def connect_mqtt(client: mqtt.Client, on_connect_callback=None, on_message_callback=None) -> bool:
    """
    Kết nối MQTT client và thiết lập callbacks
    
    Args:
        client: MQTT client instance
        on_connect_callback: Callback function for connection
        on_message_callback: Callback function for messages
    
    Returns:
        bool: True if connected successfully
    """
    try:
        if on_connect_callback:
            client.on_connect = on_connect_callback
        if on_message_callback:
            client.on_message = on_message_callback
        
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        return True
    except Exception as e:
        logging.error(f"❌ MQTT connection failed: {e}")
        return False

def publish_status(client: mqtt.Client, status: str, data: Optional[Dict[str, Any]] = None):
    """
    Publish system status to MQTT
    
    Args:
        client: MQTT client
        status: Status string (online/offline)
        data: Additional status data
    """
    try:
        status_msg = {
            "system": SYSTEM_NAME,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        if data is not None:
            status_msg.update(data)
        
        client.publish(MQTT_STATUS_TOPIC, json.dumps(status_msg), qos=1, retain=True)
    except Exception as e:
        logging.error(f"❌ Failed to publish status: {e}")

# ==================== INFLUXDB FUNCTIONS ====================

class InfluxDBHandler:
    """InfluxDB handler cho cooling tower data"""
    
    def __init__(self):
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        if INFLUXDB_AVAILABLE:
            self.connect()
    
    def connect(self) -> bool:
        """
        Kết nối tới InfluxDB
        
        Returns:
            bool: True if connected successfully
        """
        if not INFLUXDB_AVAILABLE:
            logging.error("❌ InfluxDB client not available")
            return False
        
        try:
            self.client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            
            # Test connection
            self._test_connection()
            logging.info(f"✅ Connected to InfluxDB at {INFLUXDB_URL}")
            return True
            
        except Exception as e:
            logging.error(f"❌ InfluxDB connection failed: {e}")
            return False
    
    def _test_connection(self):
        """Test InfluxDB connection"""
        try:
            if self.client:
                query_api = self.client.query_api()
                query = f'buckets() |> filter(fn: (r) => r.name == "{INFLUXDB_BUCKET}") |> limit(n: 1)'
                query_api.query(query)
        except Exception as e:
            logging.warning(f"InfluxDB connection test failed: {e}")
    
    def write_data(self, data: Dict[str, Any]) -> bool:
        """
        Ghi dữ liệu vào InfluxDB
        
        Args:
            data: Dictionary chứa các trường dữ liệu cần lưu
            
        Returns:
            bool: True if written successfully
        """
        if not self.write_api or not INFLUXDB_AVAILABLE:
            return False
        
        try:
            # Lấy device_id từ dữ liệu
            device_id = data.get("device_id", "unknown_device")
            
            # Lấy timestamp từ dữ liệu hoặc dùng thời gian hiện tại
            timestamp = data.get("timestamp")
            if timestamp:
                try:
                    # Nếu timestamp là string, convert sang datetime
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    # Đảm bảo timestamp ở múi giờ UTC
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except:
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            point = Point("cooling_tower") \
                .tag("device_id", device_id) \
                .time(timestamp, WritePrecision.S)
            
            # Thêm tất cả các trường dữ liệu hợp lệ
            for key, value in data.items():
                if isinstance(value, (int, float)) and key not in ["timestamp", "processed_at", "device_id"]:
                    point = point.field(key, float(value))

            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to write data: {e}")
            return False

    def close(self):
        """Đóng kết nối InfluxDB"""
        if self.client:
            try:
                self.client.close()
                logging.info("✅ InfluxDB connection closed")
            except Exception as e:
                logging.error(f"❌ Error closing InfluxDB: {e}")

# ==================== UTILITY FUNCTIONS ====================

def validate_sensor_data(data: Dict[str, Any]) -> bool:
    """
    Kiểm tra tính hợp lệ của dữ liệu sensor
    
    Args:
        data: Sensor data dictionary
        
    Returns:
        bool: True if data is valid
    """
    required_fields = [
        "water_flow_lpm", "water_temp_in", "water_temp_out",
        "air_temp_in", "air_humidity_in"
    ]
    
    for field in required_fields:
        if field not in data or data[field] is None:
            return False
        
        try:
            float(data[field])
        except (ValueError, TypeError):
            return False
    
    return True

def log_system_stats(stats: Dict[str, Any]):
    """
    Log system statistics
    
    Args:
        stats: Statistics dictionary
    """
    try:
        received = stats.get("messages_received", 0)
        processed = stats.get("messages_processed", 0)
        failed = stats.get("messages_failed", 0)
        
        success_rate = (processed / received * 100) if received > 0 else 0
        
        logging.info(f"📊 Stats: {processed}/{received} processed ({success_rate:.1f}%), {failed} failed")
    except Exception as e:
        logging.error(f"❌ Error logging stats: {e}")