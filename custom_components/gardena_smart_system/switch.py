"""Support for Gardena switch (Power control)."""

import asyncio
import logging

from homeassistant.components.switch import SwitchEntity

from .const import (
    ATTR_ACTIVITY,
    ATTR_BATTERY_STATE,
    ATTR_LAST_ERROR,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    DOMAIN,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switches platform."""
    entities = []
    # Note: Water control and smart irrigation control are now handled by the valve platform
    for power_switch in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "POWER_SOCKET"
    ):
        entities.append(GardenaPowerSocket(power_switch))

    _LOGGER.debug("Adding power socket as switch: %s", entities)
    async_add_entities(entities, True)


class GardenaPowerSocket(SwitchEntity):
    """Representation of a Gardena Power Socket."""

    def __init__(self, ps):
        """Initialize the Gardena Power Socket."""
        self._device = ps
        self._name = f"{self._device.name}"
        self._unique_id = f"{self._device.serial}"
        self._state = None
        self._error_message = ""

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a power socket."""
        return False

    def update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    async def async_update(self):
        """Update the states of Gardena devices."""
        _LOGGER.debug("Running Gardena update")
        # Managing state
        state = self._device.state
        _LOGGER.debug("Power socket has state %s", state)
        if state in ["WARNING", "ERROR", "UNAVAILABLE"]:
            _LOGGER.debug("Power socket has an error")
            self._state = False
            self._error_message = self._device.last_error_code
        else:
            _LOGGER.debug("Getting Power socket state")
            activity = self._device.activity
            self._error_message = ""
            _LOGGER.debug("Power socket has activity %s", activity)
            if activity == "OFF":
                self._state = False
            elif activity in ["FOREVER_ON", "TIME_LIMITED_ON", "SCHEDULED_ON"]:
                self._state = True
            else:
                _LOGGER.debug("Power socket has none activity")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.state != "UNAVAILABLE"

    def error(self):
        """Return the error message."""
        return self._error_message

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the power switch."""
        return {
            ATTR_ACTIVITY: self._device.activity,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_LAST_ERROR: self._error_message,
        }

    def turn_on(self, **kwargs):
        """Start watering."""
        return asyncio.run_coroutine_threadsafe(
            self._device.start_override(), self.hass.loop
        ).result()

    def turn_off(self, **kwargs):
        """Stop watering."""
        return asyncio.run_coroutine_threadsafe(
            self._device.stop_until_next_task(), self.hass.loop
        ).result()

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


"""Switch platform for Gardena Smart System."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_SMART_WATERING_DURATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Smart System switches."""
    _LOGGER.debug("Setting up Gardena Smart System switches")

    entities = []

    # Power socket switches
    for power_socket in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "POWER_SOCKET"
    ):
        entities.append(GardenaPowerSocketSwitch(power_socket))

    # Water control switches
    for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "WATER_CONTROL"
    ):
        entities.append(GardenaWaterControlSwitch(water_control))

    _LOGGER.debug("Adding %d switch entities", len(entities))
    async_add_entities(entities, True)


class GardenaBaseSwitch(SwitchEntity):
    """Base class for Gardena switches."""

    def __init__(self, device):
        """Initialize the Gardena switch."""
        self._device = device
        self._name = device.name
        self._unique_id = f"{device.serial}-switch"

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for switch."""
        return False

    def update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            name=self._device.name,
            manufacturer="Gardena",
            model=self._device.model_type,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the switch."""
        attributes = {}

        # Add battery info if available
        if hasattr(self._device, "battery_level"):
            attributes[ATTR_BATTERY_STATE] = self._device.battery_state
            attributes["battery_level"] = self._device.battery_level

        # Add RF link info if available
        if hasattr(self._device, "rf_link_level"):
            attributes[ATTR_RF_LINK_LEVEL] = self._device.rf_link_level
            attributes[ATTR_RF_LINK_STATE] = self._device.rf_link_state

        return attributes


class GardenaPowerSocketSwitch(GardenaBaseSwitch):
    """Representation of a Gardena Power Socket switch."""

    @property
    def is_on(self) -> bool:
        """Return true if the power socket is on."""
        return getattr(self._device, ATTR_ACTIVITY, "OFF") != "OFF"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the power socket on."""
        duration = kwargs.get("duration", 3600)  # Default 1 hour
        await self._device.start_override(duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the power socket off."""
        await self._device.stop_override()


class GardenaWaterControlSwitch(GardenaBaseSwitch):
    """Representation of a Gardena Water Control switch."""

    def __init__(self, device):
        """Initialize the Gardena water control switch."""
        super().__init__(device)
        self._name = f"{device.name} Water Control"
        self._unique_id = f"{device.serial}-water_control"

    @property
    def is_on(self) -> bool:
        """Return true if watering is active."""
        return getattr(self._device, ATTR_ACTIVITY, "OFF") == "WATERING"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start watering."""
        duration = kwargs.get(
            "duration", DEFAULT_SMART_WATERING_DURATION * 60
        )  # Convert to seconds
        await self._device.start_watering(duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop watering."""
        await self._device.stop_watering()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the water control switch."""
        attributes = super().extra_state_attributes

        # Add watering specific attributes
        if hasattr(self._device, "watering_timer_1"):
            attributes["watering_timer_1"] = self._device.watering_timer_1
        if hasattr(self._device, "watering_timer_2"):
            attributes["watering_timer_2"] = self._device.watering_timer_2
        if hasattr(self._device, "watering_timer_3"):
            attributes["watering_timer_3"] = self._device.watering_timer_3
        if hasattr(self._device, "watering_timer_4"):
            attributes["watering_timer_4"] = self._device.watering_timer_4

        return attributes
