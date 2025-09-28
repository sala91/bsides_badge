# Agent Notes

This repository targets the BSides Tallinn badge hardware. Keep the following
hardware context in mind when making changes:

- ESP32-C3FH4 module (4 MB flash) with integrated Wi-Fi and Bluetooth
- 128x64 pixel SSD1306 OLED display
- 16 WS2812B-compatible addressable LEDs
- Firmware baseline: `ESP32_GENERIC_C3-20250911-v1.26.1.bin`

When modifying code, be mindful of the limited memory available on the
microcontroller and prefer reusing shared resources (e.g., WLAN instances) to
avoid fragmentation.
