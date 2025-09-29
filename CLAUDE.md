# BSides Tallinn Badge – Claude Code Notes

These notes target the badge hardware so Claude Code can build firmware quickly and safely. Keep memory pressure low and reuse shared objects.

## MCU & Firmware
- **MCU:** ESP32‑C3FH4 (4 MB flash, 400kB ram, 2.4Ggz RISC-V core, integrated Wi‑Fi/BLE). 
- **Baseline firmware:** `ESP32_GENERIC_C3-20250911-v1.26.1.bin` (MicroPython v1.26.1). 
- **Heap discipline:** Avoid dynamic allocation inside loops; pre‑allocate buffers; prefer `bytearray` over `bytes`; reuse global singletons (Wi‑Fi, I2C, NeoPixel).

##  ESP32-C3 Wi-Fi Feature List
The following features are supporte:
* 4 virtual Wi-Fi interfaces, which are STA, AP, Sniffer and reserved.
* Station-only mode, AP-only mode, station/AP-coexistence mode
* IEEE 802.11b, IEEE 802.11g, IEEE 802.11n, and APIs to configure the protocol mode
* WPA/WPA2/WPA3/WPA2-Enterprise/WPA3-Enterprise/WAPI/WPS and DPP
* AMSDU, AMPDU, HT40, QoS, and other key features
* Modem-sleep
* The Espressif-specific ESP-NOW protocol and Long Range mode, which supports up to 1 km * of data traffic
* Up to 20 MBit/s TCP throughput and 30 MBit/s UDP throughput over the air
* Sniffer
* Both fast scan and all-channel scan
* Multiple antennas
* Channel state information

For more info on networking see [Espressif](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32c3/api-guides/wifi.html) and [Micropython](https://docs.micropython.org/en/latest/library/network.WLAN.html) documentation.

## Pin Map (high‑value)
| Function | Pin | Notes |
|---|---:|---|
| **OLED I²C SCL** | GPIO1 | SSD1306‑compatible 128×64 display (0.96")
| **OLED I²C SDA** | GPIO0 |
| **WS2812 LED DIN** | GPIO3 | 16 LEDs in series; buffer once, `np.write()` sparingly.
| **Buttons** | GPIO4, GPIO5, GPIO8, GPIO9 | 8/9 are **bootstrap pins**; avoid driving 9 as output; use internal pulls with care.
| **UART0 TX / RX** | GPIO21 / GPIO20 | Exposed on header; leave for debug if possible.
| **USB D+ / D‑** | D+ / D‑ internal USB (native) | Via Type‑C; enumerate as UART/CDC.
| **SPI (bootstrap)** | GPIO2 (MISO), 6 (CLK), 7 (MOSI), 10 (CS0), 4 (HD), 5 (WP) | 4/5 also used as buttons.

> Rule of thumb: Treat **GPIO8/9** as read‑mostly; never put time‑critical outputs on them. Prefer **GPIO3** for LEDs, **GPIO0/1** for I²C.

## Power Topology
- **Battery:** Single‑cell Li‑ion via holder; system rail **VBAT**.
- **Charge:** Linear charger (single‑cell) from **VBUS**; status LED present.
- **Regulators:** Buck to **+3V3** for load; LDO path from filtered VBUS; separate **+3V3_RF** feed to radio.
- **USB‑C:** CC resistors for sink; D+/D‑ routed to the MCU; ferrite/TVS filtering present.

### LED Current Budget
- 16 × WS2812 worst‑case ≈ **960 mA** (60 mA/LED at full‑white). Cap brightness (e.g., 64/255) unless USB power is stable. Consider per‑frame power limiting.

## Boot & Flashing
- Native USB works for flashing/REPL.
- Bootstrap truth table (for reference): keep **GPIO2=1**, **GPIO9=1** for normal SPI boot; enter ROM bootloader with **2=1, 8=1, 9=0**. Avoid wiring that forces 9 low during resets (buttons on 8/9 can influence boot).

## Driver choices (MicroPython)
- **OLED:** Use `ssd1306.py` with `framebuf`. Example init:
  ```py
  from machine import Pin, I2C
  import ssd1306

  i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400_000)
  oled = ssd1306.SSD1306_I2C(128, 64, i2c)
  oled.text("BSides", 0, 0)
  oled.show()
  ```
- **LEDs:** Use built‑in `neopixel`:
  ```py
  import neopixel
  from machine import Pin

  NPIX = 16
  np = neopixel.NeoPixel(Pin(3), NPIX)

  buf = bytearray(NPIX*3)  # reuse this buffer
  for i in range(NPIX):
      # write into buf (r,g,b)
      buf[3*i:3*i+3] = b"\x10\x00\x00"  # dim red
  np.buf = buf          # if using a patched driver; else set per‑pixel then np.write()
  np.write()
  ```
- **Buttons:** Configure with input + pull‑down (or pull‑up, but mind boot pins). Debounce in software (e.g., 10–20 ms) or use uasyncio edge tasks.

## Wi‑Fi & BLE
- Keep a **single global** Wi‑Fi station (don't repeatedly `WLAN()`); cache credentials; reuse sockets.
- For BLE beacons, throttle allocations; use pre‑built advertising payloads.

## Memory & Perf Tips
- Use **frozen modules** for static drivers/assets (fonts, logos) to cut RAM.
- For animations, build **one** 16×3 RGB `bytearray` and mutate in place; avoid per‑frame list/tuple construction.
- Double‑buffer the OLED only if needed; otherwise draw directly into the `framebuf`.
- Prefer integer math and table lookups over `math.sin` in tight loops.

## Known gotchas
- **GPIO9**: don't drive as output; it's a bootstrap. Keep pull‑ups/downs consistent across reset.
- **Buttons on 4/5/8/9**: these share SPI/boot roles—configure with gentler pulls and debounce to avoid spurious boots.
- **LEDs**: Excessive white can brown‑out on weak USB sources.

## Testing
- Use the repository root script `./run_tests_badge.sh` (which wraps `pytest`) before sending firmware patches.
- Tests rely on stubbed MicroPython modules; keep the `BSIDES_BADGE_SKIP_MAIN` environment guard in `bsides25.py` intact or the test harness will execute the event loop.
- Place new unit tests under `tests/` and extend the fixtures there instead of importing hardware drivers directly.

---
*Edit this page as the single source of truth. Keep it tight, pragmatic, and Claude Code-friendly.*