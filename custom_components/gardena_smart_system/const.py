"""Constants for the Gardena Smart System integration."""

DOMAIN = "gardena_smart_system"
GARDENA_SYSTEM = "gardena_system"
GARDENA_LOCATION = "gardena_location"

# Additional constants for sensors
ATTR_BATTERY_STATE = "battery_state"
ATTR_RF_LINK_LEVEL = "rf_link_level"
ATTR_RF_LINK_STATE = "rf_link_state"

CONF_MOWER_DURATION = "mower_duration"
CONF_SMART_IRRIGATION_DURATION = "smart_irrigation_control_duration"
CONF_SMART_WATERING_DURATION = "smart_watering_duration"

DEFAULT_MOWER_DURATION = 60
DEFAULT_SMART_IRRIGATION_DURATION = 30
DEFAULT_SMART_WATERING_DURATION = 30

ATTR_NAME = "name"
ATTR_ACTIVITY = "activity"
ATTR_SERIAL = "serial"
ATTR_OPERATING_HOURS = "operating_hours"
ATTR_LAST_ERROR = "last_error"
ATTR_ERROR = "error"
ATTR_STATE = "state"
ATTR_STINT_START = "stint_start"
ATTR_STINT_END = "stint_end"

# Add constants for rate limiting
HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_FOUND = 404
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

# Default delays for rate limiting
DEFAULT_API_DELAY = 1.0  # Minimum delay between API calls
RATE_LIMIT_DELAY = 60  # Delay when rate limited
