"""Water control device for Gardena Smart System."""

import uuid

from .base_device import BaseDevice


class WaterControl(BaseDevice):
    """Water control device for smart valve management."""

    def __init__(self, location, device_map) -> None:
        """Initialize the water control device."""
        BaseDevice.__init__(self, location, device_map["COMMON"][0]["id"])
        self.type = "WATER_CONTROL"
        self.valve_set_id = "N/A"
        self.valve_id = "N/A"
        self.valve_activity = "N/A"
        self.valve_name = "N/A"
        self.valve_state = "N/A"
        self.last_error_code = "N/A"

        # Duration attributes for timed valve operations
        self.valve_duration = "N/A"
        self.valve_duration_timestamp = "N/A"
        self.valve_remaining_time = "N/A"

        self.setup_values_from_device_map(device_map)

    def update_device_specific_data(self, device_map) -> None:
        """Update water control specific data."""
        if device_map["type"] == "VALVE_SET":
            self.valve_set_id = device_map["id"]
        if device_map["type"] == "VALVE":
            self.valve_id = device_map["id"]
            self.set_attribute_value("valve_activity", device_map, "activity")
            self.set_attribute_value("valve_name", device_map, "name")
            self.set_attribute_value("valve_state", device_map, "state")
            self.set_attribute_value("last_error_code", device_map, "lastErrorCode")

            # Duration attributes for valve operations
            self.set_duration_attributes("valve", device_map, "valveDuration")

    async def start_seconds_to_override(self, duration) -> None:
        """Start valve override operation for specified duration in seconds."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "START_SECONDS_TO_OVERRIDE", "seconds": duration},
        }
        await self.location.smart_system.call_smart_system_service(self.valve_id, data)

    async def stop_until_next_task(self) -> None:
        """Stop valve until next scheduled task."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "STOP_UNTIL_NEXT_TASK"},
        }
        await self.location.smart_system.call_smart_system_service(self.valve_id, data)

    async def pause(self) -> None:
        """Pause the valve operation."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "PAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(self.valve_id, data)

    async def unpause(self) -> None:
        """Resume the valve operation."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "UNPAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(self.valve_id, data)
