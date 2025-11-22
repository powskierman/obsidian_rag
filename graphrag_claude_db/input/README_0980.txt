---
aliases:
tags:
created: 2025-09-26 08:52
ContentType: Reference
Backlink: ""
---
### Main Idea
- 
### References
- 
### Notes
Gazebo Thermostat (ESPHome + Nextion)

Hardware
- ESP32 DevKit (adjust pins if different)
- Nextion display (page 0 HMI)
- SHT3x temperature/humidity sensor on I2C
- Relay module to drive heater

Default pins
- Nextion TX/RX: ESP32 GPIO17 (TX) -> Nextion RX, GPIO16 (RX) -> Nextion TX, 5V and GND
- I2C: SDA GPIO21, SCL GPIO22
- Relay: GPIO23 (active HIGH)

Files
- `gazebo_thermostat.yaml`: ESPHome configuration

Nextion HMI expectations (page 0)
- Text: `t_title`, `t_temp`, `t_hum`, `t_set`, `t_mode`
- Buttons: `b_up`, `b_dn`, `b_mode`
- Optional picture: `p_icon`

What it does
- Bang-bang thermostat using `climate:`. Relay turns on in HEAT mode according to setpoint.
- Nextion shows temperature, humidity, setpoint, and mode.
- `b_up`/`b_dn` adjust setpoint by 0.5 °C. `b_mode` toggles OFF/HEAT.

Setup
1. Put Wi‑Fi and API secrets in your ESPHome `secrets.yaml`:
   - `wifi_ssid`, `wifi_password`, `api_key`
2. Open the YAML in ESPHome and flash to your ESP32.
3. Upload your `.tft` to the Nextion. Ensure component names match above.
4. If your HMI uses different component IDs for buttons, update `component_id` values in `binary_sensor:`.

Customize
- Change relay pin under `output:`.
- Replace SHT3x with your sensor; update `sensor:` block accordingly.
- If you use a different baud or pins, adjust the `uart:` block.
- To display external weather or feels-like, publish to additional text components via `id(nextion0).set_component_text(...)` in automations.
### Related Notes
- 
### Questions / Ideas for Further Exploration
- 
### To-Do
- 
### Smart Connections Insights
- 
