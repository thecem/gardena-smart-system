"""Switch platform for Gardena Smart System."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_SMART_WATERING_DURATION,
    DOMAIN,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Smart System switches."""
    entities = []

    # Power socket switches
    entities.extend(
        GardenaPowerSocketSwitch(power_socket)
        for power_socket in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
            "POWER_SOCKET"
        )
    )

    # Water control switches
    entities.extend(
        GardenaWaterControlSwitch(water_control)
        for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
            "WATER_CONTROL"
        )
    )

    _LOGGER.debug("Adding %d switch entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class GardenaBaseSwitch(SwitchEntity):
    """Base class for Gardena switches."""

    def __init__(self, device: Any) -> None:
        """Initialize the Gardena switch."""
        self._device = device
        self._name = self._device.name
        self._device.add_update_callback(self.update_callback)
        self._attr_unique_id = f"{self._device.id}_{self._device.type}"

    @property
    def should_poll(self) -> bool:
        """Return true if the device should be polled for updates."""
        return False

    def update_callback(self, device: Any) -> None:
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(force_refresh=True)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._device.state != "UNAVAILABLE"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self._device.name,
            manufacturer="Gardena",
            model=self._device.type,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch."""
        attributes = {}

        if hasattr(self._device, "battery_level"):
            attributes["battery_level"] = self._device.battery_level
        if hasattr(self._device, "battery_state"):
            attributes["battery_state"] = self._device.battery_state
        if hasattr(self._device, "radio_quality"):
            attributes["radio_quality"] = self._device.radio_quality
        if hasattr(self._device, "radio_state"):
            attributes["radio_state"] = self._device.radio_state
        if hasattr(self._device, "activity"):
            attributes["activity"] = self._device.activity
        if hasattr(self._device, "state"):
            attributes["device_state"] = self._device.state

        return attributes


class GardenaPowerSocketSwitch(GardenaBaseSwitch):
    """Representation of a Gardena Power Socket switch."""

    def __init__(self, device: Any) -> None:
        """Initialize the Gardena power socket switch."""
        super().__init__(device)

    @property
    def is_on(self) -> bool:
        """Return true if the power socket is on."""
        return getattr(self._device, "activity", "OFF") == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the power socket on."""
        duration = kwargs.get("duration", DEFAULT_SMART_WATERING_DURATION)
        await self._device.start_override(duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the power socket off."""
        await self._device.stop_override()


class GardenaWaterControlSwitch(GardenaBaseSwitch):
    """Representation of a Gardena Water Control switch."""

    def __init__(self, device: Any) -> None:
        """Initialize the Gardena water control switch."""
        super().__init__(device)

    @property
    def is_on(self) -> bool:
        """Return true if the water control is watering."""
        return getattr(self._device, "valve_activity", "CLOSED") in [
            "MANUAL_WATERING",
            "SCHEDULED_WATERING",
        ]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start watering."""
        duration = kwargs.get("duration", DEFAULT_SMART_WATERING_DURATION)
        await self._device.start_watering(duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop watering."""
        await self._device.stop_watering()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the water control switch."""
        attributes = super().extra_state_attributes

        if hasattr(self._device, "valve_activity"):
            attributes["valve_activity"] = self._device.valve_activity
        if hasattr(self._device, "valve_state"):
            attributes["valve_state"] = self._device.valve_state

        return attributes
