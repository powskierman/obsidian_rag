---
aliases:
tags:
created: 2025-10-13 07:36
ContentType: Reference
Backlink: ""
---
### Main Idea
- 
### References
- 
### Notes
## Overview

This is a comprehensive ESPHome-based thermostat system for controlling a propane stove with Nextion display integration and full Home Assistant compatibility. The system was converted from an Arduino/Blynk implementation to ESPHome with enhanced features and reliability.

## Features

### ✅ Core Functionality
- **DS18B20 Temperature Sensing** with error detection and recovery
- **Hysteresis Control** to prevent short-cycling
- **Time-Based Scheduling** with day-of-week support
- **Home/Away Presence Detection**
- **Manual Override Modes** (Manual Run / Manual Stop)
- **Nextion Display Integration** (Page 3)
- **Configuration Persistence** across reboots
- **System Health Monitoring**

### ✅ Safety Features
- Temperature sensor error detection (3 consecutive bad reads)
- Temperature rate limiting (max 1°C change per reading)
- Manual run timeout protection
- Minimum cycling times to protect equipment
- Invalid value filtering

### ✅ Home Assistant Integration
- **Climate Entity** (full thermostat control)
- **Temperature Sensors** (actual and desired)
- **Configuration Numbers** (correction, hysteresis, schedule times)
- **Status Sensors** (timer active, stove active, sensor health)
- **Control Switches** (manual run, manual stop, temperature averaging)

## Hardware Requirements

### Required Components
1. **ESP32 Development Board**
2. **DS18B20 Temperature Sensor** (connected to GPIO13)
3. **Relay Module** (connected to GPIO12) - controls propane stove
4. **Nextion Display** (UART - TX: GPIO17, RX: GPIO16)

### Pin Assignments
```
GPIO12  - Relay Output (Propane Stove Control)
GPIO13  - DS18B20 Temperature Sensor (OneWire)
GPIO16  - Nextion RX
GPIO17  - Nextion TX
GPIO21  - I2C SDA
GPIO22  - I2C SCL
```

## Configuration

### 1. DS18B20 Sensor Address

**IMPORTANT:** You must replace the placeholder address in `gazebo_page3_thermostat.yaml`:

```yaml
sensor:
  - platform: dallas
    address: 0x000000000000  # ⚠️ REPLACE WITH YOUR ACTUAL ADDRESS
```

To find your DS18B20 address:

1. Upload the configuration with the placeholder address
2. Check the ESPHome logs when the device boots
3. Look for: `Found dallas device at address 0x123456789ABC`
4. Copy that address into the configuration file
5. Re-upload the configuration

### 2. Default Settings

The thermostat comes with sensible defaults that can be adjusted via Home Assistant:

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| Desired Temperature | 21°C | 10-35°C | Target temperature |
| Hysteresis | 1.0°C | 0-5°C | Temperature deadband |
| Temperature Correction | 0°C | -10 to +10°C | Calibration offset |
| Schedule Start | 08:00 | 00:00-23:59 | Heating schedule start time |
| Schedule End | 22:00 | 00:00-23:59 | Heating schedule end time |
| Manual Run Timeout | 120 min | 0-480 min | Auto-disable manual run |
| Temperature Averaging | ON | ON/OFF | Average with previous reading |

### 3. Nextion Display Configuration

The thermostat uses **Page 3** of the Nextion display with the following components:

| Component | ID | Type | Purpose |
|-----------|-----|------|---------|
| `n0` | Desired Temp | Number | Shows target temperature |
| `n1` | Actual Temp | Number | Shows current temperature |
| `Slider0` | Temperature Slider | Slider | Allows setting desired temp |

The system automatically syncs temperature values between Home Assistant and the Nextion display.

## Operation Modes

### Automatic Mode (Default)

The thermostat operates automatically based on:

1. **Home/Away Status** - Must be "Home"
2. **Timer Status** - Must be within scheduled time
3. **Temperature** - Actual vs. Desired comparison

**Heating Logic:**
- Turn ON when: `Actual Temp < Desired Temp`
- Turn OFF when: `Actual Temp >= Desired Temp + Hysteresis`

### Manual Run Mode

Forces the stove **ON** regardless of:
- Temperature readings
- Schedule settings
- Home/Away status

**Safety:** Automatically disables after configured timeout (default 2 hours)

### Manual Stop Mode

Forces the stove **OFF** regardless of all other conditions.

**Priority:** Manual Stop always takes precedence over Manual Run

### Away Mode

When set to "Away":
- Stove is immediately turned OFF
- Remains OFF regardless of temperature or schedule
- Automatically resumes normal operation when set back to "Home"

## Control Priority

The system evaluates conditions in this order (highest to lowest priority):

1. **Manual Stop** → Always OFF
2. **Manual Run** → Always ON (with timeout)
3. **Away Status** → Always OFF when away
4. **Timer Status** → OFF if outside schedule
5. **Temperature** → Normal hysteresis control

## Temperature Sensing

### Error Handling

The DS18B20 sensor includes comprehensive error handling:

1. **Bad Read Detection**
   - Checks for NaN values
   - Validates temperature range (-40°C to +85°C)
   - Tracks consecutive bad reads

2. **Sensor Failure**
   - After 3 consecutive bad reads, reports failure to HA
   - Continues using last known good temperature
   - Automatically recovers when sensor starts working

3. **Rate Limiting**
   - Limits temperature changes to 1°C per update cycle
   - Prevents spurious readings from causing rapid cycling

4. **Optional Averaging**
   - Can average current reading with previous reading
   - Smooths out temperature fluctuations
   - Enable/disable via Home Assistant switch

### Temperature Correction

The temperature correction offset allows you to calibrate the sensor:

```
Displayed Temperature = Raw Temperature + Correction Offset
```

**Example:**
- If sensor reads 20.0°C but actual is 21.0°C
- Set correction to +1.0°C
- System will display and use 21.0°C

## Time-Based Scheduling

### Schedule Configuration

Configure via Home Assistant number entities:

- **Start Time**: Seconds from midnight (e.g., 28800 = 08:00 AM)
- **End Time**: Seconds from midnight (e.g., 79200 = 10:00 PM)
- **Days of Week**: Bit flags (currently all days enabled)

### Schedule Behavior

- **Within Schedule**: Timer Active = True, heating allowed
- **Outside Schedule**: Timer Active = False, stove OFF
- **Day Selection**: Can enable/disable specific days of week

**Helper Conversion:**
```
Hours to Seconds: Hours × 3600
Minutes to Seconds: Minutes × 60
Example: 8:30 AM = (8 × 3600) + (30 × 60) = 30,600 seconds
```

## Home Assistant Configuration

### Climate Entity

```yaml
climate.gazebo_thermostat
```

**Available Attributes:**
- Current temperature
- Target temperature
- HVAC mode (heat/off)
- HVAC action (heating/idle)

### Sensors

```yaml
sensor.gazebo_actual_temperature        # Current room temp
sensor.gazebo_thermostat_wifi_signal    # WiFi strength
sensor.gazebo_thermostat_uptime         # System uptime
```

### Binary Sensors

```yaml
binary_sensor.home_status                      # Home/Away
binary_sensor.timer_active                     # Schedule status
binary_sensor.temperature_sensor_failure       # Sensor health
binary_sensor.stove_active                     # Heating status
```

### Switches

```yaml
switch.manual_run                      # Force ON
switch.manual_stop                     # Force OFF
switch.temperature_averaging           # Enable averaging
```

### Configuration Numbers

```yaml
number.temperature_correction          # Calibration offset
number.hysteresis                      # Temperature deadband
number.desired_temperature             # Target temp
number.schedule_start_time             # Schedule start
number.schedule_end_time               # Schedule end
number.manual_run_timeout              # Timeout minutes
```

### Text Sensors

```yaml
text_sensor.thermostat_status          # Current mode/status
text_sensor.schedule_status            # Schedule window display
```

## System Monitoring

### Health Checks

The system performs automatic health monitoring every 60 seconds:

- Uptime tracking
- Sensor error counting
- WiFi signal strength
- Current operational state

### Status Indicators

The `thermostat_status` text sensor reports:

| Status | Meaning |
|--------|---------|
| Manual Run Active | Forced ON mode |
| Manual Stop Active | Forced OFF mode |
| Away Mode | Home status is Away |
| Outside Schedule | Timer not active |
| Sensor Failure | Temperature sensor problem |
| Heating | Stove currently ON |
| Idle | Stove currently OFF, normal operation |
| OK | Normal operation, conditions met |

## Logging

The system provides detailed logging for troubleshooting:

### Debug Logs (Level: DEBUG)
```
thermostat - Current: 20.5°C, Target: 21.0°C, Hysteresis: 1.0°C
thermostat - Home: 1, Timer: 1, Manual Run: 0, Manual Stop: 0
```

### Info Logs (Level: INFO)
```
thermostat - STOVE ACTIVATED - Heat mode engaged
thermostat - Temperature reached 22.0°C - turning OFF
thermostat - MANUAL RUN MODE ACTIVATED
```

### Warning Logs (Level: WARN)
```
thermostat - Bad temperature read detected: nan
thermostat - Manual run timeout reached (120 minutes)
```

### Error Logs (Level: ERROR)
```
thermostat - SENSOR FAILURE: 3 consecutive bad reads!
```

## Troubleshooting

### Sensor Not Working

**Symptoms:**
- "Temperature Sensor Failure" binary sensor is ON
- Temperature shows NaN or invalid values

**Solutions:**
1. Check DS18B20 wiring (Data → GPIO13, VCC, GND)
2. Verify 4.7kΩ pull-up resistor between Data and VCC
3. Confirm correct sensor address in configuration
4. Check sensor logs for error messages

### Stove Won't Turn On

**Check in order:**
1. Manual Stop switch is OFF
2. Home Status is "Home"
3. Timer is "Active" (within schedule window)
4. Temperature is below target
5. Relay is functioning (check GPIO12 output)

### Stove Won't Turn Off

**Check in order:**
1. Manual Run switch is OFF
2. Temperature has reached target + hysteresis
3. Timer hasn't ended
4. Away mode not activated

### Nextion Display Not Updating

**Solutions:**
1. Verify UART connections (TX ↔ RX crossed properly)
2. Check baud rate is 9600
3. Verify page 3 components exist (n0, n1, Slider0)
4. Review Nextion logs for communication errors

### Manual Run Won't Disable

**Possible causes:**
1. Timeout set to 0 (disabled)
2. Switch not turning off properly
3. Check logs for timeout messages

**Solution:**
- Manually toggle the Manual Run switch OFF in Home Assistant
- Check `manual_run_timeout` setting

## Advanced Customization

### Changing Update Intervals

Edit `gazebo_page3_thermostat.yaml`:

```yaml
# Main control cycle (default: 10 seconds)
interval:
  - interval: 10s  # Change this value

# Health monitoring (default: 60 seconds)
  - interval: 60s  # Change this value
```

### Adding Nextion Visual Indicators

Add visual feedback in the control logic:

```yaml
heat_action:
  - switch.turn_on: gazebo_relay
  - lambda: |-
      // Add your visual indicator here
      id(nextion0).send_command("three.heating_led.val=1");
```

### Customizing Hysteresis Behavior

The hysteresis value can be adjusted in real-time via Home Assistant. For different heating/cooling strategies, modify the control logic in the main interval.

### Adding Additional Sensors

Add more temperature sensors for averaging:

```yaml
sensor:
  - platform: dallas
    id: ds18b20_temp_2
    address: 0x_YOUR_SECOND_SENSOR_ADDRESS
```

## Integration Examples

### Home Assistant Automation - Night Setback

```yaml
automation:
  - alias: "Thermostat Night Setback"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.desired_temperature
        data:
          value: 18
```

### Home Assistant Automation - Morning Warmup

```yaml
automation:
  - alias: "Thermostat Morning Warmup"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.desired_temperature
        data:
          value: 21
```

### Home Assistant Automation - Away Mode

```yaml
automation:
  - alias: "Thermostat Away Mode"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "not_home"
        for:
          minutes: 15
    action:
      - service: binary_sensor.turn_off
        target:
          entity_id: binary_sensor.home_status
```

## Maintenance

### Regular Checks
- **Weekly**: Verify temperature readings are accurate
- **Monthly**: Test manual override modes
- **Quarterly**: Clean temperature sensor
- **Annually**: Verify relay operation, check all connections

### Backup Configuration

Always backup your configuration files:
- `gazebo_page3_thermostat.yaml`
- `secrets.yaml`
- Nextion HMI project file

### Updates

When updating ESPHome:
1. Test on a development device first
2. Backup current working configuration
3. Review ESPHome changelog for breaking changes
4. Update gradually, testing each component

## Safety Warnings

⚠️ **IMPORTANT SAFETY INFORMATION**

1. **Propane Safety**
   - Ensure proper ventilation
   - Install CO detectors
   - Have propane system professionally inspected
   - Never leave unattended for extended periods

2. **Electrical Safety**
   - Use properly rated relay for your stove
   - Ensure all connections are secure and insulated
   - Follow local electrical codes
   - Have a licensed electrician review installation

3. **System Reliability**
   - This is a hobby/DIY project
   - Consider backup heating methods
   - Monitor system operation regularly
   - Don't rely solely on automation for safety

4. **Manual Overrides**
   - Know how to manually control your stove
   - Have physical cutoff switches accessible
   - Test emergency shutdown procedures

## Support and Contributing

### Getting Help

1. Check logs via ESPHome dashboard or Home Assistant
2. Review this documentation thoroughly
3. Verify all hardware connections
4. Test components individually

### Reporting Issues

When reporting issues, include:
- Full ESPHome logs
- Configuration file (with secrets removed)
- Hardware setup description
- Steps to reproduce the problem

## License

This project is provided as-is for educational and hobbyist use. Use at your own risk.

## Version History

### v1.0.0 (Current)
- Initial ESPHome implementation
- Complete requirements coverage
- DS18B20 sensor with error handling
- Hysteresis control
- Time-based scheduling
- Home/Away detection
- Manual overrides
- Nextion integration
- Full Home Assistant integration
- System health monitoring
- Configuration persistence

---

**Created:** October 2025
**Last Updated:** October 2025
**ESPHome Version:** 2024.6.0+
### Related Notes
- 
### Questions / Ideas for Further Exploration
- 
### To-Do
- 
### Smart Connections Insights
- 
