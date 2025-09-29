import importlib
import sys
import types
from pathlib import Path

import pytest


def _install_stub_modules():
    if "ubinascii" not in sys.modules:
        import binascii

        ubinascii = types.ModuleType("ubinascii")
        ubinascii.hexlify = binascii.hexlify
        sys.modules["ubinascii"] = ubinascii

    class _URandom(types.ModuleType):
        def __init__(self):
            super().__init__("urandom")
            self._values = [0x10, 0x32, 0x54, 0x76, 0x98, 0xBA]
            self._idx = 0

        def getrandbits(self, bits):
            value = self._values[self._idx % len(self._values)]
            self._idx += 1
            return value & ((1 << bits) - 1)

        def reset(self):
            self._idx = 0

    sys.modules.setdefault("urandom", _URandom())

    if "network" not in sys.modules:
        network = types.ModuleType("network")

        class DummyWLAN:
            instances_created = 0

            def __init__(self, iface):
                self.iface = iface
                self.active_state = False
                DummyWLAN.instances_created += 1

            def active(self, state=None):
                if state is None:
                    return self.active_state
                self.active_state = state

        network.WLAN = DummyWLAN
        network.STA_IF = 0
        sys.modules["network"] = network

    if "socket" not in sys.modules:
        socket = types.ModuleType("socket")
        socket.SOCK_STREAM = 1
        socket.AF_INET = 2

        class DummySocket:
            def __init__(self, *args, **kwargs):
                pass

            def connect(self, *args, **kwargs):
                return None

            def close(self):
                return None

        socket.socket = DummySocket
        sys.modules["socket"] = socket

    if "ssl" not in sys.modules:
        ssl_mod = types.ModuleType("ssl")

        def wrap_socket(sock, *args, **kwargs):
            return sock

        ssl_mod.wrap_socket = wrap_socket
        sys.modules["ssl"] = ssl_mod

    if "uasyncio" not in sys.modules:
        uasyncio = types.ModuleType("uasyncio")

        class DummyTask:
            def __init__(self, coro):
                self.coro = coro
                self._cancelled = False

            def cancel(self):
                self._cancelled = True

        async def sleep_ms(_ms):
            return None

        def create_task(coro):
            return DummyTask(coro)

        class CancelledError(Exception):
            pass

        uasyncio.sleep_ms = sleep_ms
        uasyncio.create_task = create_task
        uasyncio.CancelledError = CancelledError
        sys.modules["uasyncio"] = uasyncio

    if "micropython" not in sys.modules:
        micropython = types.ModuleType("micropython")

        def schedule(func, arg):
            func(arg)

        micropython.schedule = schedule
        sys.modules["micropython"] = micropython

    if "machine" not in sys.modules:
        machine = types.ModuleType("machine")

        class Pin:
            IN = 0
            OUT = 1
            IRQ_FALLING = 2
            IRQ_RISING = 4

            def __init__(self, *args, **kwargs):
                self._value = kwargs.get("value", 1)

            def irq(self, *args, **kwargs):
                return None

            def value(self):
                return self._value

        class I2C:
            def __init__(self, *args, **kwargs):
                pass

        machine.Pin = Pin
        machine.I2C = I2C
        sys.modules["machine"] = machine

    if "ssd1306" not in sys.modules:
        ssd1306 = types.ModuleType("ssd1306")

        class SSD1306_I2C:
            def __init__(self, width, height, _i2c):
                self.width = width
                self.height = height
                self.ops = []

            def fill(self, value):
                self.ops.append(("fill", value))

            def rect(self, *args):
                self.ops.append(("rect", args))

            def vline(self, *args):
                self.ops.append(("vline", args))

            def fill_rect(self, *args):
                self.ops.append(("fill_rect", args))

            def show(self):
                self.ops.append(("show",))

            def blit(self, *_args):
                self.ops.append(("blit", _args))

        ssd1306.SSD1306_I2C = SSD1306_I2C
        sys.modules["ssd1306"] = ssd1306

    if "neopixel" not in sys.modules:
        neopixel = types.ModuleType("neopixel")

        class NeoPixel:
            def __init__(self, *_args, **_kwargs):
                self.pixels = []

            def fill(self, color):
                self.pixels = [color]

            def write(self):
                return None

            def __setitem__(self, index, value):
                if index >= len(self.pixels):
                    self.pixels.extend([(0, 0, 0)] * (index + 1 - len(self.pixels)))
                self.pixels[index] = value

        neopixel.NeoPixel = NeoPixel
        sys.modules["neopixel"] = neopixel

    if "writer" not in sys.modules:
        writer_pkg = types.ModuleType("writer")
        writer_pkg.__path__ = []  # Mark as package
        sys.modules["writer"] = writer_pkg

        writer_writer = types.ModuleType("writer.writer")

        class DummyWriter:
            def __init__(self, device, font, verbose=False):
                self.device = device
                self.font = font
                self.verbose = verbose
                self.calls = []

            def set_textpos(self, device, row, col):
                self.calls.append(("set_textpos", row, col))
                if hasattr(device, "set_textpos"):
                    device.set_textpos(row, col)

            def printstring(self, text):
                self.calls.append(("printstring", text))

        writer_writer.Writer = DummyWriter
        sys.modules["writer.writer"] = writer_writer

        def _make_font_module(name):
            mod = types.ModuleType(name)

            def height():
                return 8

            def max_width():
                return 8

            def hmap():
                return True

            def reverse():
                return False

            mod.height = height
            mod.max_width = max_width
            mod.hmap = hmap
            mod.reverse = reverse
            return mod

        for sub in ("freesans20", "font10", "font6"):
            mod = _make_font_module(f"writer.{sub}")
            sys.modules[f"writer.{sub}"] = mod

    if "bsides_logo" not in sys.modules:
        bsides_logo = types.ModuleType("bsides_logo")

        class DummyLogo:
            width = 128
            height = 64

        bsides_logo.fb = DummyLogo()
        sys.modules["bsides_logo"] = bsides_logo


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bsides25_module(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("badge_runtime")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BSIDES_BADGE_SKIP_MAIN", "1")
    _install_stub_modules()
    software_dir = _project_root() / "software"
    monkeypatch.syspath_prepend(str(software_dir))
    module = importlib.import_module("bsides25")

    class _TimeStub:
        def __init__(self):
            self._now = 0

        def ticks_ms(self):
            self._now += 100
            return self._now

        @staticmethod
        def ticks_diff(a, b):
            return a - b

        @staticmethod
        def ticks_add(a, b):
            return a + b

    module.time = _TimeStub()
    module.urandom.reset()
    try:
        yield module
    finally:
        monkeypatch.undo()
