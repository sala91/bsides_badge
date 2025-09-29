# BSides 25 badge

## Hardware

ESP32-C3FH4 (4MB flash) with WiFi and Bluetooth

128x64 px OLED display (SSD1306)

16 WS2812B (Neopixel compatible) LEDs

USB-C for flashing/charging

[Schematics](./hardware/BSides_2025_badge_v1.1_schematics.pdf)

## Software

The code in `software` is written in MicroPython and loaded onto the badge via USB-C connector.

Update the code by uploading via `mpremote` or directly via some IDE like [Thonny](https://thonny.org/).

## Device preparation

Install `esptool` and `mpremote`
```
pip install --user esptool mpremote
```

Install [MicroPython](https://micropython.org/download/ESP32_GENERIC_C3).

For BSides 2025: v1.26.1 (2025-09-11)
```
wget https://micropython.org/resources/firmware/ESP32_GENERIC_C3-20250911-v1.26.1.bin
esptool --port <port> erase_flash
esptool --port <port> --baud 921600 write_flash 0 ESP32_GENERIC_C3-20250911-v1.26.1.bin
```

## Copy files to the badge

```
mpremote <port> fs cp -r software/* :/
```

If the code is already running on the badge and `mpremote` does not connect, hold `SELECT` button down while resetting your badge (pressing `RESET` button or toggling ON/OFF switch).

### Badge setup utilities

From the "Badge setup" menu on the device you can:

* Fetch your display name from the registration service.
* Scan for nearby WiFi networks – the list refreshes automatically after a scan completes, and you can press `SELECT` to trigger another scan if needed.
* View the Git repository URL for the firmware.

## Snake Game Fork

This fork adds a fully playable snake game to the BSides badge menu.
  
PREV - Turn left  
NEXT - Turn right 
SELECT - Pause/New Game  
BACK - Back to the menu  

## Home Assistant integration

Create a file named `homeassistant.json` in the root of the badge filesystem to enable the optional MQTT integration.  When Wi-Fi credentials are supplied the badge will connect automatically, publish Home Assistant discovery information, and expose the LED ring as a controllable light entity.  If you would like the bridge to reuse the built-in BSides SSID/password, set `"use_defaults": true` inside the `wifi` block; otherwise the bridge waits for an existing connection (for example, one initiated from the Fetch Name workflow).

Example configuration:

```
{
  "wifi": {
    "ssid": "MyWiFi",
    "password": "supersecret"
  },
  "mqtt": {
    "broker": "192.168.1.10",
    "port": 1883,
    "username": "ha",
    "password": "ha-pass",
    "discovery_prefix": "homeassistant"
  }
}
```

To use the default BSides Wi-Fi credentials instead of providing your own SSID, supply an empty `wifi` block with `"use_defaults": true`.

```
{
  "wifi": {
    "use_defaults": true
  },
  "mqtt": {
    "broker": "192.168.1.10"
  }
}
```

Once connected, Home Assistant will show a light entity named after the badge ID.  The entity supports on/off, brightness, hue/saturation colour control and selecting any of the badge's LED effects.  Remote changes are persisted to `params.json`, while on-device adjustments immediately update the entity state.
