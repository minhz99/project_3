"""
THEORETICAL CALCULATIONS FOR COOLING TOWER
==========================================

Các công thức tính toán khoa học cho tháp giải nhiệt, bao gồm:
- Tính toán nhiệt độ bầu ướt (Stull 2011)
- Tính toán hiệu suất tháp giải nhiệt
- Tính toán công suất giải nhiệt

Tham khảo:
- Stull, R. (2011). Wet-Bulb Temperature from Relative Humidity and Air Temperature
- ASHRAE Handbook - Fundamentals (2017)
"""

import math
import logging

logger = logging.getLogger(__name__)

# Hằng số tolerance cho nhiệt độ (độ C)
# Cho phép chênh lệch nhỏ giữa nhiệt độ vào và ra do sai số cảm biến
TEMPERATURE_TOLERANCE = 0.1  # 0.1°C

def wet_bulb_stull(temp_celsius, relative_humidity):
    """
    Tính nhiệt độ bầu ướt theo công thức Stull (2011)
    
    Args:
        temp_celsius (float): Nhiệt độ khô (°C)
        relative_humidity (float): Độ ẩm tương đối (%)
    
    Returns:
        float: Nhiệt độ bầu ướt (°C)
    
    Reference:
        Stull, R. (2011). Wet-Bulb Temperature from Relative Humidity and Air Temperature.
        Journal of Applied Meteorology and Climatology, 50(11), 2267-2269.
    """
    try:
        T = float(temp_celsius)
        RH = float(relative_humidity)
        
        # Kiểm tra giá trị đầu vào
        if RH < 0 or RH > 100:
            raise ValueError(f"Relative humidity must be between 0-100%, got {RH}%")
        if T < -50 or T > 60:
            raise ValueError(f"Temperature must be between -50°C to 60°C, got {T}°C")
        
        # Công thức Stull (2011) - đơn giản hóa
        Tw = T * math.atan(0.151977 * math.sqrt(RH + 8.313659)) + \
             math.atan(T + RH) - \
             math.atan(RH - 1.676331) + \
             0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH) - \
             4.686035
        
        logger.debug(f"Wet bulb calculation: T={T}°C, RH={RH}% -> Tw={Tw:.2f}°C")
        return Tw

    except Exception as e:
        logger.error(f"Error calculating wet bulb temperature: {e}")
        raise ValueError(f"Cannot calculate wet bulb temperature: {e}")

def calculate_cooling_tower_efficiency(water_temp_in, water_temp_out, wet_bulb_temp_in):
    """
    Tính hiệu suất tháp giải nhiệt
    
    Args:
        water_temp_in (float): Nhiệt độ nước vào (°C)
        water_temp_out (float): Nhiệt độ nước ra (°C)
        wet_bulb_temp_in (float): Nhiệt độ bầu ướt không khí vào (°C)
    
    Returns:
        float: Hiệu suất (%)
    """
    try:
        T_in = float(water_temp_in)
        T_out = float(water_temp_out)
        T_wb = float(wet_bulb_temp_in)
        
        # Kiểm tra logic nhiệt độ với tolerance
        delta_T = T_in - T_out
        if delta_T < -TEMPERATURE_TOLERANCE:
            raise ValueError(f"Water inlet temperature ({T_in}°C) must be higher than outlet ({T_out}°C) by at least {TEMPERATURE_TOLERANCE}°C. Current difference: {delta_T:.3f}°C")
        
        # Nếu chênh lệch nhiệt độ quá nhỏ (trong tolerance), coi như không có chênh lệch
        if abs(delta_T) <= TEMPERATURE_TOLERANCE:
            logger.warning(f"Temperature difference too small: {delta_T:.3f}°C (within tolerance {TEMPERATURE_TOLERANCE}°C). Setting efficiency to 0%")
            return 0.0
        
        # Kiểm tra wet bulb temperature
        if T_in <= T_wb:
            logger.warning(f"Water inlet temperature ({T_in}°C) is not higher than wet bulb temperature ({T_wb}°C). This indicates no cooling is possible.")
            return 0.0
        
        # Hiệu suất = (T_in - T_out) / (T_in - T_wb) * 100
        efficiency = (delta_T / (T_in - T_wb)) * 100
        
        # Giới hạn hiệu suất trong khoảng hợp lý
        if efficiency < 0:
            efficiency = 0
        elif efficiency > 100:
            efficiency = 100
        
        logger.debug(f"Efficiency calculation: ({T_in} - {T_out}) / ({T_in} - {T_wb}) * 100 = {efficiency:.2f}%")
        return efficiency

    except Exception as e:
        logger.error(f"Error calculating cooling tower efficiency: {e}")
        raise ValueError(f"Cannot calculate cooling tower efficiency: {e}")

def calculate_cooling_capacity(water_flow_lpm, water_temp_in, water_temp_out):
    """
    Tính công suất giải nhiệt
    
    Args:
        water_flow_lpm (float): Lưu lượng nước (L/phút)
        water_temp_in (float): Nhiệt độ nước vào (°C)
        water_temp_out (float): Nhiệt độ nước ra (°C)
    
    Returns:
        float: Công suất giải nhiệt (kW)
    """
    try:
        flow_lpm = float(water_flow_lpm)
        T_in = float(water_temp_in)
        T_out = float(water_temp_out)
        
        # Kiểm tra giá trị đầu vào
        if flow_lpm <= 0:
            raise ValueError(f"Water flow must be positive, got {flow_lpm} L/min")
        
        # Kiểm tra logic nhiệt độ với tolerance
        delta_T = T_in - T_out
        if delta_T < -TEMPERATURE_TOLERANCE:
            raise ValueError(f"Water inlet temperature ({T_in}°C) must be higher than outlet ({T_out}°C) by at least {TEMPERATURE_TOLERANCE}°C. Current difference: {delta_T:.3f}°C")
        
        # Nếu chênh lệch nhiệt độ quá nhỏ (trong tolerance), coi như không có chênh lệch
        if abs(delta_T) <= TEMPERATURE_TOLERANCE:
            logger.warning(f"Temperature difference too small: {delta_T:.3f}°C (within tolerance {TEMPERATURE_TOLERANCE}°C). Setting cooling capacity to 0 kW")
            return 0.0
        
        # Chuyển đổi lưu lượng từ L/phút sang kg/s
        # Giả định mật độ nước = 1000 kg/m³
        flow_kg_s = (flow_lpm / 60) * (1000 / 1000)  # kg/s
        
        # Nhiệt dung riêng của nước = 4.186 kJ/kg·K
        cp_water = 4.186  # kJ/kg·K
        
        # Công suất = ṁ × cp × ΔT
        cooling_capacity = flow_kg_s * cp_water * delta_T  # kW
        
        logger.debug(f"Cooling capacity calculation: {flow_kg_s:.2f} kg/s × {cp_water} kJ/kg·K × {delta_T:.2f}K = {cooling_capacity:.2f} kW")
        return cooling_capacity

    except Exception as e:
        logger.error(f"Error calculating cooling capacity: {e}")
        raise ValueError(f"Cannot calculate cooling capacity: {e}") 