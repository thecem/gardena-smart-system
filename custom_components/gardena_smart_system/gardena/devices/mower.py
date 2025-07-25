"""Mower device for Gardena Smart System."""

import uuid

from .base_device import BaseDevice


class Mower(BaseDevice):
    """Mower device for smart lawn cutting operations."""

    def __init__(self, location, device_map) -> None:
        """Initialize the mower device."""
        BaseDevice.__init__(self, location, device_map["COMMON"][0]["id"])
        self.type = "MOWER"
        self.activity = "N/A"
        self.operating_hours = "N/A"
        self.state = "N/A"
        self.last_error_code = "N/A"
        self.mower_id = None

        # Duration attributes for timed mowing operations
        self.mowing_duration = "N/A"
        self.mowing_duration_timestamp = "N/A"
        self.mowing_remaining_time = "N/A"

        self.setup_values_from_device_map(device_map)

    def update_device_specific_data(self, device_map) -> None:
        """Update mower specific data."""
        # Mower has only one item
        if device_map["type"] == "MOWER":
            self.mower_id = device_map["id"]
            self.set_attribute_value("activity", device_map, "activity")
            self.set_attribute_value("operating_hours", device_map, "operatingHours")
            self.set_attribute_value("state", device_map, "state")
            self.set_attribute_value("last_error_code", device_map, "lastErrorCode")

            # Duration attributes for mowing operations
            self.set_duration_attributes("mowing", device_map, "mowingDuration")

    async def start_seconds_to_override(self, duration) -> None:
        """Start mowing override operation for specified duration in seconds."""
        if self.mower_id is not None:
            data = {
                "id": str(uuid.uuid1()),
                "type": "MOWER_CONTROL",
                "attributes": {
                    "command": "START_SECONDS_TO_OVERRIDE",
                    "seconds": duration,
                },
            }
            await self.location.smart_system.call_smart_system_service(
                self.mower_id, data
            )
        else:
            self.location.smart_system.logger.error("The mower id is not defined")

    async def start_dont_override(self) -> None:
        """Start mowing without overriding the schedule."""
        if self.mower_id is not None:
            data = {
                "id": str(uuid.uuid1()),
                "type": "MOWER_CONTROL",
                "attributes": {"command": "START_DONT_OVERRIDE"},
            }
            await self.location.smart_system.call_smart_system_service(
                self.mower_id, data
            )
        else:
            self.location.smart_system.logger.error("The mower id is not defined")

    async def park_until_next_task(self) -> None:
        """Park mower until next scheduled task."""
        if self.mower_id is not None:
            data = {
                "id": str(uuid.uuid1()),
                "type": "MOWER_CONTROL",
                "attributes": {"command": "PARK_UNTIL_NEXT_TASK"},
            }
            await self.location.smart_system.call_smart_system_service(
                self.mower_id, data
            )
        else:
            self.location.smart_system.logger.error("The mower id is not defined")

    async def park_until_further_notice(self) -> None:
        """Park mower until manually restarted."""
        if self.mower_id is not None:
            data = {
                "id": str(uuid.uuid1()),
                "type": "MOWER_CONTROL",
                "attributes": {"command": "PARK_UNTIL_FURTHER_NOTICE"},
            }
            await self.location.smart_system.call_smart_system_service(
                self.mower_id, data
            )
        else:
            self.location.smart_system.logger.error("The mower id is not defined")
