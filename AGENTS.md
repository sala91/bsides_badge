# BSides Tallinn Badge – Agent Notes

These notes target the badge hardware so agents can build firmware quickly and safely. Keep memory pressure low and reuse shared objects.

## MCU & Firmware
- **MCU:** ESP32‑C3FH4 (RISC‑V, 4 MB flash, integrated Wi‑Fi/BLE).
- **Baseline firmware:** `ESP32_GENERIC_C3-20250911-v1.26.1.bin` (MicroPython v1.26.1).
- **Heap discipline:** Avoid dynamic allocation inside loops; pre‑allocate buffers; prefer `bytearray` over `bytes`; reuse global singletons (Wi‑Fi, I2C, NeoPixel).

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
- 16 × WS2812 worst‑case ≈ **960 mA** (60 mA/LED at full‑white). Cap brightness (e.g., 64/255) unless USB power is stable. Consider per‑frame power limiting.

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
- **Buttons:** Configure with input + pull‑down (or pull‑up, but mind boot pins). Debounce in software (e.g., 10–20 ms) or use uasyncio edge tasks.

## Wi‑Fi & BLE
- Keep a **single global** Wi‑Fi station (don’t repeatedly `WLAN()`); cache credentials; reuse sockets.
- For BLE beacons, throttle allocations; use pre‑built advertising payloads.

## Memory & Perf Tips
- Use **frozen modules** for static drivers/assets (fonts, logos) to cut RAM.
- For animations, build **one** 16×3 RGB `bytearray` and mutate in place; avoid per‑frame list/tuple construction.
- Double‑buffer the OLED only if needed; otherwise draw directly into the `framebuf`.
- Prefer integer math and table lookups over `math.sin` in tight loops.

## Minimal Bring‑Up Checklist
1. Power from **USB‑C**; confirm 3V3 rail.
2. Flash baseline MicroPython; confirm USB REPL.
3. Check I²C scan → address **0x3C** (typical SSD1306).
4. Light one LED at index 0; verify order matches physical.
5. Read all four buttons; verify boot still OK after presses at reset.

## Known gotchas
- **GPIO9**: don’t drive as output; it’s a bootstrap. Keep pull‑ups/downs consistent across reset.
- **Buttons on 4/5/8/9**: these share SPI/boot roles—configure with gentler pulls and debounce to avoid spurious boots.
- **LEDs**: Excessive white can brown‑out on weak USB sources.

---
*Edit this page as the single source of truth. Keep it tight, pragmatic, and agent‑friendly.*

