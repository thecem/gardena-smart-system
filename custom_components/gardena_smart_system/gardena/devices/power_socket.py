"""Power socket device for Gardena Smart System."""

import uuid

from .base_device import BaseDevice


class PowerSocket(BaseDevice):
    """Power socket device for smart power control."""

    def __init__(self, location, device_map):
        """Initialize the Power socket device."""
        BaseDevice.__init__(self, location, device_map["COMMON"][0]["id"])
        self.type = "POWER_SOCKET"
        self.activity = "N/A"
        self.state = "N/A"
        self.last_error_code = "N/A"

        # Duration attributes for timed operations
        self.override_duration = "N/A"
        self.override_duration_timestamp = "N/A"
        self.override_remaining_time = "N/A"

        self.setup_values_from_device_map(device_map)

    def update_device_specific_data(self, device_map):
        """Update power socket specific data."""
        if device_map["type"] == "POWER_SOCKET":
            # Standard attributes
            self.set_attribute_value("activity", device_map, "activity")
            self.set_attribute_value("state", device_map, "state")
            self.set_attribute_value("last_error_code", device_map, "lastErrorCode")

            # Duration attributes for override operations
            self.set_duration_attributes("override", device_map, "overrideDuration")

    async def start_seconds_to_override(self, duration):
        """Start override operation for specified duration in seconds."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "POWER_SOCKET_CONTROL",
            "attributes": {"command": "START_SECONDS_TO_OVERRIDE", "seconds": duration},
        }
        await self.location.smart_system.call_smart_system_service(self.id, data)

    async def start_override(self):
        """Start override operation without duration limit."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "POWER_SOCKET_CONTROL",
            "attributes": {"command": "START_OVERRIDE"},
        }
        await self.location.smart_system.call_smart_system_service(self.id, data)

    async def stop_until_next_task(self):
        """Stop until next scheduled task."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "POWER_SOCKET_CONTROL",
            "attributes": {"command": "STOP_UNTIL_NEXT_TASK"},
        }
        await self.location.smart_system.call_smart_system_service(self.id, data)

    async def pause(self):
        """Pause the power socket operation."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "POWER_SOCKET_CONTROL",
            "attributes": {"command": "PAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(self.id, data)

    async def unpause(self):
        """Resume the power socket operation."""
        data = {
            "id": str(uuid.uuid1()),
            "type": "POWER_SOCKET_CONTROL",
            "attributes": {"command": "UNPAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(self.id, data)
