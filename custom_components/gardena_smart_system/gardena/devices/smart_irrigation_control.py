import uuid

from .base_device import BaseDevice


class SmartIrrigationControl(BaseDevice):
    def __init__(self, location, device_map) -> None:
        """Constructor for the smart irrigation control device."""
        BaseDevice.__init__(self, location, device_map["COMMON"][0]["id"])
        self.type = "SMART_IRRIGATION_CONTROL"
        self.valve_set_id = "N/A"
        self.valve_set_state = "N/A"
        self.valve_set_last_error_code = "N/A"
        self.valves = {}

        # Duration attributes per valve - will be populated when valves are created
        self.valve_durations = {}  # valve_id -> duration info

        # Device-level duration attributes (for compatibility with existing sensor code)
        self.valve_duration = "N/A"
        self.valve_duration_timestamp = "N/A"
        self.valve_remaining_time = "N/A"

        self.setup_values_from_device_map(device_map)

    def _set_valves_map_value(
        self, target_map, source_map, value_name_in_source, value_name_in_target=None
    ) -> None:
        if not value_name_in_target:
            value_name_in_target = value_name_in_source
        if value_name_in_source in source_map:
            target_map[value_name_in_target] = source_map[value_name_in_source]["value"]
        else:
            target_map[value_name_in_target] = "N/A"

    def update_device_specific_data(self, device_map) -> None:
        if device_map["type"] == "VALVE_SET":
            # SmartIrrigationControl has only one item
            self.valve_set_id = device_map["id"]
            self.set_attribute_value("valve_set_state", device_map, "state")
            self.set_attribute_value(
                "valve_set_last_error_code", device_map, "lastErrorCode"
            )
        if device_map["type"] == "VALVE":
            valve_id = device_map["id"]
            self.valves[valve_id] = {"id": valve_id}

            # Debug: Log all available data for valve to find duration
            import logging

            logger = logging.getLogger(__name__)
            logger.debug("VALVE DEBUG - Processing valve %s", valve_id)
            logger.debug("VALVE DEBUG - Complete device_map structure: %s", device_map)
            logger.debug(
                "VALVE DEBUG - Available attributes: %s",
                list(device_map.get("attributes", {}).keys()),
            )
            if "attributes" in device_map:
                for attr_name, attr_data in device_map["attributes"].items():
                    if "duration" in attr_name.lower() or "time" in attr_name.lower():
                        logger.debug(
                            "VALVE DEBUG - Found time/duration attribute: %s = %s",
                            attr_name,
                            attr_data,
                        )
                    logger.debug("VALVE DEBUG - Attribute %s: %s", attr_name, attr_data)

            self._set_valves_map_value(
                self.valves[device_map["id"]], device_map["attributes"], "activity"
            )
            self._set_valves_map_value(
                self.valves[device_map["id"]],
                device_map["attributes"],
                "lastErrorCode",
                "last_error_code",
            )
            self._set_valves_map_value(
                self.valves[device_map["id"]], device_map["attributes"], "name"
            )
            self._set_valves_map_value(
                self.valves[device_map["id"]], device_map["attributes"], "state"
            )

            # Look for duration information in various possible API fields
            duration_found = False
            if "attributes" in device_map:
                # Check for various possible duration field names from API
                possible_duration_fields = [
                    "valveDuration",
                    "duration",
                    "watering_duration",
                    "remainingTime",
                    "remaining_time",
                    "watering_time",
                    "schedule_duration",
                    "timer",
                ]

                for field_name in possible_duration_fields:
                    if field_name in device_map["attributes"]:
                        # Found API duration data - but only use it if valve is active
                        duration_data = device_map["attributes"][field_name]

                        # Check if valve is currently active
                        valve_activity = (
                            device_map.get("attributes", {})
                            .get("activity", {})
                            .get("value", "CLOSED")
                        )
                        is_valve_active = valve_activity in [
                            "MANUAL_WATERING",
                            "SCHEDULED_WATERING",
                        ]

                        if (
                            isinstance(duration_data, dict)
                            and "value" in duration_data
                            and "timestamp" in duration_data
                            and is_valve_active  # Only process duration if valve is active
                        ):
                            # Extract duration value and timestamp
                            duration_seconds = duration_data["value"]
                            start_timestamp = duration_data["timestamp"]

                            # Calculate remaining time
                            import datetime

                            try:
                                start_time = datetime.datetime.fromisoformat(
                                    start_timestamp
                                )
                                current_time = datetime.datetime.now(datetime.UTC)
                                elapsed_seconds = int(
                                    (current_time - start_time).total_seconds()
                                )
                                remaining_seconds = max(
                                    0, duration_seconds - elapsed_seconds
                                )

                                # Set the duration attributes per valve AND globally (as numbers)
                                self.valve_duration = duration_seconds
                                self.valve_duration_timestamp = start_timestamp
                                self.valve_remaining_time = remaining_seconds

                                # IMPORTANT: Also set duration attributes on this specific valve
                                if valve_id not in self.valve_durations:
                                    self.valve_durations[valve_id] = {}
                                self.valve_durations[valve_id].update(
                                    {
                                        "duration": duration_seconds,  # Store as number (seconds)
                                        "timestamp": start_timestamp,
                                        "remaining_time": remaining_seconds,  # Store as number (seconds)
                                        "was_active": True,
                                    }
                                )

                                logger.debug(
                                    "Parsed duration for valve %s: total=%ds, elapsed=%ds, remaining=%ds",
                                    valve_id,
                                    duration_seconds,
                                    elapsed_seconds,
                                    remaining_seconds,
                                )
                            except Exception as e:
                                logger.debug("Error parsing duration timestamp: %s", e)
                                self.valve_duration = duration_seconds
                                self.valve_duration_timestamp = start_timestamp
                                self.valve_remaining_time = (
                                    0  # Default to 0 if calculation fails
                                )
                        elif (
                            isinstance(duration_data, dict)
                            and "value" in duration_data
                            and "timestamp" in duration_data
                            and not is_valve_active  # Valve is NOT active but has duration data
                        ):
                            # Valve is not active - clear duration attributes
                            if valve_id not in self.valve_durations:
                                self.valve_durations[valve_id] = {}
                            self.valve_durations[valve_id].update(
                                {
                                    "duration": 0,  # Clear duration when inactive
                                    "timestamp": "N/A",
                                    "remaining_time": 0,  # Clear remaining time when inactive
                                    "was_active": False,
                                }
                            )
                            # Also clear device-level attributes
                            self.valve_duration = 0
                            self.valve_duration_timestamp = "N/A"
                            self.valve_remaining_time = 0

                            logger.debug(
                                "Valve %s is inactive - cleared duration attributes",
                                valve_id,
                            )
                        else:
                            # Fallback for other duration formats
                            self.set_duration_attributes(
                                "valve", device_map, field_name
                            )

                        duration_found = True
                        logger.debug(
                            "Found API duration data in field %s for valve %s: %s",
                            field_name,
                            valve_id,
                            duration_data,
                        )
                        break

                # Also check for timestamp fields that might indicate duration
                timestamp_fields = [
                    "startTime",
                    "start_time",
                    "watering_start",
                    "operation_start",
                ]
                for field_name in timestamp_fields:
                    if field_name in device_map["attributes"]:
                        logger.debug(
                            "Found timestamp field %s for valve %s: %s",
                            field_name,
                            valve_id,
                            device_map["attributes"][field_name],
                        )

            # If no API duration found, implement simple local tracking
            if not duration_found:
                valve_id = device_map["id"]
                activity = (
                    device_map.get("attributes", {})
                    .get("activity", {})
                    .get("value", "CLOSED")
                )

                # Initialize duration tracking for this valve if not exists
                if valve_id not in self.valve_durations:
                    self.valve_durations[valve_id] = {
                        "duration": 0,  # Store as number (seconds)
                        "timestamp": "N/A",
                        "remaining_time": 0,  # Store as number (seconds)
                        "was_active": False,
                    }

                # Track when valve becomes active
                valve_info = self.valve_durations[valve_id]
                is_currently_active = activity in [
                    "MANUAL_WATERING",
                    "SCHEDULED_WATERING",
                ]

                if is_currently_active and not valve_info["was_active"]:
                    # Valve just became active - start tracking
                    import datetime

                    valve_info["timestamp"] = datetime.datetime.now(
                        datetime.UTC
                    ).isoformat()
                    valve_info["duration"] = 0  # No API duration available yet
                    valve_info["remaining_time"] = 0  # No remaining time yet
                    valve_info["was_active"] = True
                    logger.debug(
                        "Started local tracking for valve %s at %s",
                        valve_id,
                        valve_info["timestamp"],
                    )

                elif not is_currently_active and valve_info["was_active"]:
                    # Valve just became inactive - clear duration and remaining time
                    import datetime

                    if valve_info["timestamp"] != "N/A":
                        try:
                            start_time = datetime.datetime.fromisoformat(
                                valve_info["timestamp"]
                            )
                            end_time = datetime.datetime.now(datetime.UTC)
                            duration_seconds = int(
                                (end_time - start_time).total_seconds()
                            )
                            logger.debug(
                                "Valve %s finished watering, final duration: %s seconds",
                                valve_id,
                                duration_seconds,
                            )
                        except Exception as e:
                            logger.debug(
                                "Error calculating final duration for valve %s: %s",
                                valve_id,
                                e,
                            )

                    # Reset duration attributes when valve becomes inactive
                    valve_info["duration"] = 0
                    valve_info["timestamp"] = "N/A"
                    valve_info["remaining_time"] = 0
                    valve_info["was_active"] = False
                elif is_currently_active and valve_info["was_active"]:
                    # Valve is still active - update remaining time
                    import datetime

                    if valve_info["timestamp"] != "N/A":
                        try:
                            start_time = datetime.datetime.fromisoformat(
                                valve_info["timestamp"]
                            )
                            current_time = datetime.datetime.now(datetime.UTC)
                            elapsed_seconds = int(
                                (current_time - start_time).total_seconds()
                            )
                            valve_info["remaining_time"] = (
                                elapsed_seconds  # Show elapsed time
                            )
                        except Exception:
                            valve_info["remaining_time"] = 0

                # Set device-level attributes based on any active valve
                active_valve_info = None
                for vinfo in self.valve_durations.values():
                    if vinfo["was_active"]:
                        active_valve_info = vinfo
                        break

                if active_valve_info:
                    self.valve_duration = active_valve_info["duration"]
                    self.valve_duration_timestamp = active_valve_info["timestamp"]
                    self.valve_remaining_time = active_valve_info["remaining_time"]
                else:
                    self.valve_duration = 0
                    self.valve_duration_timestamp = "N/A"
                    self.valve_remaining_time = 0

    async def start_seconds_to_override(self, duration, valve_id) -> None:
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "START_SECONDS_TO_OVERRIDE", "seconds": duration},
        }
        await self.location.smart_system.call_smart_system_service(valve_id, data)

    async def stop_until_next_task(self, valve_id) -> None:
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "STOP_UNTIL_NEXT_TASK"},
        }
        await self.location.smart_system.call_smart_system_service(valve_id, data)

    async def pause(self, valve_id) -> None:
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "PAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(valve_id, data)

    async def unpause(self, valve_id) -> None:
        data = {
            "id": str(uuid.uuid1()),
            "type": "VALVE_CONTROL",
            "attributes": {"command": "UNPAUSE"},
        }
        await self.location.smart_system.call_smart_system_service(valve_id, data)
