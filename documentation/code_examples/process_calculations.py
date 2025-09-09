#!/usr/bin/env python3
import math
import logging
from datetime import datetime
from typing import Dict, Optional, Any

def calculate_wet_bulb_temperature(T_dry: float, RH: float) -> Optional[float]:
    if not ((-50 <= T_dry <= 80) and (0 <= RH <= 100)): return None
    try:
        T_wb = T_dry * math.atan(0.151977 * math.sqrt(RH + 8.313659)) + \
               math.atan(T_dry + RH) - math.atan(RH - 1.676331) + \
               0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH) - 4.686035
        return round(T_wb, 2)
    except: return None

def calculate_cooling_efficiency(T_in: float, T_out: float, T_wb: float) -> float:
    if T_in <= T_wb or T_out >= T_in: return 0.0
    return round(max(0.0, min(100.0, ((T_in - T_out) / (T_in - T_wb)) * 100)), 1)

def calculate_cooling_capacity(flow_rate_lpm: float, T_in: float, T_out: float) -> float:
    if flow_rate_lpm <= 0 or T_in <= T_out: return 0.0
    return round((flow_rate_lpm / 60.0) * 4.186 * (T_in - T_out), 1)

def calculate_approach_temperature(T_out: float, T_wb: float) -> float:
    return round(T_out - T_wb, 2)

def calculate_cooling_range(T_in: float, T_out: float) -> float:
    return round(T_in - T_out, 2)

def process_sensor_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        flow_rate = raw_data.get('flow_rate', 0)
        T_in, T_out = raw_data.get('water_temp_inlet', 0), raw_data.get('water_temp_outlet', 0)
        air_temp, air_humidity = raw_data.get('air_temp_inlet', 0), raw_data.get('air_humidity_inlet', 0)
        T_wb = calculate_wet_bulb_temperature(air_temp, air_humidity)
        
        return {
            'device_id': raw_data.get('device_id'), 'timestamp': datetime.now().isoformat(),
            'water_flow_lpm': round(flow_rate, 2), 'water_temp_in': round(T_in, 2), 'water_temp_out': round(T_out, 2),
            'air_temp_in': round(air_temp, 2), 'air_humidity_in': round(air_humidity, 1), 'wet_bulb_temp_in': T_wb,
            'cooling_efficiency': calculate_cooling_efficiency(T_in, T_out, T_wb) if T_wb else 0.0,
            'cooling_capacity': calculate_cooling_capacity(flow_rate, T_in, T_out),
            'approach_temp': calculate_approach_temperature(T_out, T_wb) if T_wb else 0.0,
            'cooling_range': calculate_cooling_range(T_in, T_out)
        }
    except Exception as e:
        return {'error': 'data_processing_error', 'message': str(e), 'timestamp': datetime.now().isoformat()}
