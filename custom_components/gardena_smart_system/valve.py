"""Support for Gardena valves (Water control, smart irrigation control)."""

import datetime
import logging

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_ACTIVITY,
    ATTR_BATTERY_STATE,
    ATTR_LAST_ERROR,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    CONF_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING_DURATION,
    DEFAULT_SMART_IRRIGATION_DURATION,
    DEFAULT_SMART_WATERING_DURATION,
    DOMAIN,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)

# Constants for pending state change protection
PENDING_STATE_TIMEOUT_SECONDS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the valves platform."""
    entities = []
    for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "WATER_CONTROL"
    ):
        entities.append(GardenaSmartWaterControl(water_control, config_entry.options))

    for smart_irrigation in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "SMART_IRRIGATION_CONTROL"
    ):
        for valve in smart_irrigation.valves.values():
            entities.append(
                GardenaSmartIrrigationControl(
                    smart_irrigation, valve["id"], config_entry.options
                )
            )

    _LOGGER.debug(
        "Adding water control and smart irrigation control as valve: %s", entities
    )
    async_add_entities(entities, update_before_add=True)


class GardenaSmartWaterControl(ValveEntity):
    """Representation of a Gardena Smart Water Control."""

    def __init__(self, wc, options) -> None:
        """Initialize the Gardena Smart Water Control."""
        self._device = wc
        self._options = options
        self._name = f"{self._device.name}"
        self._unique_id = f"{self._device.serial}-valve"
        self._state = None
        self._error_message = ""
        # Track pending state changes to prevent override
        self._pending_state_change = None
        self._pending_state_timestamp = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a water valve."""
        return False

    def update_callback(self, device) -> None:
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")

        # Check if we have a pending state change that should be respected
        if (
            self._pending_state_change is not None
            and self._pending_state_timestamp is not None
        ):
            # Only respect pending state for defined timeout period
            time_diff = (
                datetime.datetime.now(tz=datetime.UTC) - self._pending_state_timestamp
            )
            if time_diff.total_seconds() < PENDING_STATE_TIMEOUT_SECONDS:
                _LOGGER.debug("Skipping state update due to pending user action")
                return
            # Clear expired pending state
            self._pending_state_change = None
            self._pending_state_timestamp = None

        # Managing state
        state = self._device.valve_state
        _LOGGER.debug("Water control has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Water control has an error")
            self._state = False
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting water control state")
            activity = self._device.valve_activity
            self._error_message = ""
            _LOGGER.debug("Water control has activity %s", activity)
            if activity == "CLOSED":
                self._state = False
            elif activity in ["MANUAL_WATERING", "SCHEDULED_WATERING"]:
                self._state = True
            else:
                _LOGGER.debug("Water control has none activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_closed(self) -> bool:
        """Return true if the valve is closed."""
        return not self._state

    @property
    def device_class(self):
        """Return the device class for water valves."""
        return ValveDeviceClass.WATER

    @property
    def supported_features(self):
        """Return the supported features."""
        return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    @property
    def reports_position(self) -> bool:
        """Return False as this valve does not report position."""
        return False

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.valve_state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the water valve."""
        attributes = {
            ATTR_ACTIVITY: self._device.valve_activity,
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_LAST_ERROR: self._error_message,
        }

        # Add duration attributes if available as numbers (seconds) - only if valve is active
        valve_activity = getattr(self._device, "valve_activity", "CLOSED")
        is_valve_active = valve_activity in ["MANUAL_WATERING", "SCHEDULED_WATERING"]

        # Only show duration attributes if valve is active AND has valid values
        if (
            is_valve_active
            and hasattr(self._device, "valve_duration")
            and isinstance(self._device.valve_duration, int)
            and self._device.valve_duration > 0
        ):
            attributes["valve_duration"] = self._device.valve_duration
        if (
            is_valve_active
            and hasattr(self._device, "valve_duration_timestamp")
            and self._device.valve_duration_timestamp != "N/A"
        ):
            attributes["valve_duration_timestamp"] = (
                self._device.valve_duration_timestamp
            )
        if (
            is_valve_active
            and hasattr(self._device, "valve_remaining_time")
            and isinstance(self._device.valve_remaining_time, int)
            and self._device.valve_remaining_time > 0
        ):
            attributes["valve_remaining_time"] = self._device.valve_remaining_time

        return attributes

    @property
    def option_smart_watering_duration(self) -> int:
        return self._options.get(
            CONF_SMART_WATERING_DURATION, DEFAULT_SMART_WATERING_DURATION
        )

    async def async_open_valve(self) -> None:
        """Open the valve to start watering."""
        duration = self.option_smart_watering_duration * 60
        await self._device.start_seconds_to_override(duration)
        # Set pending state to prevent immediate override
        self._pending_state_change = True
        self._pending_state_timestamp = datetime.datetime.now(tz=datetime.UTC)
        # Immediately update state for responsive UI
        self._state = True
        self.async_write_ha_state()

    async def async_close_valve(self) -> None:
        """Close the valve to stop watering."""
        await self._device.stop_until_next_task()
        # Set pending state to prevent immediate override
        self._pending_state_change = False
        self._pending_state_timestamp = datetime.datetime.now(tz=datetime.UTC)
        # Immediately update state for responsive UI
        self._state = False
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }


class GardenaSmartIrrigationControl(ValveEntity):
    """Representation of a Gardena Smart Irrigation Control."""

    def __init__(self, sic, valve_id, options) -> None:
        """Initialize the Gardena Smart Irrigation Control."""
        self._device = sic
        self._valve_id = valve_id
        self._options = options
        self._name = (
            f"{self._device.name} - {self._device.valves[self._valve_id]['name']}"
        )
        self._unique_id = f"{self._device.serial}-valve-{self._valve_id}"
        self._state = None
        self._error_message = ""
        # Track pending state changes to prevent override
        self._pending_state_change = None
        self._pending_state_timestamp = None

        # Timer for regular remaining time updates
        self._update_timer = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        self._device.add_callback(self.update_callback)

        # Set up timer for regular remaining time updates
        self._update_timer = async_track_time_interval(
            self.hass, self._async_timer_update, datetime.timedelta(seconds=10)
        )
        _LOGGER.debug("Timer set up for irrigation valve %s", self._valve_id)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up timer when removing from hass."""
        if self._update_timer:
            self._update_timer()
            self._update_timer = None

    async def _async_timer_update(self, now) -> None:
        """Timer-based update for remaining time."""
        # Only update if valve has active duration tracking
        if (
            hasattr(self._device, "valve_durations")
            and self._valve_id in self._device.valve_durations
        ):
            valve_duration_data = self._device.valve_durations[self._valve_id]

            if (
                valve_duration_data.get("was_active")
                and valve_duration_data.get("timestamp") != "N/A"
                and isinstance(valve_duration_data.get("duration"), int)
                and valve_duration_data.get("duration") > 0
            ):
                try:
                    start_time = datetime.datetime.fromisoformat(
                        valve_duration_data["timestamp"]
                    )
                    current_time = datetime.datetime.now(datetime.UTC)
                    elapsed_seconds = int((current_time - start_time).total_seconds())
                    remaining_seconds = max(
                        0, valve_duration_data["duration"] - elapsed_seconds
                    )

                    # Update the remaining time and schedule HA state update
                    old_remaining = valve_duration_data.get("remaining_time", -1)
                    valve_duration_data["remaining_time"] = remaining_seconds

                    _LOGGER.debug(
                        "TIMER UPDATE - Valve %s: %d → %d seconds remaining",
                        self._valve_id,
                        old_remaining,
                        remaining_seconds,
                    )

                    # Force Home Assistant to update the entity state
                    self.async_schedule_update_ha_state(force_refresh=True)

                except ValueError as e:
                    _LOGGER.debug("Error in timer update: %s", e)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a smart irrigation control."""
        return False

    def update_callback(self, device) -> None:
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")

        # Check if we have a pending state change that should be respected
        if (
            self._pending_state_change is not None
            and self._pending_state_timestamp is not None
        ):
            # Only respect pending state for defined timeout period
            time_diff = (
                datetime.datetime.now(tz=datetime.UTC) - self._pending_state_timestamp
            )
            if time_diff.total_seconds() < PENDING_STATE_TIMEOUT_SECONDS:
                _LOGGER.debug("Skipping state update due to pending user action")
                return
            # Clear expired pending state
            self._pending_state_change = None
            self._pending_state_timestamp = None

        # Managing state
        valve = self._device.valves[self._valve_id]
        _LOGGER.debug("Valve has state: %s", valve["state"])
        if valve["state"] in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Valve has an error")
            self._state = False
            self._error_message = valve["last_error_code"]
        else:
            _LOGGER.debug("Getting Valve state")
            activity = valve["activity"]
            self._error_message = ""
            _LOGGER.debug("Valve has activity: %s", activity)
            if activity == "CLOSED":
                self._state = False
            elif activity in ["MANUAL_WATERING", "SCHEDULED_WATERING"]:
                self._state = True
            else:
                _LOGGER.debug("Valve has unknown activity")

        # IMPORTANT: Force remaining time recalculation during async_update
        if (
            hasattr(self._device, "valve_durations")
            and self._valve_id in self._device.valve_durations
        ):
            valve_duration_data = self._device.valve_durations[self._valve_id]

            # Force recalculation of remaining time for active valves
            if (
                valve_duration_data.get("was_active")
                and valve_duration_data.get("timestamp") != "N/A"
                and isinstance(valve_duration_data.get("duration"), int)
                and valve_duration_data.get("duration") > 0
            ):
                try:
                    start_time = datetime.datetime.fromisoformat(
                        valve_duration_data["timestamp"]
                    )
                    current_time = datetime.datetime.now(datetime.UTC)
                    elapsed_seconds = int((current_time - start_time).total_seconds())
                    remaining_seconds = max(
                        0, valve_duration_data["duration"] - elapsed_seconds
                    )

                    # Update the remaining time in device data
                    old_remaining = valve_duration_data.get("remaining_time", -1)
                    valve_duration_data["remaining_time"] = remaining_seconds

                    _LOGGER.debug(
                        "ASYNC UPDATE - Valve %s: remaining %d → %d (elapsed=%d)",
                        self._valve_id,
                        old_remaining,
                        remaining_seconds,
                        elapsed_seconds,
                    )
                except Exception as e:
                    _LOGGER.debug(
                        "Error in async_update remaining time calculation: %s", e
                    )
            else:
                _LOGGER.debug("Valve has unknown activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_closed(self) -> bool:
        """Return true if the valve is closed."""
        return not self._state

    @property
    def device_class(self):
        """Return the device class for water valves."""
        return ValveDeviceClass.WATER

    @property
    def supported_features(self):
        """Return the supported features."""
        return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    @property
    def reports_position(self) -> bool:
        """Return False as this valve does not report position."""
        return False

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.valves[self._valve_id]["state"] != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the smart irrigation control."""
        _LOGGER.debug(
            "REMAINING TIME DEBUG - extra_state_attributes called for valve %s",
            self._valve_id,
        )

        attributes = {
            ATTR_ACTIVITY: self._device.valves[self._valve_id]["activity"],
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_LAST_ERROR: self._error_message,
        }

        # Add valve-specific duration attributes if available
        if (
            hasattr(self._device, "valve_durations")
            and self._valve_id in self._device.valve_durations
        ):
            valve_duration_data = self._device.valve_durations[self._valve_id]
            _LOGGER.debug(
                "REMAINING TIME DEBUG - Found valve_duration_data: %s",
                valve_duration_data,
            )

            # Calculate current remaining time if valve is active with API duration
            if (
                valve_duration_data.get("was_active")
                and valve_duration_data.get("timestamp") != "N/A"
                and isinstance(valve_duration_data.get("duration"), int)
                and valve_duration_data.get("duration") > 0
            ):
                # Recalculate remaining time in real-time
                try:
                    start_time = datetime.datetime.fromisoformat(
                        valve_duration_data["timestamp"]
                    )
                    current_time = datetime.datetime.now(datetime.UTC)
                    elapsed_seconds = int((current_time - start_time).total_seconds())
                    remaining_seconds = max(
                        0, valve_duration_data["duration"] - elapsed_seconds
                    )

                    _LOGGER.debug(
                        "REMAINING TIME DEBUG - Recalculated: start=%s, current=%s, elapsed=%d, remaining=%d",
                        start_time,
                        current_time,
                        elapsed_seconds,
                        remaining_seconds,
                    )

                    # Update the remaining time in device data
                    valve_duration_data["remaining_time"] = remaining_seconds
                except Exception as e:
                    # Fallback to stored value
                    _LOGGER.debug("REMAINING TIME DEBUG - Error in calculation: %s", e)
            else:
                _LOGGER.debug(
                    "REMAINING TIME DEBUG - Conditions not met: was_active=%s, timestamp=%s, duration=%s",
                    valve_duration_data.get("was_active"),
                    valve_duration_data.get("timestamp"),
                    valve_duration_data.get("duration"),
                )

            # Add duration attributes as numbers (seconds) - only if valve is active or has valid duration
            valve_activity = self._device.valves.get(self._valve_id, {}).get(
                "activity", "CLOSED"
            )
            is_valve_active = valve_activity in [
                "MANUAL_WATERING",
                "SCHEDULED_WATERING",
            ]

            _LOGGER.debug(
                "REMAINING TIME DEBUG - valve_activity=%s, is_valve_active=%s",
                valve_activity,
                is_valve_active,
            )

            # Only show duration attributes if valve is active OR if there's a meaningful duration > 0
            if is_valve_active and valve_duration_data.get("duration", 0) > 0:
                attributes["valve_duration"] = valve_duration_data["duration"]
                _LOGGER.debug(
                    "REMAINING TIME DEBUG - Added valve_duration: %s",
                    valve_duration_data["duration"],
                )

            if is_valve_active and valve_duration_data.get("timestamp") != "N/A":
                attributes["valve_duration_timestamp"] = valve_duration_data[
                    "timestamp"
                ]
                _LOGGER.debug(
                    "REMAINING TIME DEBUG - Added valve_duration_timestamp: %s",
                    valve_duration_data["timestamp"],
                )

            if is_valve_active and valve_duration_data.get("remaining_time", 0) > 0:
                attributes["valve_remaining_time"] = valve_duration_data[
                    "remaining_time"
                ]
                _LOGGER.debug(
                    "REMAINING TIME DEBUG - Added valve_remaining_time: %s",
                    valve_duration_data["remaining_time"],
                )
            else:
                _LOGGER.debug(
                    "REMAINING TIME DEBUG - Not adding remaining_time: active=%s, remaining=%s",
                    is_valve_active,
                    valve_duration_data.get("remaining_time", 0),
                )
        else:
            # Fallback to device-level attributes (for backwards compatibility)
            valve_activity = self._device.valves.get(self._valve_id, {}).get(
                "activity", "CLOSED"
            )
            is_valve_active = valve_activity in [
                "MANUAL_WATERING",
                "SCHEDULED_WATERING",
            ]

            # Only show duration attributes if valve is active AND has valid duration
            if (
                is_valve_active
                and hasattr(self._device, "valve_duration")
                and isinstance(self._device.valve_duration, int)
                and self._device.valve_duration > 0
            ):
                attributes["valve_duration"] = self._device.valve_duration
            if (
                is_valve_active
                and hasattr(self._device, "valve_duration_timestamp")
                and self._device.valve_duration_timestamp != "N/A"
            ):
                attributes["valve_duration_timestamp"] = (
                    self._device.valve_duration_timestamp
                )
            if (
                is_valve_active
                and hasattr(self._device, "valve_remaining_time")
                and isinstance(self._device.valve_remaining_time, int)
                and self._device.valve_remaining_time > 0
            ):
                attributes["valve_remaining_time"] = self._device.valve_remaining_time

        return attributes

    @property
    def option_smart_irrigation_duration(self) -> int:
        return self._options.get(
            CONF_SMART_IRRIGATION_DURATION, DEFAULT_SMART_IRRIGATION_DURATION
        )

    async def async_open_valve(self) -> None:
        """Open the valve to start watering."""
        duration = self.option_smart_irrigation_duration * 60
        await self._device.start_seconds_to_override(duration, self._valve_id)
        # Set pending state to prevent immediate override
        self._pending_state_change = True
        self._pending_state_timestamp = datetime.datetime.now(tz=datetime.UTC)
        # Immediately update state for responsive UI
        self._state = True
        self.async_write_ha_state()

    async def async_close_valve(self) -> None:
        """Close the valve to stop watering."""
        await self._device.stop_until_next_task(self._valve_id)
        # Set pending state to prevent immediate override
        self._pending_state_change = False
        self._pending_state_timestamp = datetime.datetime.now(tz=datetime.UTC)
        # Immediately update state for responsive UI
        self._state = False
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }
