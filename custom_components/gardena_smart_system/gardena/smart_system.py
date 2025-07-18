import asyncio
import functools
import json
import logging
import ssl
from json.decoder import JSONDecodeError

import backoff
import httpx
from authlib.integrations.base_client.errors import InvalidTokenError, OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import ConnectError, ConnectTimeout, HTTPStatusError, TimeoutException
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .devices.device_factory import DeviceFactory
from .exceptions.authentication_exception import AuthenticationException
from .location import Location
from .token_manager import TokenManager

MAX_BACKOFF_VALUE = 900
DEFAULT_TIMEOUT = 30.0  # 30 seconds default timeout
CONNECTION_TIMEOUT = 15.0  # 15 seconds for connection
READ_TIMEOUT = 30.0  # 30 seconds for reading response


class RateLimitException(Exception):
    """Exception raised when API rate limit is reached."""



@functools.lru_cache(maxsize=1)
def get_ssl_context():
    """Create and cache SSL context outside of event loop."""
    context = ssl.create_default_context()
    return context


class SmartSystem:
    """Base class to communicate with gardena and handle network calls"""

    def __init__(
        self, client_id=None, client_secret=None, level=logging.INFO, ssl_context=None
    ):
        """Constructor, create instance of gateway"""
        if client_id is None or client_secret is None:
            raise ValueError(
                "Arguments 'email', 'client_secret' and 'client_id' are required"
            )
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)
        self.AUTHENTICATION_HOST = "https://api.authentication.husqvarnagroup.dev"
        self.SMART_HOST = "https://api.smart.gardena.dev"
        self.client_id = client_id
        self.client_secret = client_secret
        self.locations = {}
        self.level = level
        self.client: AsyncOAuth2Client = None
        self.token_manager = TokenManager(logger=self.logger)
        self.ws = None
        self.is_ws_connected = False
        self.ws_status_callback = None
        self.should_stop = False
        self.supported_services = [
            "COMMON",
            "VALVE",
            "VALVE_SET",
            "SENSOR",
            "MOWER",
            "POWER_SOCKET",
            "DEVICE",
        ]
        # Use provided SSL context or get cached one
        self._ssl_context = ssl_context or get_ssl_context()

        # Rate limiting and backoff settings
        self.connection_attempts = 0
        self.max_backoff = MAX_BACKOFF_VALUE
        self.base_delay = 5

    def create_header(self, include_json=False):
        headers = {"Authorization-Provider": "husqvarna", "X-Api-Key": self.client_id}
        if include_json:
            headers["Content-Type"] = "application/vnd.api+json"
        return headers

    async def authenticate(self):
        """
        Authenticate and get tokens.

        This function needs to be called first.
        """
        url = self.AUTHENTICATION_HOST + "/v1/oauth2/token"
        extra = {"client_id": self.client_id}

        # Create timeout configuration using httpx.Timeout
        timeout_config = httpx.Timeout(
            connect=CONNECTION_TIMEOUT,
            read=READ_TIMEOUT,
            write=DEFAULT_TIMEOUT,
            pool=DEFAULT_TIMEOUT,
        )

        self.client = AsyncOAuth2Client(
            self.client_id,
            self.client_secret,
            update_token=self.token_saver,
            grant_type="client_credentials",
            token_endpoint=url,
            verify=self._ssl_context,  # Pass SSL context to httpx client
            timeout=timeout_config,  # Add timeout configuration
        )

        try:
            self.logger.debug("Attempting authentication with Gardena API...")
            token = await self.client.fetch_token(url, grant_type="client_credentials")
            self.token_manager.load_from_oauth2_token(token)
            self.logger.debug("Authentication successful, updating locations...")
        except (ConnectTimeout, ConnectError, TimeoutException) as ex:
            self.logger.error("Connection timeout during authentication: %s", ex)
            raise ConnectionError(
                f"Authentication failed due to connection timeout: {ex}"
            ) from ex
        except Exception as ex:
            self.logger.error("Authentication failed: %s", ex)
            raise

    async def quit(self):
        self.should_stop = True
        if self.client:
            if self.token_manager.access_token:
                await self.client.post(
                    f"{self.AUTHENTICATION_HOST}/v1/oauth2/revoke",
                    headers={
                        "Authorization": "Bearer " + self.token_manager.access_token
                    },
                    data={"token": self.token_manager.access_token},
                )

    async def token_saver(self, token, refresh_token=None, access_token=None):
        self.token_manager.load_from_oauth2_token(token)

    async def call_smart_system_service(self, service_id, data):
        """Call Gardena Smart System service with improved error handling."""
        args = {"data": data}
        headers = self.create_header(True)

        try:
            self.logger.debug("Calling service %s with data: %s", service_id, data)
            r = await self.client.put(
                f"{self.SMART_HOST}/v2/command/{service_id}",
                headers=headers,
                data=json.dumps(args, ensure_ascii=False),
            )
            if r.status_code != 202:
                response = r.json()
                error_msg = f"{r.status_code} : {response['errors'][0]['title']}"
                self.logger.error("Service call failed: %s", error_msg)
                raise ConnectionError(error_msg)
        except (ConnectTimeout, ConnectError, TimeoutException) as ex:
            self.logger.error(
                "Connection timeout during service call to %s: %s", service_id, ex
            )
            raise ConnectionError(
                f"Service call failed due to connection timeout: {ex}"
            ) from ex
        except Exception as ex:
            self.logger.error(
                "Unexpected error during service call to %s: %s", service_id, ex
            )
            raise

    def __response_has_errors(self, response):
        if response.status_code not in (200, 202):
            try:
                r = response.json()
                if "errors" in r:
                    msg = f"{r['errors'][0]['title']} - {r['errors'][0]['detail']}"
                elif "message" in r:
                    msg = f"{r['message']}"

                    if response.status_code == 403:
                        msg = f"{msg} (hint: did you 'Connect an API' in your Application?)"
                else:
                    msg = f"{r}"

            except JSONDecodeError:
                msg = response.content

            self.logger.error(f"{response.status_code} : {msg}")

            if response.status_code == 401:
                raise AuthenticationException(msg)
            response.raise_for_status()
            return True
        return False

    @backoff.on_exception(
        backoff.expo,
        (HTTPStatusError, ConnectTimeout, ConnectError, TimeoutException),
        max_value=MAX_BACKOFF_VALUE,
        logger=logging.getLogger(__name__),
    )
    async def __call_smart_system_get(self, url):
        try:
            self.logger.debug("Making GET request to: %s", url)
            response = await self.client.get(url, headers=self.create_header())
            if self.__response_has_errors(response):
                return None
            return json.loads(response.content.decode("utf-8"))
        except (ConnectTimeout, ConnectError, TimeoutException) as ex:
            self.logger.error(
                "Connection timeout during GET request to %s: %s", url, ex
            )
            raise ConnectionError(
                f"GET request failed due to connection timeout: {ex}"
            ) from ex
        except Exception as ex:
            self.logger.error("Unexpected error during GET request to %s: %s", url, ex)
            raise

    async def update_locations(self):
        """Update locations from Gardena API with improved error handling."""
        try:
            self.logger.debug("Fetching locations from Gardena API...")
            response_data = await self.__call_smart_system_get(
                f"{self.SMART_HOST}/v2/locations"
            )
            if response_data is not None:
                if "data" not in response_data or len(response_data["data"]) < 1:
                    self.logger.error("No locations found in API response")
                    self.logger.error("Response data: %s", response_data)
                    raise ConnectionError(
                        "No locations found - check if your account has registered devices"
                    )
                self.locations = {}
                for location in response_data["data"]:
                    new_location = Location(self, location)
                    new_location.update_location_data(location)
                    self.locations[new_location.id] = new_location
                self.logger.debug(
                    "Successfully loaded %d locations", len(self.locations)
                )
            else:
                self.logger.error("Empty response when fetching locations")
                raise ConnectionError("Empty response from locations endpoint")
        except ConnectionError:
            # Re-raise connection errors as-is
            raise
        except Exception as ex:
            self.logger.error("Unexpected error fetching locations: %s", ex)
            raise ConnectionError(f"Failed to fetch locations: {ex}") from ex

    async def update_devices(self, location):
        response_data = await self.__call_smart_system_get(
            f"{self.SMART_HOST}/v2/locations/{location.id}"
        )
        if response_data is not None:
            #  TODO : test if key exists
            if len(response_data["data"]["relationships"]["devices"]["data"]) < 1:
                self.logger.error("No device found....")
            else:
                devices_smart_system = {}
                self.logger.debug("Received devices in  message")
                self.logger.debug("------- Beginning of message ---------")
                self.logger.debug(response_data["included"])
                for device in response_data["included"]:
                    real_id = device["id"].split(":")[0]
                    if real_id not in devices_smart_system:
                        devices_smart_system[real_id] = {}
                    if device["type"] in self.supported_services:
                        if device["type"] not in devices_smart_system[real_id]:
                            devices_smart_system[real_id][device["type"]] = []
                        devices_smart_system[real_id][device["type"]].append(device)
                for parsed_device in devices_smart_system.values():
                    device_obj = DeviceFactory.build(location, parsed_device)
                    if device_obj is not None:
                        location.add_device(device_obj)

    async def start_ws(self, location):
        """Start WebSocket connection with improved robustness."""
        connection_attempts = 0
        max_consecutive_failures = 5

        # Gardena API requirement: WebSocket connections have max duration of 2 hours
        max_connection_duration = 2 * 60 * 60  # 2 hours in seconds

        while not self.should_stop:
            self.logger.debug(
                "Trying to connect to gardena API.... (attempt %d)",
                connection_attempts + 1,
            )
            websocket = None
            connection_start_time = asyncio.get_event_loop().time()

            try:
                ws_url = await self.__get_ws_url(location)
                websocket = await self.__launch_websocket_loop(
                    ws_url, connection_start_time, max_connection_duration
                )

                # Reset failure counter on successful connection
                connection_attempts = 0

            except (ConnectionClosed, InvalidTokenError, OAuthError) as error:
                connection_attempts += 1
                self.logger.warning(
                    f"WebSocket connection error (attempt {connection_attempts}): {error}"
                )

                # If too many consecutive failures, increase the delay
                if connection_attempts >= max_consecutive_failures:
                    self.logger.error(
                        f"Too many consecutive WebSocket failures ({connection_attempts}), extending delay"
                    )
                    delay = min(
                        60, 10 + (connection_attempts - max_consecutive_failures) * 10
                    )
                else:
                    delay = 10

            except RateLimitException as error:
                connection_attempts += 1
                delay = self.calculate_backoff_delay()
                self.logger.warning(
                    f"Rate limit reached: {error}. Backing off for {delay} seconds."
                )

            except Exception as error:
                # Handle AttributeError for 'closed' gracefully
                if isinstance(error, AttributeError) and "closed" in str(error):
                    self.logger.info(
                        "WebSocket AttributeError handled in start_ws, treating as closed connection"
                    )
                    # Do NOT count as error, do NOT log as unexpected, just break
                    break
                connection_attempts += 1
                self.logger.error(
                    f"Unexpected WebSocket error (attempt {connection_attempts}): {type(error).__name__}: {error}"
                )
                delay = min(30, 5 + connection_attempts * 2)

            finally:
                self.set_ws_status(False)

                # Ensure WebSocket is properly closed
                if websocket:
                    # Robustly determine if websocket is closed
                    closed = True  # Default to closed
                    try:
                        if hasattr(websocket, "open"):
                            closed = not getattr(websocket, "open", True)
                        elif hasattr(websocket, "closed"):
                            closed_attr = getattr(websocket, "closed", None)
                            if callable(closed_attr):
                                closed = closed_attr()
                            else:
                                closed = (
                                    bool(closed_attr)
                                    if closed_attr is not None
                                    else True
                                )
                        elif hasattr(websocket, "state"):
                            # 1 = OPEN, 2 = CLOSING, 3 = CLOSED (per websockets.protocol)
                            closed = getattr(websocket, "state", 3) != 1
                        elif hasattr(websocket, "close_code"):
                            closed = getattr(websocket, "close_code", None) is not None
                    except (AttributeError, TypeError):
                        closed = True  # If any attribute access fails, treat as closed
                    if not closed:
                        await websocket.close()
                        self.logger.debug("WebSocket connection closed")

            if not self.should_stop:
                delay = self.calculate_backoff_delay()
                self.logger.debug(f"Sleeping {delay} seconds before reconnect..")
                # Use shorter sleep intervals to allow faster shutdown
                await self._wait_with_cancel(delay)

    def calculate_backoff_delay(self):
        """Calculate exponential backoff delay for reconnection attempts."""
        return min(self.max_backoff, self.base_delay * (2**self.connection_attempts))

    async def _wait_with_cancel(self, delay):
        """Wait for specified delay while allowing for cancellation."""
        for _ in range(int(delay)):
            if self.should_stop:
                break
            await asyncio.sleep(1)

    @backoff.on_exception(
        backoff.expo,
        HTTPStatusError,
        max_value=MAX_BACKOFF_VALUE,
        logger=logging.getLogger(__name__),
    )
    async def __get_ws_url(self, location):
        args = {
            "data": {
                "type": "WEBSOCKET",
                "attributes": {"locationId": location.id},
                "id": "does-not-matter",
            }
        }
        self.logger.debug("Trying to get Websocket url")
        r = await self.client.post(
            f"{self.SMART_HOST}/v2/websocket",
            headers=self.create_header(True),
            data=json.dumps(args, ensure_ascii=False),
        )
        self.logger.debug("Websocket url: got response")

        # Check for rate limiting
        if r.status_code == 429:
            raise RateLimitException(
                "API rate limit reached when retrieving WebSocket URL"
            )

        r.raise_for_status()
        response = r.json()
        ws_url = response["data"]["attributes"]["url"]
        self.logger.debug("Websocket url retrieved successfully")
        return ws_url

    async def __launch_websocket_loop(
        self, url, connection_start_time, max_connection_duration
    ):
        """Launch WebSocket connection with improved error handling and 2-hour time limit."""
        self.logger.debug("Connecting to websocket ..")

        # Configure WebSocket with better settings
        websocket = await connect(
            url,
            ping_interval=150,  # Send ping every 150 seconds
            ping_timeout=60,  # Wait 60 seconds for pong
            close_timeout=10,  # Wait 10 seconds for close handshake
            ssl=self._ssl_context,
            max_size=2**20,  # 1MB max message size
            compression=None,  # Disable compression for better performance
        )

        self.set_ws_status(True)
        self.logger.debug("WebSocket connected successfully!")

        try:
            while not self.should_stop:
                # Check if we've exceeded the 2-hour connection limit
                current_time = asyncio.get_event_loop().time()
                if current_time - connection_start_time >= max_connection_duration:
                    self.logger.info(
                        "WebSocket connection reached 2-hour limit, reconnecting as per Gardena API requirements"
                    )
                    break

                try:
                    # Use shorter timeout for more responsive shutdown
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    self.logger.debug("Message received from WebSocket")
                    self.on_message(message)

                except TimeoutError:
                    # Check connection health periodically
                    closed = True  # Default to closed
                    try:
                        if hasattr(websocket, "open"):
                            closed = not getattr(websocket, "open", True)
                        elif hasattr(websocket, "closed"):
                            closed_attr = getattr(websocket, "closed", None)
                            if callable(closed_attr):
                                closed = closed_attr()
                            else:
                                closed = (
                                    bool(closed_attr)
                                    if closed_attr is not None
                                    else True
                                )
                        elif hasattr(websocket, "state"):
                            closed = getattr(websocket, "state", 3) != 1
                        elif hasattr(websocket, "close_code"):
                            closed = getattr(websocket, "close_code", None) is not None
                    except (AttributeError, TypeError) as attr_err:
                        if isinstance(attr_err, AttributeError) and "closed" in str(
                            attr_err
                        ):
                            self.logger.info(
                                "WebSocket AttributeError handled in timeout check, treating as closed connection"
                            )
                            closed = True
                        else:
                            closed = (
                                True  # If any attribute access fails, treat as closed
                            )
                    if closed:
                        self.logger.info(
                            "WebSocket connection closed unexpectedly (handled)"
                        )
                        break
                    continue

                except ConnectionClosed:
                    self.logger.warning("WebSocket connection closed by server")
                    break

        except AttributeError as attr_err:
            if "closed" in str(attr_err):
                self.logger.info(
                    "WebSocket AttributeError handled in message loop, connection likely closed"
                )
            else:
                self.logger.error(
                    "Unexpected AttributeError in WebSocket loop: %s", attr_err
                )
        except Exception as ex:
            self.logger.error(
                "Error in WebSocket message loop: %s: %s", type(ex).__name__, ex
            )
            raise

        finally:
            # Robustly determine if websocket is closed
            closed = True  # Default to closed
            try:
                if hasattr(websocket, "open"):
                    closed = not getattr(websocket, "open", True)
                elif hasattr(websocket, "closed"):
                    closed_attr = getattr(websocket, "closed", None)
                    if callable(closed_attr):
                        closed = closed_attr()
                    else:
                        closed = bool(closed_attr) if closed_attr is not None else True
                elif hasattr(websocket, "state"):
                    closed = getattr(websocket, "state", 3) != 1
                elif hasattr(websocket, "close_code"):
                    closed = getattr(websocket, "close_code", None) is not None
            except (AttributeError, TypeError):
                closed = True  # If any attribute access fails, treat as closed
            if not closed:
                await websocket.close()

        return websocket

    def on_message(self, message):
        data = json.loads(message)
        self.logger.debug("Received %s message", data["type"])
        self.logger.debug("------- Beginning of message ---------")
        self.logger.debug(message)
        if data["type"] == "LOCATION":
            self.logger.debug(">>>>>>>>>>>>> Found LOCATION")
            self.parse_location(data)
        elif data["type"] in self.supported_services:
            self.logger.debug(">>>>>>>>>>>>> Found DEVICE")
            self.parse_device(data)
        else:
            self.logger.debug(">>>>>>>>>>>>> Unkonwn Message")
        self.logger.debug("------- End of message ---------")

    def parse_location(self, location):
        if location["id"] not in self.locations:
            self.logger.debug("Location not found : %s", location["attributes"]["name"])
        self.locations[location["id"]].update_location_data(location)

    def parse_device(self, device):
        device_id = device["id"].split(":")[0]
        for location in self.locations.values():
            if device_id in location.devices:
                location.devices[device_id].update_data(device)
                break

    def add_ws_status_callback(self, callback):
        self.ws_status_callback = callback

    def set_ws_status(self, status):
        self.is_ws_connected = status
        if self.ws_status_callback:
            self.ws_status_callback(status)
