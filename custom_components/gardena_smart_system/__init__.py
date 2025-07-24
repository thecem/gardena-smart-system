"""Support for Gardena Smart System devices."""

import asyncio
import logging
import sys
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    GARDENA_LOCATION,
    GARDENA_SYSTEM,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema("gardena_smart_system")

# Ensure gardena module can be imported
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import gardena modules after path setup
from gardena.exceptions.authentication_exception import (
    AuthenticationException,
)

from .gardena.location import Location  # noqa: E402
from .gardena.smart_system import SmartSystem  # noqa: E402

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "valve", "binary_sensor", "lawn_mower"]


async def _check_and_cleanup_existing_sessions(hass: HomeAssistant) -> None:
    """Check for and cleanup any existing sessions or WebSocket connections."""
    _LOGGER.debug("Checking for existing Gardena sessions in Home Assistant")

    # Check if DOMAIN exists and has active sessions
    if DOMAIN in hass.data:
        domain_data = hass.data[DOMAIN]
        cleanup_performed = False

        # Check for existing SmartSystem instances
        for key, value in list(domain_data.items()):
            if isinstance(value, SmartSystem):
                _LOGGER.warning("Found existing SmartSystem session, cleaning up...")
                cleanup_performed = True
                try:
                    await value.quit()
                    _LOGGER.debug("Successfully cleaned up SmartSystem session")
                    # Remove from data
                    domain_data.pop(key, None)
                except Exception as ex:
                    _LOGGER.debug("Error during SmartSystem cleanup: %s", ex)

            # Check for GardenaSmartSystem instances
            elif hasattr(value, "smart_system") and hasattr(value, "stop"):
                _LOGGER.warning(
                    "Found existing GardenaSmartSystem session, cleaning up..."
                )
                cleanup_performed = True
                try:
                    await value.stop()
                    _LOGGER.debug("Successfully cleaned up GardenaSmartSystem session")
                    # Remove from data
                    domain_data.pop(key, None)
                except Exception as ex:
                    _LOGGER.debug("Error during GardenaSmartSystem cleanup: %s", ex)

        if cleanup_performed:
            # Additional wait to ensure sessions are fully terminated
            _LOGGER.debug("Waiting for session cleanup to complete...")
            await asyncio.sleep(8)  # Increased wait time
        else:
            _LOGGER.debug("No existing sessions found to cleanup")
    else:
        _LOGGER.debug("No domain data found")


async def _authenticate_with_retry(
    smart_system: SmartSystem, hass: HomeAssistant
) -> None:
    """Authenticate with retry logic for simultaneous logins."""
    max_retries = 3  # Reduced since we now have better cleanup
    base_wait_time = 15  # Reduced base wait time since cleanup is more thorough

    for attempt in range(max_retries):
        try:
            # For retry attempts, ensure clean state
            if attempt > 0:
                _LOGGER.debug("Cleaning up before retry attempt %d", attempt + 1)

                # Check for and cleanup any existing sessions first
                await _check_and_cleanup_existing_sessions(hass)

                # Force logout current session
                try:
                    await smart_system.quit()
                    _LOGGER.debug("Current SmartSystem session terminated")
                except Exception as ex:
                    _LOGGER.debug("Error during current session cleanup: %s", ex)

                # Progressive wait for API session cleanup
                cleanup_wait = 5 + (attempt * 5)  # 5s, 10s, 15s
                _LOGGER.debug(
                    "Waiting %d seconds for API session cleanup", cleanup_wait
                )
                await asyncio.sleep(cleanup_wait)

            _LOGGER.debug("Authentication attempt %d/%d", attempt + 1, max_retries)
            await smart_system.authenticate()
            _LOGGER.info("Authentication successful on attempt %d", attempt + 1)
            return

        except Exception as ex:
            error_msg = str(ex).lower()

            # Check for simultaneous login error specifically
            is_simultaneous_login = (
                "simultaneous logins detected" in error_msg
                or "simultaneous login" in error_msg
                or ("invalid_request" in error_msg and "client" in error_msg)
                or "already authenticated" in error_msg
                or "session already exists" in error_msg
            )

            if is_simultaneous_login and attempt < max_retries - 1:
                wait_time = base_wait_time + (attempt * 10)  # 15s, 25s, 35s
                _LOGGER.warning(
                    "Simultaneous login detected (attempt %d/%d). This indicates "
                    "an existing session is still active from this integration. "
                    "Performing thorough cleanup and waiting %d seconds...",
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                _LOGGER.info(
                    "Session conflict resolution:\n"
                    "1) Checking for other Home Assistant instances with this integration\n"
                    "2) Cleaning up any remaining WebSocket connections\n"
                    "3) Ensuring proper session termination on API server\n"
                    "Note: The official Gardena app uses different credentials and should not conflict"
                )
                await asyncio.sleep(wait_time)
                continue

            # For final attempt or non-login errors, provide helpful context
            if attempt == max_retries - 1:
                _LOGGER.exception(
                    "Authentication failed after %d attempts",
                    max_retries,
                )
                if is_simultaneous_login:
                    _LOGGER.warning("Session conflict persists. Possible causes:")
                    _LOGGER.warning(
                        "1. Another Home Assistant instance is running this integration"
                    )
                    _LOGGER.warning(
                        "2. Previous session cleanup did not complete properly"
                    )
                    _LOGGER.warning(
                        "3. WebSocket connection from previous session still active"
                    )
                    _LOGGER.warning(
                        "4. Manual restart of Home Assistant may be required"
                    )

            # Re-raise the original exception
            raise


# Create SSL context outside of event loop
# Remove the SSL context line


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Gardena Smart System component."""
    hass.data.setdefault(DOMAIN, {})

    # Defer service registration to avoid blocking startup
    async def _register_services_background():
        """Register integration services in background."""

        # Register mower control services
        async def start_mowing_service(call: ServiceCall) -> None:
            """Service to start mowing."""
            call.data.get("duration", 60)
            # Implementation depends on the specific mower entity
            # This would need to be implemented based on the actual device structure

        async def park_until_next_task_service(call: ServiceCall) -> None:
            """Service to park mower until next task."""
            # Implementation depends on the specific mower entity

        async def park_until_further_notice_service(call: ServiceCall) -> None:
            """Service to park mower until further notice."""
            # Implementation depends on the specific mower entity

        async def start_dont_override_service(call: ServiceCall) -> None:
            """Service to start automatic mode."""
            # Implementation depends on the specific mower entity

        # Register services
        hass.services.async_register(DOMAIN, "start_mowing", start_mowing_service)
        hass.services.async_register(
            DOMAIN, "park_until_next_task", park_until_next_task_service
        )
        hass.services.async_register(
            DOMAIN, "park_until_further_notice", park_until_further_notice_service
        )
        hass.services.async_register(
            DOMAIN, "start_dont_override", start_dont_override_service
        )

    # Register services in background to not block startup
    hass.async_create_task(
        _register_services_background(), name="gardena_services_setup"
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gardena Smart System from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create SmartSystem instance directly for initial setup
    smart_system = SmartSystem(
        client_id=entry.data["application_key"],
        client_secret=entry.data["application_secret"],
    )

    # Store in hass data immediately
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = smart_system

    # Create a background task for complete setup including platform forwarding
    async def _complete_setup_background():
        """Complete setup including authentication, device loading, and platform forwarding."""
        try:
            # Add timeout and retry logic for authentication
            await asyncio.wait_for(
                _authenticate_with_retry(smart_system, hass),
                timeout=120,  # 2 minutes total timeout
            )

            # After successful authentication, update locations
            await smart_system.update_locations()
            _LOGGER.debug(
                "Successfully loaded %d location(s)", len(smart_system.locations)
            )

            # Ensure we have at least one location
            if not smart_system.locations:
                _LOGGER.error("No locations found in your Gardena account")
                # Clean up and mark as failed
                hass.data[DOMAIN].pop(entry.entry_id, None)
                return

            # Load devices for each location
            for location in smart_system.locations.values():
                await smart_system.update_devices(location)
                _LOGGER.debug(
                    "Loaded %d devices for location %s",
                    len(location.devices),
                    location.name,
                )

            # Store location data for platforms to access
            first_location = next(iter(smart_system.locations.values()))
            hass.data[DOMAIN][GARDENA_LOCATION] = first_location

            _LOGGER.info("Gardena Smart System setup completed successfully")

            # Now forward entry setups to platforms with data available
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            _LOGGER.debug("Platforms setup completed successfully")

            # After successful platform setup, create and start the WebSocket wrapper
            gardena_system = GardenaSmartSystem(
                hass=hass,
                smart_system=smart_system,  # Pass the already authenticated instance
            )

            # Store the wrapper for WebSocket management
            hass.data[DOMAIN][f"{entry.entry_id}_websocket"] = gardena_system

            # Start WebSocket connection
            _LOGGER.info("Starting WebSocket connection for real-time updates")
            await gardena_system.start()
            _LOGGER.info("WebSocket connection setup completed")

        except Exception as ex:
            # Log the error and clean up
            _LOGGER.exception(
                "Failed to set up Gardena Smart System: %s", type(ex).__name__
            )
            # Clean up stored data on failure
            hass.data[DOMAIN].pop(entry.entry_id, None)
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN, None)

    # Start complete setup in background
    _LOGGER.debug("Starting Gardena Smart System complete setup in background")
    hass.async_create_task(
        _complete_setup_background(), name=f"gardena_complete_setup_{entry.entry_id}"
    )

    # Return True immediately to not block HA startup at all
    return True


async def _register_services(hass: HomeAssistant, gardena_system) -> None:
    """Register integration services."""

    async def websocket_diagnostics_service(call: ServiceCall):
        """Handle websocket diagnostics service call."""
        detailed = call.data.get("detailed", False)

        diagnostics = {
            "websocket_connected": gardena_system.is_websocket_connected,
            "websocket_task_status": gardena_system.websocket_task_status,
            "smart_system_status": gardena_system.smart_system.is_ws_connected
            if gardena_system.smart_system
            else False,
        }

        if detailed:
            diagnostics.update(
                {
                    "location_count": len(gardena_system.smart_system.locations)
                    if gardena_system.smart_system
                    else 0,
                    "device_count": sum(
                        len(loc.devices)
                        for loc in gardena_system.smart_system.locations.values()
                    )
                    if gardena_system.smart_system
                    else 0,
                    "has_active_task": gardena_system._ws_task is not None
                    and not gardena_system._ws_task.done(),
                    "shutdown_event_set": gardena_system._shutdown_event.is_set(),
                }
            )

        return diagnostics

    async def reload_service(call: ServiceCall) -> None:
        """Handle reload service call."""
        _LOGGER.info("Reload service called")
        # Find the config entry for this integration
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            _LOGGER.info("Reloading config entry: %s", config_entry.title)
            await hass.config_entries.async_reload(config_entry.entry_id)

    hass.services.async_register(
        DOMAIN,
        "websocket_diagnostics",
        websocket_diagnostics_service,
    )

    hass.services.async_register(DOMAIN, "reload", reload_service)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Gardena Smart System component")

    # Unload all platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Stop the SmartSystem and clean up resources properly
        smart_system = hass.data[DOMAIN].get(entry.entry_id)
        if smart_system:
            _LOGGER.debug("Stopping SmartSystem and cleaning up session")
            try:
                # Ensure proper logout to clean up API session
                await smart_system.quit()
                _LOGGER.debug("SmartSystem session cleaned up successfully")
                # Additional wait to ensure session is fully terminated on server side
                await asyncio.sleep(3)
            except Exception as ex:
                _LOGGER.warning("Error during SmartSystem cleanup: %s", ex)

        # Clean up legacy GardenaSmartSystem if it exists
        gardena_system = hass.data[DOMAIN].get(GARDENA_SYSTEM)
        if gardena_system:
            _LOGGER.debug("Stopping legacy GardenaSmartSystem")
            try:
                await gardena_system.stop()
                # Give a moment for the WebSocket to close properly
                _LOGGER.debug("Waiting for WebSocket connection to close...")
                await asyncio.sleep(2)
            except Exception as ex:
                _LOGGER.warning("Error during GardenaSmartSystem stop: %s", ex)

        # Unregister services if this is the last config entry
        remaining_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining_entries:
            _LOGGER.debug("Unregistering Gardena Smart System services")
            hass.services.async_remove(DOMAIN, "websocket_diagnostics")
            hass.services.async_remove(DOMAIN, "reload")

        # Clean up stored data
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(GARDENA_SYSTEM, None)
            hass.data[DOMAIN].pop(GARDENA_LOCATION, None)
            # If no more entries, remove the domain entirely
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN, None)

        _LOGGER.debug("Gardena Smart System component unloaded successfully")
    else:
        _LOGGER.error("Failed to unload Gardena Smart System platforms")

    return unload_ok


class GardenaSmartSystem:
    """A Gardena Smart System wrapper class."""

    def __init__(
        self, hass, smart_system=None, client_id=None, client_secret=None
    ) -> None:
        """Initialize the Gardena Smart System."""
        self._hass = hass
        self._ws_task = None
        self._shutdown_event = asyncio.Event()
        _LOGGER.debug("Initializing GardenaSmartSystem wrapper")

        # Use existing smart_system if provided, otherwise create new one
        if smart_system:
            self.smart_system = smart_system
        else:
            if not client_id or not client_secret:
                raise ValueError(
                    "Either smart_system or both client_id and client_secret must be provided"
                )
            self.smart_system = SmartSystem(
                client_id=client_id,
                client_secret=client_secret,
            )

    async def start(self) -> None:
        """Start WebSocket connection using existing authenticated smart_system."""
        try:
            _LOGGER.debug("Starting GardenaSmartSystem websocket connection")

            # Skip authentication since smart_system is already authenticated
            if not self.smart_system.locations:
                _LOGGER.error("No locations available for WebSocket connection")
                return

            # Use the first (and typically only) location
            location = next(iter(self.smart_system.locations.values()))
            _LOGGER.debug("Using location: %s (%s)", location.name, location.id)

            # Ensure hass.data[DOMAIN] is initialized
            if DOMAIN not in self._hass.data:
                self._hass.data[DOMAIN] = {}
            self._hass.data[DOMAIN][GARDENA_LOCATION] = location
            _LOGGER.debug("Starting GardenaSmartSystem websocket connection")

            # Start WebSocket with proper task management
            self._ws_task = asyncio.create_task(
                self._managed_websocket_connection(location), name="gardena_websocket"
            )
            # Add task exception handling
            self._ws_task.add_done_callback(self._websocket_task_done_callback)
            _LOGGER.debug("Websocket task created and launched with management")

        except Exception:
            _LOGGER.exception("Error during GardenaSmartSystem WebSocket start")
            raise

    async def _managed_websocket_connection(self, location: "Location") -> None:
        """Manage WebSocket connection with improved error handling and reconnection."""
        reconnect_delay = 5  # Initial delay in seconds
        max_reconnect_delay = 300  # Maximum delay (5 minutes)
        reconnect_attempts = 0

        while not self._shutdown_event.is_set():
            try:
                _LOGGER.debug("WebSocket connection attempt %d", reconnect_attempts + 1)
                await self.smart_system.start_ws(location)
                # If we get here, the WebSocket loop ended normally
                if self._shutdown_event.is_set():
                    _LOGGER.debug("WebSocket connection ended due to shutdown")
                    break
                _LOGGER.warning("WebSocket connection ended unexpectedly")

            except Exception:
                _LOGGER.exception("WebSocket connection error")
                reconnect_attempts += 1

            # Exponential backoff for reconnection
            if not self._shutdown_event.is_set():
                current_delay = min(
                    reconnect_delay * (2 ** min(reconnect_attempts - 1, 5)),
                    max_reconnect_delay,
                )
                _LOGGER.info(
                    "Reconnecting WebSocket in %d seconds (attempt %d)",
                    current_delay,
                    reconnect_attempts,
                )

                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=current_delay
                    )
                    break  # Shutdown was requested during wait
                except TimeoutError:
                    continue  # Continue with reconnection attempt

        _LOGGER.debug("WebSocket management task ending")

    def _websocket_task_done_callback(self, task: asyncio.Task) -> None:
        """Handle WebSocket task completion or failure."""
        if task.cancelled():
            _LOGGER.debug("WebSocket task was cancelled")
        elif task.exception():
            _LOGGER.error("WebSocket task failed with exception: %s", task.exception())
        else:
            _LOGGER.debug("WebSocket task completed normally")

    @property
    def is_websocket_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return (
            self._ws_task is not None
            and not self._ws_task.done()
            and self.smart_system.is_ws_connected
        )

    @property
    def websocket_task_status(self) -> str:
        """Get WebSocket task status for debugging."""
        if self._ws_task is None:
            return "not_started"
        if self._ws_task.cancelled():
            return "cancelled"
        if self._ws_task.done():
            if self._ws_task.exception():
                return f"failed: {self._ws_task.exception()}"
            return "completed"
        return "running"

    async def stop(self) -> None:
        """Stop the GardenaSmartSystem and clean up resources."""
        _LOGGER.debug("Stopping GardenaSmartSystem")

        # Signal shutdown to WebSocket management
        self._shutdown_event.set()

        # Cancel WebSocket task if running
        if self._ws_task and not self._ws_task.done():
            _LOGGER.debug("Cancelling WebSocket task")
            self._ws_task.cancel()
            try:
                await asyncio.wait_for(self._ws_task, timeout=10.0)
            except (TimeoutError, asyncio.CancelledError):
                _LOGGER.debug("WebSocket task cancelled/timed out")

        # Stop the underlying smart system
        await self.smart_system.quit()
        _LOGGER.debug("GardenaSmartSystem stopped")
