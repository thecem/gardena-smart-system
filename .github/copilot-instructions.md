# Gardena Smart System Integration - Copilot Instructions

## Architecture Overview

This is a **Home Assistant custom integration** for Gardena Smart System devices using OAuth2 authentication and WebSocket real-time updates. The architecture follows Home Assistant's entity-platform pattern with custom Gardena API client.

### Key Components

- **`custom_components/gardena_smart_system/`** - Main integration package
- **`gardena/`** - Internal API client library (embedded, not external dependency)
- **`smartsystem.py`** - Core API client with OAuth2 + WebSocket handling
- **Entity platforms**: `valve.py`, `sensor.py`, `lawn_mower.py`, `switch.py`, `binary_sensor.py`

### Data Flow Architecture

```
OAuth2 Auth → SmartSystem → Location → Devices → HA Entities
                     ↓
               WebSocket (real-time)
```

**Critical Pattern**: The integration uses `hass.data[DOMAIN][GARDENA_LOCATION]` as the central data store where `GARDENA_LOCATION` contains a `Location` object with all devices.

## Development Workflows

### Running & Debugging
```bash
# Start HA in debug mode (uses config/ directory)
scripts/develop

# Lint code (ruff format + check)
scripts/lint
```

**Key**: The `scripts/develop` sets `PYTHONPATH` to include `custom_components/` directory, allowing local development without symlinking.

### Project-Specific Patterns

#### 1. Entity Setup Pattern
All platforms use this pattern in `async_setup_entry()`:
```python
entities = []
for device in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("DEVICE_TYPE"):
    entities.append(EntityClass(device, config_entry.options))
```

#### 2. WebSocket Session Management
**Critical**: The integration has sophisticated session cleanup to prevent "Simultaneous logins detected" errors:
- `_check_and_cleanup_existing_sessions()` in `__init__.py`
- Always reuse authenticated sessions via `GardenaSmartSystem` wrapper
- WebSocket connections are managed centrally in `SmartSystem` class

#### 3. Device Update Callbacks
Devices use callback pattern for real-time updates:
```python
device.add_callback(entity.update_callback)
```

#### 4. Rate Limiting & Backoff
API calls use `@backoff` decorators with exponential backoff (`MAX_BACKOFF_VALUE = 900`). All HTTP calls go through `SmartSystem.create_header()` with proper authentication.

## Integration Points

### OAuth2 Flow
- Uses `authlib` for OAuth2 with Husqvarna API
- `TokenManager` handles token refresh automatically
- Authentication host: `api.authentication.husqvarnagroup.dev`
- API host: `api.smart.gardena.dev`

### WebSocket Real-Time Updates
- Established after OAuth2 authentication
- Handles device state changes within seconds
- Automatic reconnection on connection loss
- Uses `websockets` library, not Home Assistant's WebSocket

### Device Types & Services
- **VALVE**: Water control, smart irrigation (with duration configuration)
- **MOWER**: Robotic mowers with scheduling
- **SENSOR**: Environmental sensors, soil sensors
- **POWER_SOCKET**: Smart outlets
- **Binary sensors**: Connectivity, error states

## Configuration

### manifest.json Dependencies
```json
"requirements": [
    "oauthlib==3.2.2", "authlib>=1.2.0", "httpx>=0.24.0",
    "websockets", "backoff>=2.0.0"
]
```

### Config Flow
Uses `CONFIG_SCHEMA` with `application_key` and `application_secret` from Gardena Developer Portal. Options include duration settings for different device types.

## Error Handling Patterns

### Simultaneous Login Prevention
The integration has sophisticated logic to detect and cleanup existing sessions. Always check `__init__.py` session cleanup code when debugging authentication issues.

### Pending State Protection
Valve entities use `PENDING_STATE_TIMEOUT_SECONDS = 10` to prevent conflicts during user actions.

## Common Debugging Scenarios

### "Simultaneous logins detected" Error
**Symptoms**: Integration fails to authenticate, logs show simultaneous login errors
**Root Cause**: Multiple SmartSystem instances or lingering WebSocket connections
**Debug Steps**:
1. Check `_check_and_cleanup_existing_sessions()` in `__init__.py`
2. Look for existing sessions in `hass.data[DOMAIN]`
3. Verify WebSocket cleanup in SmartSystem destructor
4. Restart Home Assistant if cleanup fails

### WebSocket Connection Issues
**Symptoms**: Device states not updating in real-time, WebSocket connection errors
**Debug Steps**:
1. Enable debug logging: `custom_components.gardena_smart_system: debug`
2. Check `SmartSystem.start_ws()` connection establishment
3. Monitor WebSocket task lifecycle in `_handle_ws_messages()`
4. Verify SSL context configuration in `smart_system.py`

### Valve State Synchronization Problems
**Symptoms**: Valve shows wrong state, commands don't reflect immediately
**Debug Steps**:
1. Check pending state protection in `valve.py` (10-second window)
2. Verify callback registration: `device.add_callback(entity.update_callback)`
3. Monitor WebSocket messages for valve state changes
4. Check duration timer updates in `_async_timer_update()`

### Authentication Token Refresh Failures
**Symptoms**: Integration stops working after period of time, 401/403 errors
**Debug Steps**:
1. Check `TokenManager` token refresh logic
2. Verify OAuth2 client configuration in `SmartSystem`
3. Monitor token expiration handling
4. Check rate limiting backoff in API calls

## Key Files for Understanding

- **`__init__.py`**: Session management, service registration, cleanup logic
- **`gardena/smart_system.py`**: Core API client, WebSocket, authentication
- **`valve.py`**: Shows entity pattern with real-time updates and state management
- **`const.py`**: All domain constants, default durations, rate limiting settings
- **`config_flow.py`**: Configuration UI and validation patterns

## Device-Specific Entity Patterns

### Valve Entities (Water Control & Smart Irrigation)
**Duration Configuration**: Each valve type has configurable default durations from config options:
```python
@property
def option_smart_watering_duration(self) -> int:
    return self._options.get(CONF_SMART_WATERING_DURATION, DEFAULT_SMART_WATERING_DURATION)
```

**Real-time Timer Updates**: Valves show live countdown during operation:
```python
async def _async_timer_update(self, now) -> None:
    """Update remaining time for active valves."""
    if self.is_on and self._remaining_time > 0:
        self._remaining_time = max(0, self._remaining_time - 1)
        self.async_write_ha_state()
```

**Pending State Protection**: Prevents conflicts during user actions:
```python
if self._last_state_change and (datetime.now(UTC) - self._last_state_change).total_seconds() < PENDING_STATE_TIMEOUT_SECONDS:
    return  # Skip state updates during pending window
```

### Mower Entities
**Activity State Mapping**: Mowers have complex state mapping from Gardena API:
```python
@property
def state(self):
    if self._activity == "PAUSED": return "paused"
    elif self._activity == "OK_CUTTING": return "mowing"
    elif self._activity == "PARKED_TIMER": return "docked"
```

**Service Integration**: Mowers expose Home Assistant services for control:
- `start_mowing_service()` - Duration-based mowing
- `park_until_next_task_service()` - Scheduled parking
- `park_until_further_notice_service()` - Manual parking

### Sensor Entities
**Multi-type Support**: Single platform handles multiple sensor types:
```python
# Environmental sensors (temperature, humidity, light)
for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("SENSOR"):
    if hasattr(sensor, 'temperature'):
        entities.append(GardenaSmartSensorTemperature(sensor))

# Soil sensors (moisture, temperature)
for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("SOIL_SENSOR"):
    entities.append(GardenaSmartSoilTemperature(sensor))
```

## WebSocket Message Handling

### Connection Establishment
WebSocket connects after OAuth2 authentication using secure WebSocket:
```python
async def start_ws(self) -> None:
    """Start WebSocket connection for real-time updates."""
    if not self.token_manager.access_token:
        await self.authenticate()

    ws_url = f"wss://api.smart.gardena.dev/v1/websocket?access_token={self.token_manager.access_token}"
    self.ws = await connect(ws_url, ssl=self._ssl_context)
    self.is_ws_connected = True
```

### Message Processing Pattern
WebSocket messages trigger device updates via callback system:
```python
async def _handle_ws_messages(self) -> None:
    """Process incoming WebSocket messages."""
    async for message in self.ws:
        try:
            data = json.loads(message)
            if data.get("type") == "LOCATION":
                # Update device data
                location = self.locations[data["id"]]
                location.update_devices(data)
                # Callbacks automatically notify HA entities
        except JSONDecodeError:
            self.logger.error("Invalid WebSocket message format")
```

### Real-time State Updates
Device callbacks trigger immediate Home Assistant state updates:
```python
def update_callback(self, device) -> None:
    """Called when device receives WebSocket update."""
    if self._device.id == device.id:
        # Update entity state from device data
        self._state = device.activity
        self._remaining_time = device.remaining_time
        # Immediately update HA state
        self.async_write_ha_state()
```

### WebSocket Error Handling & Reconnection
Automatic reconnection on connection loss:
```python
except ConnectionClosed:
    self.logger.warning("WebSocket connection closed, attempting reconnection")
    self.is_ws_connected = False
    await asyncio.sleep(5)  # Brief delay before reconnect
    if not self.should_stop:
        await self.start_ws()  # Automatic reconnection
```
