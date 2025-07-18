"""Base device class for Gardena Smart System devices."""

from datetime import UTC, datetime

from ..base_gardena_class import BaseGardenaClass


class BaseDevice(BaseGardenaClass):
    """Base class informations about gardena devices."""

    def __init__(self, location, device_id):
        """Initialize the BaseDevice."""
        self.location = location
        self.id = device_id
        self.type = "N/A"
        self.battery_level = "N/A"
        self.battery_state = "N/A"
        self.name = "N/A"
        self.rf_link_level = "N/A"
        self.rf_link_state = "N/A"
        self.serial = "N/A"
        self.model_type = "N/A"
        self.callbacks = []

    def setup_values_from_device_map(self, device_map):
        """Set up initial values from device map."""
        for messages_list in device_map.values():
            for message in messages_list:
                self.update_data(message)

    def add_callback(self, callback):
        """Add a callback for data updates."""
        self.callbacks.append(callback)

    def update_data(self, device_map):
        """Update device data from device map."""
        if device_map["type"] == "COMMON":
            self.update_common_data(device_map)
        self.update_device_specific_data(device_map)
        for callback in self.callbacks:
            callback(self)

    def update_common_data(self, common_map):
        """Update common device data."""
        self.set_attribute_value("battery_level", common_map, "batteryLevel")
        self.set_attribute_value("battery_state", common_map, "batteryState")
        self.set_attribute_value("name", common_map, "name")
        self.set_attribute_value("rf_link_level", common_map, "rfLinkLevel")
        self.set_attribute_value("rf_link_state", common_map, "rfLinkState")
        self.set_attribute_value("serial", common_map, "serial")
        self.set_attribute_value("model_type", common_map, "modelType")

    def set_attribute_value(self, field_name, attributes_map, attribute_name):
        """Set a single attribute value from the attributes map."""
        if attribute_name in attributes_map["attributes"]:
            setattr(
                self, field_name, attributes_map["attributes"][attribute_name]["value"]
            )

    def set_duration_attributes(self, field_prefix, attributes_map, attribute_name):
        """Set duration-related attributes including timestamp, value, and remaining time."""
        if attribute_name in attributes_map["attributes"]:
            duration_data = attributes_map["attributes"][attribute_name]

            # Set the main duration value
            setattr(self, f"{field_prefix}_duration", duration_data.get("value", "N/A"))

            # Set the timestamp when this duration was set/updated
            setattr(
                self,
                f"{field_prefix}_duration_timestamp",
                duration_data.get("timestamp", "N/A"),
            )

            # Calculate remaining time if we have both value and timestamp
            remaining_time = self._calculate_remaining_time(duration_data)
            setattr(self, f"{field_prefix}_remaining_time", remaining_time)

    def _calculate_remaining_time(self, duration_data):
        """Calculate remaining time based on duration value and timestamp."""
        try:
            if "value" not in duration_data or "timestamp" not in duration_data:
                return "N/A"

            duration_seconds = duration_data["value"]
            if not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0:
                return "N/A"

            # Parse the timestamp
            timestamp_str = duration_data["timestamp"]
            if not timestamp_str:
                return "N/A"

            # Parse ISO 8601 timestamp
            start_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            current_time = datetime.now(UTC)

            # Calculate elapsed time
            elapsed_seconds = (current_time - start_time).total_seconds()

            # Calculate remaining time
            remaining_seconds = max(0, duration_seconds - elapsed_seconds)

            return int(remaining_seconds)

        except (ValueError, TypeError, AttributeError):
            # If any calculation fails, return N/A
            return "N/A"

    def update_device_specific_data(self, device_map):
        """
        Update device-specific data.

        To be implemented by subclasses.
        """
