"""
COOLING TOWER DATA PROCESSING MODULE
===================================

Mô-đun xử lý dữ liệu tháp giải nhiệt và tính toán các thông số kỹ thuật cốt lõi.

INPUT JSON FORMAT (Dữ liệu từ ESP32):
Topic: sensors/cooling_tower
QoS: 0
{
  "device_id": "ESP32_TOWER_01",
  "timestamp": 31729,
  "flow_rate": 5.555555,
  "water_temp_inlet": 28,
  "water_temp_outlet": 26.6875,
  "air_temp_inlet": 28.6,
  "air_humidity_inlet": 49.5,
}

OUTPUT JSON FORMAT (Kết quả xử lý cho Frontend):
{
  "device_id": "ESP32_TOWER_01",
  "timestamp": "2024-01-15T10:30:00Z",
  "processed_at": "2024-01-15T10:30:05.123Z",
  "water_flow_lpm": 5.56,
  "water_temp_in": 28.0,
  "water_temp_out": 26.69,
  "air_temp_in": 28.6,
  "air_humidity_in": 49.5,
  "wet_bulb_temp_in": 22.8,
  "cooling_efficiency": 78.5,
  "cooling_capacity": 262.1
}

ERROR OUTPUT FORMAT (Khi có lỗi):
{
  "error": "data_validation_error",
  "message": "Missing required fields or invalid data",
  "timestamp": "2024-01-15T10:30:05.123Z"
}

NOTES:
- Giá trị -999 từ ESP32 được coi là invalid data
- data_valid flag phải là true để xử lý
- ESP32 chỉ gửi air inlet data (không có air outlet)
- Khi có lỗi tính toán, giá trị sẽ được set None và lỗi ghi vào calculation_errors
- Hệ thống chịu lỗi: một cảm biến lỗi không làm toàn bộ hệ thống dừng
- Dữ liệu luôn được lưu vào database ngay cả khi có lỗi tính toán
"""

from datetime import datetime
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from theoretical_calculations import (
    wet_bulb_stull, 
    calculate_cooling_tower_efficiency,
    calculate_cooling_capacity
)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def assess_data_quality(water_temp_in, water_temp_out, water_flow_lpm, air_humidity_in):
    """
    Đánh giá chất lượng dữ liệu dựa trên các tiêu chí kỹ thuật
    
    Returns:
        str: "excellent", "good", "fair", "poor"
    """
    quality_score = 0
    
    # Kiểm tra chênh lệch nhiệt độ
    delta_T = abs(water_temp_in - water_temp_out)
    if delta_T > 1.0:
        quality_score += 3  # Chênh lệch nhiệt độ tốt
    elif delta_T > 0.5:
        quality_score += 2  # Chênh lệch nhiệt độ trung bình
    elif delta_T > 0.1:
        quality_score += 1  # Chênh lệch nhiệt độ nhỏ
    
    # Kiểm tra lưu lượng
    if water_flow_lpm > 1.0:
        quality_score += 2  # Lưu lượng hợp lý
    elif water_flow_lpm > 0.1:
        quality_score += 1  # Lưu lượng thấp
    
    # Kiểm tra độ ẩm
    if 20 <= air_humidity_in <= 80:
        quality_score += 2  # Độ ẩm trong khoảng hợp lý
    elif 10 <= air_humidity_in <= 90:
        quality_score += 1  # Độ ẩm trong khoảng chấp nhận được
    
    # Đánh giá chất lượng
    if quality_score >= 6:
        return "excellent"
    elif quality_score >= 4:
        return "good"
    elif quality_score >= 2:
        return "fair"
    else:
        return "poor"

def process_data(data):
    """
    Xử lý dữ liệu cảm biến tháp giải nhiệt từ ESP32
    
    Args:
        data (dict): Dữ liệu JSON từ ESP32 hoặc đã được convert sang backend format
    
    Returns:
        dict: Dữ liệu đã xử lý với các thông số tính toán cốt lõi
        None: Nếu có lỗi xảy ra
    """
    try:
        
        # Lấy dữ liệu từ ESP32 format
        device_id = data.get("device_id")
        timestamp = data.get("timestamp")
        water_flow_lpm = data.get("flow_rate")
        water_temp_in = data.get("water_temp_inlet")
        water_temp_out = data.get("water_temp_outlet")
        air_temp_in = data.get("air_temp_inlet")
        air_humidity_in = data.get("air_humidity_inlet")

        # Kiểm tra dữ liệu đầu vào bắt buộc
        required_fields = [
            ("device_id", device_id),
            ("water_flow_lpm", water_flow_lpm),
            ("water_temp_in", water_temp_in),
            ("water_temp_out", water_temp_out),
            ("air_temp_in", air_temp_in),
            ("air_humidity_in", air_humidity_in)
        ]
        
        missing_fields = []
        invalid_fields = []
        
        for field_name, field_value in required_fields:
            if field_value is None:
                missing_fields.append(field_name)
            elif field_name != "device_id":  # Skip device_id for numeric checks
                # Kiểm tra giá trị -999 (invalid data từ ESP32)
                try:
                    numeric_value = float(field_value)
                    if numeric_value == -999:
                        invalid_fields.append(field_name)
                except (ValueError, TypeError):
                    invalid_fields.append(field_name)
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        if invalid_fields:
            raise ValueError(f"Invalid sensor data (value = -999): {', '.join(invalid_fields)}")

        # Chuyển đổi sang float để đảm bảo tính toán chính xác
        # Đã kiểm tra None và -999 ở trên, an toàn để convert
        water_flow_lpm = float(water_flow_lpm or 0)
        water_temp_in = float(water_temp_in or 0)
        water_temp_out = float(water_temp_out or 0)
        air_temp_in = float(air_temp_in or 0)
        air_humidity_in = float(air_humidity_in or 0)

        # Kiểm tra range hợp lý
        if water_flow_lpm < 0:
            raise ValueError(f"Invalid water flow rate: {water_flow_lpm}")
        
        if air_humidity_in < 0 or air_humidity_in > 100:
            raise ValueError(f"Invalid humidity: {air_humidity_in}%")

        # Đánh giá chất lượng dữ liệu
        data_quality = assess_data_quality(water_temp_in, water_temp_out, water_flow_lpm, air_humidity_in)

        # logger.info("Input data validated, starting core calculations...")

        # Danh sách lưu lỗi tính toán (không dừng toàn bộ process)
        calculation_errors = []

        # 1. Tính nhiệt độ bầu ướt không khí vào
        try:
            wb_temp_in = wet_bulb_stull(air_temp_in, air_humidity_in)
            logger.debug(f"Wet bulb temperature: {wb_temp_in:.2f}°C")
        except Exception as e:
            wb_temp_in = None
            error_msg = f"wet_bulb_calculation_error: {str(e)}"
            calculation_errors.append(error_msg)
            logger.warning(f"Wet bulb calculation failed: {e}")

        # 2. Tính hiệu suất tháp giải nhiệt
        try:
            # Chỉ tính nếu wet bulb temperature có sẵn
            if wb_temp_in is not None:
                cooling_efficiency = calculate_cooling_tower_efficiency(water_temp_in, water_temp_out, wb_temp_in)
                logger.debug(f"Cooling efficiency: {cooling_efficiency:.2f}%")
            else:
                raise ValueError("Cannot calculate efficiency: wet bulb temperature unavailable")
        except Exception as e:
            cooling_efficiency = None
            error_msg = f"cooling_efficiency_calculation_error: {str(e)}"
            calculation_errors.append(error_msg)
            logger.warning(f"Cooling efficiency calculation failed: {e}")

        # 3. Tính công suất giải nhiệt
        try:
            cooling_capacity = calculate_cooling_capacity(water_flow_lpm, water_temp_in, water_temp_out)
            logger.debug(f"Cooling capacity: {cooling_capacity:.2f} kW")
        except Exception as e:
            cooling_capacity = None
            error_msg = f"cooling_capacity_calculation_error: {str(e)}"
            calculation_errors.append(error_msg)
            logger.warning(f"Cooling capacity calculation failed: {e}")

        # Tạo dictionary chứa kết quả
        processed_data = {
            "device_id": device_id,
            "timestamp": timestamp,
            "processed_at": datetime.now().isoformat(),
            "water_flow_lpm": round(water_flow_lpm, 2),
            "water_temp_in": round(water_temp_in, 2),
            "water_temp_out": round(water_temp_out, 2),
            "air_temp_in": round(air_temp_in, 2),
            "air_humidity_in": round(air_humidity_in, 1),
            "wet_bulb_temp_in": round(wb_temp_in, 2) if wb_temp_in is not None else None,
            "cooling_efficiency": round(cooling_efficiency, 2) if cooling_efficiency is not None else None,
            "cooling_capacity": round(cooling_capacity, 2) if cooling_capacity is not None else None,
            "calculation_errors": calculation_errors,
            "data_quality": data_quality,
            "processing_status": "success" if not calculation_errors else "partial_success"
        }

        # Log kết quả xử lý
        if calculation_errors:
            logger.info(f"Data processed with {len(calculation_errors)} calculation errors for device {device_id}. Data quality: {data_quality}")
        else:
            logger.debug(f"Data processing completed successfully for device {device_id}. Data quality: {data_quality}")
        
        return processed_data

    except ValueError as ve:
        logger.error(f"Data validation error: {ve}")
        return {
            "error": "data_validation_error",
            "message": str(ve),
            "timestamp": datetime.now().isoformat(),
            "processing_status": "failed"
        }
    except Exception as e:
        logger.error(f"Unexpected processing error: {e}")
        return {
            "error": "processing_error", 
            "message": f"Data processing error: {e}",
            "timestamp": datetime.now().isoformat(),
            "processing_status": "failed"
        }
