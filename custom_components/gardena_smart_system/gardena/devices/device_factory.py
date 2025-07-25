from .mower import Mower
from .power_socket import PowerSocket
from .sensor import Sensor
from .smart_irrigation_control import SmartIrrigationControl
from .soil_sensor import SoilSensor
from .water_control import WaterControl


class DeviceFactory:
    @staticmethod
    def build(location, device_map):
        if "MOWER" in device_map:
            return Mower(location, device_map)
        if "SENSOR" in device_map:
            if "ambientTemperature" in device_map["SENSOR"][0]["attributes"]:
                return Sensor(location, device_map)
            return SoilSensor(location, device_map)
        if "POWER_SOCKET" in device_map:
            return PowerSocket(location, device_map)
        if "VALVE" in device_map:
            if len(device_map["VALVE"]) > 1:
                return SmartIrrigationControl(location, device_map)
            return WaterControl(location, device_map)
        return None
