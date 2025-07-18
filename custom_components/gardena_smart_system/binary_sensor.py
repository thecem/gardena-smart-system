"""Support for Gardena Smart System websocket connection status."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from custom_components.gardena_smart_system import GARDENA_SYSTEM

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Gardena websocket connection status."""
    async_add_entities(
        [SmartSystemWebsocketStatus(hass.data[DOMAIN][GARDENA_SYSTEM].smart_system)],
        True,
    )


class SmartSystemWebsocketStatus(BinarySensorEntity):
    """Representation of Gardena Smart System websocket connection status."""

    def __init__(self, smart_system) -> None:
        """Initialize the binary sensor."""
        super().__init__()
        self._unique_id = "smart_gardena_websocket_status"
        self._name = "Gardena Smart System connection"
        self._smart_system = smart_system

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._smart_system.add_ws_status_callback(self.update_callback)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._smart_system.is_ws_connected

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    def update_callback(self, status):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.CONNECTIVITY


"""Binary sensor platform for Gardena Smart System."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Smart System binary sensor entities."""
    _LOGGER.debug("Setting up Gardena Smart System binary sensor entities")

    entities = []

    # Mower connectivity sensors
    for mower in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("MOWER"):
        entities.append(GardenaConnectivitySensor(mower))

    # Smart irrigation control connectivity sensors
    for irrigation_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "SMART_IRRIGATION_CONTROL"
    ):
        entities.append(GardenaConnectivitySensor(irrigation_control))

    # Power socket connectivity sensors
    for power_socket in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "POWER_SOCKET"
    ):
        entities.append(GardenaConnectivitySensor(power_socket))

    # Sensor connectivity sensors
    for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("SENSOR"):
        entities.append(GardenaConnectivitySensor(sensor))

    # Water control connectivity sensors
    for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "WATER_CONTROL"
    ):
        entities.append(GardenaConnectivitySensor(water_control))

    _LOGGER.debug("Adding %d binary sensor entities", len(entities))
    async_add_entities(entities, True)


class GardenaBaseBinarySensor(BinarySensorEntity):
    """Base class for Gardena binary sensors."""

    def __init__(self, device, sensor_type):
        """Initialize the Gardena binary sensor."""
        self._device = device
        self._sensor_type = sensor_type

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for binary sensors."""
        return False

    def update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if the device is connected."""
        return getattr(self._device, ATTR_RF_LINK_STATE, "OFFLINE") == "ONLINE"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the binary sensor."""
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            name=self._device.name,
            manufacturer="Gardena",
            model=self._device.model_type,
        )


class GardenaConnectivitySensor(GardenaBaseBinarySensor):
    """Representation of a Gardena connectivity sensor."""

    def __init__(self, device):
        """Initialize the Gardena connectivity sensor."""
        super().__init__(device, "connectivity")
        self._name = f"{device.name} connectivity"
        self._unique_id = f"{device.serial}-connectivity"

    @property
    def device_class(self):
        """Return the device class."""
        return "connectivity"
