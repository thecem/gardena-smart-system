"""Support for Gardena Smart System sensors."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, UnitOfTemperature
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    PERCENTAGE,
    UnitOfTime,
)
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    DOMAIN,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)

SOIL_SENSOR_TYPES = {
    "soil_temperature": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
    ],
    "soil_humidity": ["%", "mdi:water-percent", SensorDeviceClass.HUMIDITY],
    ATTR_BATTERY_LEVEL: [PERCENTAGE, "mdi:battery", SensorDeviceClass.BATTERY],
}

SENSOR_TYPES = {
    "ambient_temperature": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
    ],
    "light_intensity": ["lx", None, SensorDeviceClass.ILLUMINANCE],
    **SOIL_SENSOR_TYPES,
}

# Duration sensor types for different device operations
DURATION_SENSOR_TYPES = {
    "override_duration": [UnitOfTime.SECONDS, "mdi:timer", SensorDeviceClass.DURATION],
    "override_remaining_time": [
        UnitOfTime.SECONDS,
        "mdi:timer-sand",
        SensorDeviceClass.DURATION,
    ],
    "valve_duration": [UnitOfTime.SECONDS, "mdi:timer", SensorDeviceClass.DURATION],
    "valve_remaining_time": [
        UnitOfTime.SECONDS,
        "mdi:timer-sand",
        SensorDeviceClass.DURATION,
    ],
    "mowing_duration": [UnitOfTime.SECONDS, "mdi:timer", SensorDeviceClass.DURATION],
    "mowing_remaining_time": [
        UnitOfTime.SECONDS,
        "mdi:timer-sand",
        SensorDeviceClass.DURATION,
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Perform the setup for Gardena sensor devices."""
    entities = []

    # Regular sensors
    entities.extend(
        [
            GardenaSensor(sensor, sensor_type)
            for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
                "SENSOR"
            )
            for sensor_type in SENSOR_TYPES
        ]
    )

    # Soil sensors
    entities.extend(
        [
            GardenaSensor(sensor, sensor_type)
            for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
                "SOIL_SENSOR"
            )
            for sensor_type in SOIL_SENSOR_TYPES
        ]
    )

    # Mower sensors (battery + duration)
    for mower in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("MOWER"):
        entities.append(GardenaSensor(mower, ATTR_BATTERY_LEVEL))
        # Add duration sensors for mowing operations
        entities.extend(
            [
                GardenaDurationSensor(mower, duration_type)
                for duration_type in ["mowing_duration", "mowing_remaining_time"]
                if hasattr(mower, duration_type)
                and getattr(mower, duration_type) != "N/A"
            ]
        )

    # Water control sensors (battery only)
    for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "WATER_CONTROL"
    ):
        entities.append(GardenaSensor(water_control, ATTR_BATTERY_LEVEL))

    # Smart irrigation control sensors - no automatic duration sensors
    # Duration data is available in valve entity attributes instead

    # Power socket duration sensors
    for power_socket in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type(
        "POWER_SOCKET"
    ):
        entities.extend(
            [
                GardenaDurationSensor(power_socket, duration_type)
                for duration_type in ["override_duration", "override_remaining_time"]
                if hasattr(power_socket, duration_type)
                and getattr(power_socket, duration_type) != "N/A"
            ]
        )

    _LOGGER.debug("Adding sensor as sensor %s", entities)
    async_add_entities(entities, update_before_add=True)


class GardenaDurationSensor(Entity):
    """Representation of a Gardena Duration Sensor for timed operations."""

    def __init__(self, device, sensor_type) -> None:
        """Initialize the Gardena Duration Sensor."""
        self._sensor_type = sensor_type
        self._name = f"{device.name} {sensor_type.replace('_', ' ')}"
        self._unique_id = f"{device.serial}-{sensor_type}"
        self._device = device

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensor events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    def update_callback(self, device) -> None:
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return DURATION_SENSOR_TYPES[self._sensor_type][1]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return DURATION_SENSOR_TYPES[self._sensor_type][0]

    @property
    def device_class(self):
        """Return the device class of this entity."""
        if self._sensor_type in DURATION_SENSOR_TYPES:
            return DURATION_SENSOR_TYPES[self._sensor_type][2]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        value = getattr(self._device, self._sensor_type, "N/A")
        # Don't show N/A values in Home Assistant
        return None if value == "N/A" else value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
        }

        # Add duration-specific timestamp if available
        if "duration" in self._sensor_type:
            timestamp_attr = self._sensor_type.replace("duration", "duration_timestamp")
            if hasattr(self._device, timestamp_attr):
                timestamp_value = getattr(self._device, timestamp_attr)
                if timestamp_value != "N/A":
                    attributes["timestamp"] = timestamp_value

        return attributes

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }


class GardenaSensor(Entity):
    """Representation of a Gardena Sensor."""

    def __init__(self, device, sensor_type) -> None:
        """Initialize the Gardena Sensor."""
        self._sensor_type = sensor_type
        self._name = f"{device.name} {sensor_type.replace('_', ' ')}"
        self._unique_id = f"{device.serial}-{sensor_type}"
        self._device = device

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensor events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    def update_callback(self, device) -> None:
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor_type][0]

    @property
    def device_class(self):
        """Return the device class of this entity."""
        if self._sensor_type in SENSOR_TYPES:
            return SENSOR_TYPES[self._sensor_type][2]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self._device, self._sensor_type)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
        }

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }
