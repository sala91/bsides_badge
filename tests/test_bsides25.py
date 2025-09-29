import asyncio as pyasyncio
from pathlib import Path

import pytest


class FakeOLED:
    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.operations = []

    def fill(self, value):
        self.operations.append(("fill", value))

    def rect(self, *args):
        self.operations.append(("rect", args))

    def vline(self, *args):
        self.operations.append(("vline", args))

    def fill_rect(self, *args):
        self.operations.append(("fill_rect", args))

    def show(self):
        self.operations.append(("show",))

    def set_textpos(self, row, col):
        self.operations.append(("set_textpos", row, col))


class DummyWriter:
    def __init__(self):
        self.calls = []

    def set_textpos(self, device, row, col):
        self.calls.append(("set_textpos", row, col))
        device.set_textpos(row, col)

    def printstring(self, text):
        self.calls.append(("printstring", text))


@pytest.fixture(autouse=True)
def reset_led_state(bsides25_module, tmp_path, monkeypatch):
    module = bsides25_module
    module.led_effects[:] = [("Rainbow", object()), ("Fire", object())]
    module.led_effect.value = 0
    module.led_effect.maxval = 3
    module.led_brightness.value = 10
    module.led_brightness.maxval = 100
    module.led_hue.value = 120
    module.led_hue.maxval = 360
    module.led_sat.value = 80
    module.led_sat.maxval = 100
    module.led_speed.value = 20
    module.led_speed.maxval = 100
    module.homeassistant = None
    monkeypatch.chdir(tmp_path)
    module.params.clear()
    module.params.update({
        "Brightness": module.led_brightness,
        "Hue": module.led_hue,
        "Saturation": module.led_sat,
        "Speed": module.led_speed,
        "Light_effect": module.led_effect,
        "SnakeHighScore": module.snake_high_score,
    })
    module.snake_high_score.value = 0
    yield


def test_clamp(bsides25_module):
    module = bsides25_module
    assert module._clamp(5, 0, 10) == 5
    assert module._clamp(-1, 0, 10) == 0
    assert module._clamp(42, 0, 10) == 10


def test_get_led_state_for_homeassistant(bsides25_module):
    module = bsides25_module
    module.led_effect.value = 1
    module.led_brightness.value = 50
    module.led_hue.value = 270
    module.led_sat.value = 70
    module.led_speed.value = 33

    state = module.get_led_state_for_homeassistant()

    assert state["effect_index"] == 1
    assert state["effect_name"] == "Fire"
    assert state["brightness"] == module._clamp(int((50 * 255) / 100), 0, 255)
    assert state["hue"] == 270
    assert state["saturation"] == 70
    assert state["speed"] == 33


def test_apply_homeassistant_command_updates(bsides25_module):
    module = bsides25_module
    cmd = {
        "effect": "Fire",
        "brightness": 200,
        "hs_color": (30, 45),
        "speed": 90,
    }

    changed = module.apply_homeassistant_command(cmd)

    assert changed is True
    assert module.led_effect.value == 1
    expected_brightness = module._clamp(int((200 * module.led_brightness.maxval) / 255), 0, module.led_brightness.maxval)
    assert module.led_brightness.value == expected_brightness
    assert module.led_hue.value == 30
    assert module.led_sat.value == 45
    assert module.led_speed.value == 90

    params_file = Path(module.FILENAME)
    assert params_file.exists()


def test_apply_homeassistant_command_invalid_input(bsides25_module):
    module = bsides25_module
    cmd = {
        "effect": "Unknown",
        "brightness": "not-a-number",
        "hs_color": ("x", "y"),
        "speed": None,
    }

    changed = module.apply_homeassistant_command(cmd)

    assert changed is False
    assert module.led_effect.value == 0
    assert module.led_brightness.value == 10
    assert module.led_hue.value == 120
    assert module.led_sat.value == 80
    assert module.led_speed.value == 20


def test_is_valid_hex_id(bsides25_module):
    module = bsides25_module
    assert module.is_valid_hex_id("A1B2C3D4E5F6") is True
    assert module.is_valid_hex_id("12345") is False
    assert module.is_valid_hex_id("G1B2C3D4E5F6") is False


def test_load_or_create_device_id_persists(bsides25_module, tmp_path, monkeypatch):
    module = bsides25_module
    module.urandom.reset()
    file_path = tmp_path / "custom_id.txt"
    monkeypatch.setattr(module, "ID_FILENAME", str(file_path))

    created = module.load_or_create_device_id()
    assert len(created) == 12
    assert file_path.read_text() == created

    # Subsequent load should reuse the stored value and not advance RNG
    module.urandom.reset()
    loaded = module.load_or_create_device_id()
    assert loaded == created


def test_get_shared_wlan_singleton(bsides25_module):
    module = bsides25_module
    module._shared_wlan = None
    wlan1 = module.get_shared_wlan()
    wlan2 = module.get_shared_wlan()
    assert wlan1 is wlan2
    assert module.network.WLAN.instances_created == 1


def test_param_screen_smoke(bsides25_module):
    module = bsides25_module
    oled = FakeOLED(module.OLED_WIDTH, module.OLED_HEIGHT)
    writer = DummyWriter()
    param = module.Parameter("Brightness", 0, 10)

    screen = module.ParamScreen(oled, writer, param, lambda o: "menu", barfill=True)
    screen.render()

    assert any(call[0] == "printstring" for call in writer.calls)

    pyasyncio.run(screen.handle_button(module.BTN_NEXT))
    assert param.value == 1

    pyasyncio.run(screen.handle_button(module.BTN_PREV))
    assert param.value == 0
