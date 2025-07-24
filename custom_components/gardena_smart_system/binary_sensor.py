"""Binary sensor platform for Gardena Smart System."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    DOMAIN,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    _config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    entities = []

    # Get the location from hass data
    location = hass.data[DOMAIN][GARDENA_LOCATION]

    # Add websocket status sensor using the location's smart_system
    entities.append(SmartSystemWebsocketStatus(location.smart_system))

    # Add connectivity sensors for all device types
    for device_type in [
        "MOWER",
        "SMART_IRRIGATION_CONTROL",
        "POWER_SOCKET",
        "SENSOR",
        "WATER_CONTROL",
    ]:
        for device in location.find_device_by_type(device_type):
            entities.append(GardenaConnectivitySensor(device))

    async_add_entities(entities, update_before_add=True)


class SmartSystemWebsocketStatus(BinarySensorEntity):
    """Representation of Gardena Smart System websocket connection status."""

    def __init__(self, smart_system: Any) -> None:
        """Initialize the websocket status sensor."""
        self._smart_system = smart_system
        self._attr_name = "Gardena Smart System Websocket"
        self._attr_unique_id = "gardena_smart_system_websocket_status"

    @property
    def is_on(self) -> bool:
        """Return true if the websocket is connected."""
        return self._smart_system.is_ws_connected

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return BinarySensorDeviceClass.CONNECTIVITY


class GardenaConnectivitySensor(BinarySensorEntity):
    """Representation of a Gardena device connectivity sensor."""

    def __init__(self, device: Any) -> None:
        """Initialize the connectivity sensor."""
        self._device = device
        self._attr_name = f"{device.name} Connectivity"
        self._attr_unique_id = f"{device.serial}_connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return getattr(self._device, ATTR_RF_LINK_STATE, "OFFLINE") == "ONLINE"

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        attributes = {}

        # Add battery state if available
        if hasattr(self._device, ATTR_BATTERY_STATE):
            attributes[ATTR_BATTERY_STATE] = getattr(self._device, ATTR_BATTERY_STATE)

        # Add RF link level if available
        if hasattr(self._device, ATTR_RF_LINK_LEVEL):
            attributes[ATTR_RF_LINK_LEVEL] = getattr(self._device, ATTR_RF_LINK_LEVEL)

        # Add RF link state if available
        if hasattr(self._device, ATTR_RF_LINK_STATE):
            attributes[ATTR_RF_LINK_STATE] = getattr(self._device, ATTR_RF_LINK_STATE)

        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            name=self._device.name,
            manufacturer="Gardena",
            model=getattr(self._device, "model_type", "Unknown"),
        )

    def update_callback(self) -> None:
        """Update the sensor state."""
        self.schedule_update_ha_state(force_refresh=True)
