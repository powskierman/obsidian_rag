---
aliases:
tags:
created: 2025-10-06 08:51
ContentType: Reference
Backlink: ""
---
### Main Idea
- 
### References
- 
### Notes
This directory contains a modular ESPHome configuration for the Gazebo Thermostat project. The configuration has been separated into logical files for better maintainability and organization.

## File Structure

### Main Configuration
- **`gazebo_thermostat_modular.yaml`** - Main configuration file that includes all modular components
- **`gazebo_thermostat.yaml`** - Original monolithic configuration (kept for reference)

### Modular Components

#### Core Configuration
- **`gazebo_base.yaml`** - Core ESPHome settings including:
  - Device settings and boot sequence
  - WiFi and network configuration
  - Time synchronization (SNTP)
  - Hardware setup (GPIO, I2C, UART)
  - Nextion display setup

#### Page-Specific Configurations
- **`gazebo_page0.yaml`** - Page 0 sensors (current outdoor conditions):
  - Current temperature (feels_like)
  - Current humidity (rain)

- **`gazebo_page1.yaml`** - Page 1 sensors (7-hour forecast):
  - Column 1: Time (dt0-dt6) - Template sensors
  - Column 2: Weather Icons (wxIcon0-wxIcon6)
  - Column 3: Feels Like Temperature (fl0-fl6)
  - Column 4: Precipitation (rain0-rain6)

- **`gazebo_page2.yaml`** - Page 2 sensors (extended forecast):
  - Column 1: Time (dt10-dt16) - Template sensors (shared with Page 1)
  - Column 2: Weather Icons (wxIcon10-wxIcon16)
  - Column 3: Temperature (temp0-temp6)
  - Column 4: Humidity (humidity0-humidity6)

#### Navigation and UI
- **`gazebo_navigation.yaml`** - Nextion navigation controls:
  - Page navigation buttons (Back/Next for each page)
  - Text sensors for WiFi info and time display

## Usage

### Using the Modular Configuration
To use the modular configuration, compile and upload using:

```bash
esphome compile gazebo_thermostat_modular.yaml
esphome upload gazebo_thermostat_modular.yaml
```

### Using Individual Components
Each modular file can be used independently by including it in a main configuration file:

```yaml
# Example: Using only base + page 0
<<: !include gazebo_base.yaml
<<: !include gazebo_page0.yaml
```

## Benefits of Modular Structure

1. **Maintainability** - Each page and function is in its own file
2. **Readability** - Clear separation of concerns
3. **Reusability** - Components can be mixed and matched
4. **Debugging** - Easier to isolate issues to specific pages
5. **Collaboration** - Multiple developers can work on different pages simultaneously

## File Dependencies

- All modular files depend on `gazebo_base.yaml` for core functionality
- Page-specific files are independent of each other
- `gazebo_navigation.yaml` can be used with any combination of page files
- The main modular file includes all components

## Configuration Validation

All configurations have been tested and validated using ESPHome:

```bash
esphome config gazebo_thermostat_modular.yaml
```

The configuration is valid and ready for deployment.

## Nextion Display Pages

- **Page 0 (zero)**: Current outdoor conditions
- **Page 1 (one)**: 7-hour forecast with time, weather icons, feels like temperature, and precipitation
- **Page 2 (two)**: Extended forecast with time, weather icons, temperature, and humidity

Each page has navigation buttons to move between pages in a circular fashion (0→1→2→0).
### Related Notes
- 
### Questions / Ideas for Further Exploration
- 
### To-Do
- 
### Smart Connections Insights
- 
