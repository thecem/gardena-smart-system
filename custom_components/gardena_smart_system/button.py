"""Button platform for Gardena Smart System."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Smart System buttons."""
    _LOGGER.debug("Setting up Gardena Smart System buttons")
    # Placeholder for now
