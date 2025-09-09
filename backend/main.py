#!/usr/bin/env python3
"""
COOLING TOWER MONITORING SYSTEM - MAIN APPLICATION
==================================================

Ứng dụng chính cho hệ thống giám sát tháp giải nhiệt.

Chức năng:
- Nhận dữ liệu ESP32 format qua MQTT
- Xử lý dữ liệu trực tiếp bằng process_data.py  
- Lưu trữ dữ liệu raw và processed vào InfluxDB
- Hiển thị thống kê hệ thống

Usage:
    python main.py
    python main.py --debug
"""

import asyncio
import json
import signal
import sys
import argparse
from datetime import datetime
from typing import Dict, Any
import paho.mqtt.client as mqtt

from config import (
    setup_logging, create_mqtt_client, connect_mqtt, publish_status,
    InfluxDBHandler, 
    log_system_stats,
    MQTT_TOPIC, SYSTEM_NAME
)
from process_data import process_data

# Global variables
logger = setup_logging()  # Initialize logger early
influx_handler = None
mqtt_client = None
running = False

# Statistics
stats = {
    "messages_received": 0,
    "messages_processed": 0,
    "messages_failed": 0,
    "start_time": datetime.now()
}

def on_connect(client, _userdata, flags, rc):
    """Callback khi kết nối MQTT thành công"""
    global logger
    if rc == 0:
        logger.info("✅ MQTT connected")
        client.subscribe(MQTT_TOPIC, qos=1)
        publish_status(client, "online")
    else:
        logger.error(f"❌ MQTT connection failed: {rc}")

def on_message(client, _userdata, msg):
    """Callback khi nhận được message MQTT"""
    global logger, influx_handler, stats
    
    try:
        stats["messages_received"] += 1
        
        # Parse JSON từ ESP32
        payload = json.loads(msg.payload.decode('utf-8'))
        
        # Log mỗi 10 messages
        if stats["messages_received"] % 60 == 0:
            logger.info(f"📨 Received {stats['messages_received']} messages")
        
        # Extract device ID cho logging
        device_id = payload.get("device_id", "unknown_device")
        
        # Xử lý dữ liệu
        processed_result = process_data(payload)
        
        # Kiểm tra kết quả xử lý
        if processed_result is None:
            stats["messages_failed"] += 1
            logger.error(f"❌ {device_id} processing failed: No result returned")
            return
        
        # Kiểm tra nếu có lỗi validation nghiêm trọng
        if isinstance(processed_result, dict) and "error" in processed_result:
            stats["messages_failed"] += 1
            error_msg = processed_result.get("message", "Processing failed")
            logger.error(f"❌ {device_id} processing failed: {error_msg}")
            return

        # Lưu processed data vào InfluxDB (luôn luôn lưu nếu có dữ liệu)
        if influx_handler and processed_result:
            try:
                influx_handler.write_data(processed_result)
                logger.debug(f"💾 Data saved to database for device {device_id}")
            except Exception as db_error:
                logger.error(f"❌ Database write error for device {device_id}: {db_error}")
                # Không tăng stats failed vì đây là lỗi database, không phải lỗi xử lý
        
        # Cập nhật thống kê
        stats["messages_processed"] += 1
        
        # Kiểm tra trạng thái xử lý để log phù hợp
        processing_status = processed_result.get('processing_status', 'unknown')
        calculation_errors = processed_result.get('calculation_errors', [])
        
        if processing_status == 'success':
            # Xử lý hoàn toàn thành công
            if stats["messages_processed"] % 60 == 0:
                efficiency = processed_result.get('cooling_efficiency', 0)
                water_temp_in = processed_result.get('water_temp_in', 'N/A')
                water_temp_out = processed_result.get('water_temp_out', 'N/A')
                data_quality = processed_result.get('data_quality', 'unknown')
                logger.info(f"✅ {device_id}: Eff={efficiency:.1f}%, Temp={water_temp_in}°C→{water_temp_out}°C, Quality={data_quality} ({stats['messages_processed']} processed)")
        elif processing_status == 'partial_success':
            # Xử lý một phần thành công (có lỗi tính toán)
            if calculation_errors:
                logger.info(f"⚠️ {device_id}: Partial success with {len(calculation_errors)} calculation errors. Data quality: {processed_result.get('data_quality', 'unknown')}")
                # Log chi tiết các lỗi tính toán
                for error in calculation_errors[:3]:  # Chỉ log 3 lỗi đầu tiên
                    logger.debug(f"   Calculation error: {error}")
                if len(calculation_errors) > 3:
                    logger.debug(f"   ... and {len(calculation_errors) - 3} more errors")
        else:
            # Trạng thái không xác định
            logger.warning(f"❓ {device_id}: Unknown processing status: {processing_status}")
        
    except json.JSONDecodeError as e:
        stats["messages_failed"] += 1
        logger.error(f"❌ JSON parse error: {e}")
    except Exception as e:
        stats["messages_failed"] += 1
        logger.error(f"❌ Message processing error: {e}")

async def main_loop():
    """Vòng lặp chính của hệ thống"""
    global logger, running
    
    loop_count = 0
    while running:
        await asyncio.sleep(1)
        loop_count += 1
        
        # Log statistics mỗi 5 phút (300 giây)
        if loop_count % 300 == 0 and stats["messages_received"] > 0:
            log_system_stats(stats)

def signal_handler(signum, frame):
    """Signal handler để dừng hệ thống gracefully"""
    global logger, running, mqtt_client, influx_handler
    
    logger.info("🛑 Stopping system...")
    running = False
    
    # Publish offline status
    if mqtt_client:
        try:
            publish_status(mqtt_client, "offline")
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"❌ MQTT stop error: {e}")
    
    # Close InfluxDB
    if influx_handler:
        influx_handler.close()
    
    # Log final stats
    log_system_stats(stats)
    logger.info("✅ System stopped")
    sys.exit(0)

async def main():
    """Hàm main"""
    global logger, influx_handler, mqtt_client, running
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Cooling Tower Monitoring System')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    logger = setup_logging(log_level)
    
    try:
        logger.info(f"🚀 Starting {SYSTEM_NAME}")
        
        # Initialize InfluxDB
        influx_handler = InfluxDBHandler()
        
        # Initialize MQTT
        mqtt_client = create_mqtt_client()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Connect MQTT
        if not connect_mqtt(mqtt_client, on_connect, on_message):
            logger.error("❌ Failed to connect MQTT")
            return 1
        
        # Wait for connection
        await asyncio.sleep(2)
        
        running = True
        logger.info("✅ System started successfully")
        
        # Main loop
        await main_loop()
        
    except KeyboardInterrupt:
        logger.info("📡 User interrupted")
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 