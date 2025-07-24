"""Configuration flow for Gardena Smart System."""

import asyncio
import logging
from collections import OrderedDict

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_MOWER_DURATION,
    CONF_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING_DURATION,
    DEFAULT_MOWER_DURATION,
    DEFAULT_SMART_IRRIGATION_DURATION,
    DEFAULT_SMART_WATERING_DURATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("application_key"): str,
        vol.Required("application_secret"): str,
    }
)

DEFAULT_OPTIONS = {
    CONF_MOWER_DURATION: DEFAULT_MOWER_DURATION,
    CONF_SMART_IRRIGATION_DURATION: DEFAULT_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING_DURATION: DEFAULT_SMART_WATERING_DURATION,
}


class GardenaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gardena Smart System."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        errors = errors or {}

        fields = OrderedDict()
        fields[vol.Required("application_key")] = str
        fields[vol.Required("application_secret")] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the configuration
                await self._test_credentials(user_input)
                return self.async_create_entry(
                    title="Gardena Smart System",
                    data=user_input,
                )
            except Exception as ex:
                _LOGGER.exception("Failed to validate credentials")
                error_msg = str(ex).lower()

                if "invalid_client" in error_msg or "client not found" in error_msg:
                    errors["application_key"] = "invalid_application_key"
                elif "invalid_grant" in error_msg:
                    errors["application_secret"] = "invalid_application_secret"
                elif "access_denied" in error_msg:
                    errors["base"] = "access_denied"
                elif "timeout" in error_msg:
                    errors["base"] = "timeout"
                elif "simultaneous logins detected" in error_msg:
                    errors["base"] = "simultaneous_logins"
                elif "invalid_request" in error_msg:
                    errors["base"] = "invalid_request"
                else:
                    errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://developer.husqvarnagroup.cloud/",
            },
        )

    async def _test_credentials(self, config: dict) -> bool:
        """Test if credentials are valid with retry logic for simultaneous logins."""
        from .gardena.smart_system import SmartSystem

        smart_system = SmartSystem(
            client_id=config["application_key"],
            client_secret=config["application_secret"],
        )

        # Try multiple times with increasing delays for simultaneous login errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # For retry attempts, completely reset the authentication state
                if attempt > 0:
                    await smart_system.quit()  # Clean up any existing state

                await smart_system.authenticate()
                await smart_system.quit()
                return True
            except Exception as ex:
                error_msg = str(ex).lower()

                # If it's a simultaneous login error, wait and retry
                if (
                    "simultaneous logins detected" in error_msg
                    and attempt < max_retries - 1
                ):
                    _LOGGER.warning(
                        "Simultaneous login detected, waiting %d seconds before retry %d/%d",
                        (attempt + 1) * 10,
                        attempt + 2,
                        max_retries,
                    )
                    await asyncio.sleep((attempt + 1) * 10)  # Wait 10, 20, 30 seconds
                    continue

                # For other errors or final retry, re-raise
                _LOGGER.exception("Authentication test failed")
                raise

        # Should never reach here due to exception re-raising
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GardenaSmartSystemOptionsFlowHandler(config_entry)


class GardenaSmartSystemOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        """Initialize Gardena Smart System options flow."""
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # TODO: Validate options (min, max values)
            return self.async_create_entry(title="", data=user_input)

        fields = OrderedDict()
        fields[
            vol.Optional(
                CONF_MOWER_DURATION,
                default=self.config_entry.options.get(
                    CONF_MOWER_DURATION, DEFAULT_MOWER_DURATION
                ),
            )
        ] = cv.positive_int
        fields[
            vol.Optional(
                CONF_SMART_IRRIGATION_DURATION,
                default=self.config_entry.options.get(
                    CONF_SMART_IRRIGATION_DURATION, DEFAULT_SMART_IRRIGATION_DURATION
                ),
            )
        ] = cv.positive_int
        fields[
            vol.Optional(
                CONF_SMART_WATERING_DURATION,
                default=self.config_entry.options.get(
                    CONF_SMART_WATERING_DURATION, DEFAULT_SMART_WATERING_DURATION
                ),
            )
        ] = cv.positive_int

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )


async def try_connection(client_id, client_secret) -> None:
    _LOGGER.debug("Trying to connect to Gardena during setup")
    # Import here to avoid circular imports at module level
    from .gardena.exceptions.authentication_exception import AuthenticationException
    from .gardena.smart_system import SmartSystem

    smart_system = SmartSystem(client_id=client_id, client_secret=client_secret)
    try:
        await smart_system.authenticate()
        await smart_system.update_locations()
        await smart_system.quit()
        _LOGGER.debug("Successfully connected to Gardena during setup")
    except AuthenticationException as auth_ex:
        _LOGGER.exception("Authentication failed during setup: %s", auth_ex)
        raise
    except Exception as ex:
        error_msg = str(ex).lower()
        _LOGGER.exception("Connection test failed: %s", ex)

        # Handle specific error types
        if "rate limit" in error_msg or "429" in error_msg:
            msg = "Rate limit exceeded. Please wait and try again."
            raise ConnectionError(msg) from ex
        if "simultaneous logins" in error_msg:
            msg = "Multiple logins detected. Close other Gardena apps and try again."
            raise ConnectionError(msg) from ex
        if (
            "403" in error_msg
            or "forbidden" in error_msg
            or "not authorized" in error_msg
        ):
            msg = "Access forbidden. Check your API application configuration."
            raise ConnectionError(msg) from ex
        if "invalid_client" in error_msg or "client secret is invalid" in error_msg:
            msg = "Invalid Client ID or Client Secret"
            raise AuthenticationException(msg) from ex
        if "timeout" in error_msg:
            msg = "Connection timeout. Check your internet connection."
            raise ConnectionError(msg) from ex

        # Re-raise as ConnectionError for generic issues
        msg = f"Failed to connect to Gardena API: {ex}"
        raise ConnectionError(msg) from ex
