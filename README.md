# Gardena Smart System Integration for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/thecem/gardena-smart-system.svg?style=flat-square)](https://github.com/thecem/gardena-smart-system/releases)
[![GitHub Activity](https://img.shields.io/github/commit-activity/y/thecem/gardena-smart-system.svg?style=flat-square)](https://github.com/thecem/gardena-smart-system/commits)
[![License](https://img.shields.io/github/license/thecem/gardena-smart-system.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

A complete Home Assistant integration for the **Gardena Smart System**, providing comprehensive control and monitoring of your smart garden devices.

## 🌱 Features

### Complete Device Support
- **🤖 Robotic Mowers**: Full control with scheduling, manual override, and real-time status
- **💧 Water Control**: Smart irrigation and watering with timer management
- **🌿 Smart Irrigation**: Multi-valve systems with individual zone control
- **🔌 Power Sockets**: Smart outlet management with timer functionality
- **📊 Environmental Sensors**: Temperature, humidity, light, and soil monitoring
- **🔔 Status Monitoring**: Device connectivity and operational states

### Advanced Features
- **⏱️ Real-time Duration Tracking**: Live countdown timers for all operations
- **🌐 WebSocket Communication**: Instant updates from your devices
- **🔐 OAuth2 Authentication**: Secure API connection with token management
- **🌍 Multi-Language Support**: EN, DE, FR, NL, FI, SK, SV, NB
- **📱 Full Home Assistant Integration**: Native UI, automations, and notifications

## 🚀 Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/thecem/gardena-smart-system` as repository
6. Select "Integration" as category
7. Click "Add"
8. Search for "Gardena Smart System" and install
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub releases](https://github.com/thecem/gardena-smart-system/releases)
2. Extract the files
3. Copy the `custom_components/gardena_smart_system` folder to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant

## ⚙️ Configuration

### Prerequisites

You need a Gardena Smart System account and API credentials:

1. Go to [Gardena Developer Portal](https://developer.husqvarnagroup.cloud/)
2. Create an account and register your application
3. Note your **Client ID** and **Client Secret**

### Setup Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Gardena Smart System"
4. Enter your API credentials:
   - **Client ID**: Your application's client ID
   - **Client Secret**: Your application's client secret
5. Follow the OAuth2 authentication flow
6. Select your garden locations
7. Complete the setup

## 🎛️ Supported Entities

### Lawn Mower
- **Entity Type**: `lawn_mower`
- **Features**: Start, stop, dock, pause, resume
- **Attributes**: Battery level, activity, error states, cutting height
- **Services**:
  - Start mowing
  - Park until next scheduled task
  - Park until further notice
  - Override schedule with duration

### Water Control & Irrigation
- **Entity Type**: `valve`
- **Features**: Open/close valves, duration control
- **Attributes**: Valve activity, remaining time, water flow
- **Services**:
  - Manual watering with duration
  - Stop watering
  - Cancel override

### Power Sockets
- **Entity Type**: `switch`
- **Features**: On/off control, timer operations
- **Attributes**: Power state, activity, remaining time
- **Services**:
  - Turn on/off
  - Override with duration
  - Cancel override

### Sensors
- **Types**: Temperature, humidity, light intensity, soil temperature, soil moisture
- **Attributes**: Real-time values, battery status, signal strength
- **Updates**: Automatic via WebSocket connection

### Binary Sensors
- **Types**: Device connectivity, RF link status, error states
- **States**: Connected/disconnected, online/offline, ok/error

## 🔧 Services

### `gardena_smart_system.start_mowing`
Start mowing operation
```yaml
service: gardena_smart_system.start_mowing
target:
  entity_id: lawn_mower.my_mower
data:
  duration: 60  # minutes (optional)
```

### `gardena_smart_system.park_until_next_task`
Park mower until next scheduled task
```yaml
service: gardena_smart_system.park_until_next_task
target:
  entity_id: lawn_mower.my_mower
```

### `gardena_smart_system.start_watering`
Start watering with duration
```yaml
service: gardena_smart_system.start_watering
target:
  entity_id: valve.my_valve
data:
  duration: 30  # minutes
```

### `gardena_smart_system.stop_watering`
Stop current watering operation
```yaml
service: gardena_smart_system.stop_watering
target:
  entity_id: valve.my_valve
```

## 🌍 Supported Regions

This integration supports all European Gardena Smart System regions:

🇩🇪 Germany | 🇦🇹 Austria | 🇨🇭 Switzerland | 🇫🇷 France | 🇮🇹 Italy | 🇪🇸 Spain | 🇳🇱 Netherlands | 🇧🇪 Belgium | 🇱🇺 Luxembourg | 🇬🇧 United Kingdom | 🇮🇪 Ireland | 🇩🇰 Denmark | 🇸🇪 Sweden | 🇳🇴 Norway | 🇫🇮 Finland | 🇵🇱 Poland | 🇨🇿 Czech Republic | 🇸🇰 Slovakia | 🇭🇺 Hungary | 🇸🇮 Slovenia | 🇭🇷 Croatia | 🇧🇬 Bulgaria | 🇷🇴 Romania | 🇪🇪 Estonia | 🇱🇻 Latvia | 🇱🇹 Lithuania

## 🔄 Automation Examples

### Water Garden When Temperature is High
```yaml
automation:
  - alias: "Water garden when hot"
    trigger:
      - platform: numeric_state
        entity_id: sensor.garden_temperature
        above: 30
    action:
      - service: gardena_smart_system.start_watering
        target:
          entity_id: valve.garden_irrigation
        data:
          duration: 45
```

### Mow Lawn After Rain Stops
```yaml
automation:
  - alias: "Mow after rain"
    trigger:
      - platform: state
        entity_id: binary_sensor.rain_sensor
        from: "on"
        to: "off"
        for: "01:00:00"
    action:
      - service: gardena_smart_system.start_mowing
        target:
          entity_id: lawn_mower.robomow
        data:
          duration: 120
```

## 🛠️ Troubleshooting

### Common Issues

**Integration not appearing in setup**
- Restart Home Assistant after installation
- Check that files are in the correct directory
- Verify HACS installation if using HACS

**Authentication failures**
- Verify your Client ID and Client Secret
- Check that your Gardena account is active
- Ensure your application is approved in the developer portal

**Devices not appearing**
- Ensure devices are online in the Gardena app
- Check that devices are assigned to a location
- Restart the integration from Settings → Devices & Services

**WebSocket connection issues**
- Check your internet connection
- Verify firewall settings
- The integration automatically reconnects after connection loss

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: info
  logs:
    custom_components.gardena_smart_system: debug
```

## 🔧 Development

### Development Container

This project includes a complete development environment using VS Code Dev Containers. The devcontainer provides:

- **Pre-configured Environment**: Debian GNU/Linux 12 (bookworm) with all necessary tools
- **Python Development**: Python 3.11+ with pip3 and Python language extensions
- **Node.js Support**: Node.js, npm, and eslint for JavaScript development
- **Git Integration**: Latest Git version built from source
- **Command Line Tools**: Full suite of development tools (curl, wget, ssh, rsync, etc.)

#### Getting Started with Dev Container

1. **Prerequisites**:
   - [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
   - [Docker](https://docker.com/) or [Podman](https://podman.io/)

2. **Open in Dev Container**:
   ```bash
   # Clone the repository
   git clone https://github.com/thecem/gardena-smart-system.git
   cd gardena-smart-system

   # Open in VS Code
   code .

   # VS Code will prompt to reopen in container
   # Or use Command Palette: "Dev Containers: Reopen in Container"
   ```

3. **Development Features**:
   - **Auto-completion**: Full Python IntelliSense and type checking
   - **Debugging**: Integrated Python debugger for Home Assistant
   - **Testing**: Pre-configured test environment
   - **Linting**: ESLint for JavaScript and Python linting tools
   - **Git Integration**: Full Git workflow with VS Code integration

#### Development Scripts

The devcontainer includes helper scripts in the `scripts/` directory:

- `scripts/develop` - Start Home Assistant in development mode
- `scripts/lint` - Run code linting and formatting
- `scripts/release.sh` - Automated release process
- `scripts/fix-and-release.sh` - Fix git sync issues and release

#### Browser Integration

Use the built-in browser opener for testing:
```bash
# Open Home Assistant in host browser
"$BROWSER" http://localhost:8123
```

### Requirements
- Python 3.11+
- Home Assistant 2025.2.4+

### Dependencies
```
oauthlib==3.2.2
authlib>=1.2.0
backoff>=2.0.0
httpx>=0.24.0
websockets
```

### Local Development Setup

If not using the dev container, set up your environment manually:

1. **Install Python Dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Install Home Assistant**:
   ```bash
   pip3 install homeassistant
   ```

3. **Development Configuration**:
   - Copy the integration to your HA config directory
   - Enable debug logging in `configuration.yaml`
   - Restart Home Assistant

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes using the dev container
4. Add tests if applicable
5. Run linting: `scripts/lint`
6. Submit a pull request

### VS Code Tasks

The project includes pre-configured VS Code tasks:

- **Run Debug (Home Assistant Core)**: Start HA in debug mode
- **Run Lint**: Execute code linting and formatting
- **Run Tests**: Execute test suite (if available)

Access tasks via: `Terminal` → `Run Task` or `Ctrl+Shift+P` → `Tasks: Run Task`

## 📝 Changelog

### v1.0.3 - Complete Integration Implementation
- Complete Gardena Smart System integration
- Full device support for all device types
- Real-time duration tracking and monitoring
- WebSocket communication for live updates
- Multi-language support
- OAuth2 authentication with token management
- Comprehensive error handling and logging
- HACS integration ready

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Home Assistant community
- Gardena/Husqvarna for providing the API
- All contributors and testers

## 🐛 Issues & Feature Requests

Please report issues and feature requests on [GitHub Issues](https://github.com/thecem/gardena-smart-system/issues)

## 💬 Support

- **GitHub Issues**: Bug reports and feature requests
- **Home Assistant Community**: General discussions and help
- **Documentation**: Full guides and API reference

---

**⭐ If you find this integration useful, please give it a star on GitHub!**

